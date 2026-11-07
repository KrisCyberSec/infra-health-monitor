#!/usr/bin/env python3
"""Collect real host metrics and print one JSON document on stdout.

The object matches the health-check shape: a ``checks`` list with one
record. Stdout is JSON only. Diagnostics go to stderr and name the
failing step. They do not include log lines, usernames, addresses, or
key material.

``failed_logins_last_hour`` counts sshd ``Failed password`` and
``Failed keyboard-interactive`` lines in the last hour. It is null off
Linux, and null when those logs cannot be read. A zero means the logs
were readable and no matching line was in the window.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

_RUNNING = {"active", "reloading", "activating"}
_FAILED_LOGIN = re.compile(
    r"Failed password for |Failed keyboard-interactive(?:/pam)? for ",
    re.IGNORECASE,
)
_REPEATED = re.compile(r"message repeated (\d+) times: \[ (.+?)\]\s*$")
_SYSLOG = re.compile(
    r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+\S+\s+(.*)$"
)
_ISO = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+\S+\s+(.*)$"
)
_JOURNAL_INCOMPLETE = (
    "not seeing messages from other users and the system",
    "insufficient permissions",
    "No journal files were opened",
)
_UNITS = {
    "sshd": ("ssh.service", "sshd.service", "ssh.socket", "sshd.socket"),
    "nginx": ("nginx.service",),
    "apache2": ("apache2.service",),
}


def _env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "LC_ALL": "C",
        "LANG": "C",
        "SYSTEMD_COLORS": "0",
    }


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hostname() -> str:
    try:
        name = socket.gethostname().strip()
    except OSError:
        return "unknown"
    return name or "unknown"


def _as_int_percent(value: float) -> int:
    if not math.isfinite(value):
        raise ValueError("non-finite percent")
    return int(round(value))


def _metric(fn) -> int | None:
    try:
        return _as_int_percent(float(fn()))
    except Exception:
        print("collect_metrics: percent metric failed", file=sys.stderr)
        return None


def _unit_facts(systemctl: str, unit: str) -> tuple[str, str] | None:
    active_proc = _run([systemctl, "is-active", unit], timeout=8)
    load_proc = _run([systemctl, "show", unit, "-p", "LoadState", "--value"], timeout=8)
    if active_proc is None and load_proc is None:
        return None
    active = ""
    if active_proc is not None and active_proc.stdout.strip():
        active = active_proc.stdout.strip().splitlines()[-1].strip().lower()
    load = ""
    if load_proc is not None and load_proc.returncode == 0 and load_proc.stdout.strip():
        load = load_proc.stdout.strip().splitlines()[-1].strip().lower()
    if not active and not load:
        return None
    return active, load


def _status_for_units(units: tuple[str, ...]) -> str:
    """Map systemctl is-active / LoadState onto the health-check labels.

    ``systemctl is-active`` prints ``inactive`` both for a stopped unit and,
    on current systemd, often for a unit that is not installed. LoadState
    separates those. An installed unit that is stopped is reported as
    ``inactive`` because the requested set has no honest label for it.
    """
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return "unknown"

    saw_failed = False
    saw_present = False
    queried = False
    inconclusive = False

    for unit in units:
        facts = _unit_facts(systemctl, unit)
        if facts is None:
            continue
        active, load = facts
        queried = True
        if load == "not-found" or active == "not-found":
            continue
        # Without LoadState, "inactive" is ambiguous (stopped vs missing).
        if load == "" and active not in _RUNNING and active != "failed":
            inconclusive = True
            continue
        saw_present = True
        if active in _RUNNING:
            return "running"
        if active == "failed":
            saw_failed = True

    if saw_failed:
        return "failed"
    if saw_present:
        return "inactive"
    if inconclusive or not queried:
        return "unknown"
    return "not-installed"


def _service_map() -> dict[str, str]:
    return {name: _status_for_units(units) for name, units in _UNITS.items()}


def _count_login_line(line: str, require_sshd_tag: bool) -> int:
    repeated = _REPEATED.search(line)
    if repeated:
        body = repeated.group(2)
        source = line
        try:
            times = int(repeated.group(1))
        except ValueError:
            return 0
        if times < 1:
            return 0
    else:
        body = line
        source = line
        times = 1
    if require_sshd_tag and "sshd" not in source:
        return 0
    if _FAILED_LOGIN.search(body) is None:
        return 0
    return times


def _in_last_hour(when: datetime, now: datetime) -> bool:
    return now - timedelta(hours=1) <= when <= now + timedelta(minutes=2)


def _system_tz():
    """Zone used by local syslog timestamps.

    rsyslog writes wall time in the zone of /etc/localtime. A fixed offset
    taken from "now" is wrong across a daylight-saving change, and the TZ
    environment variable does not change how the log was written.
    """
    cached = getattr(_system_tz, "cache", None)
    if cached is not None:
        return cached
    tz = None
    try:
        from zoneinfo import ZoneInfo

        resolved = os.path.realpath("/etc/localtime")
        marker = "zoneinfo/"
        pos = resolved.find(marker)
        if pos != -1:
            tz = ZoneInfo(resolved[pos + len(marker) :])
    except Exception:
        tz = None
    if tz is None:
        tz = datetime.now().astimezone().tzinfo
    _system_tz.cache = tz
    return tz


def _parse_syslog_time(month: str, day: str, hms: str, now: datetime) -> datetime | None:
    tz = _system_tz()
    try:
        local_now = now.astimezone(tz)
    except (TypeError, ValueError, OSError):
        local_now = now.astimezone()
        tz = local_now.tzinfo
    try:
        parsed = datetime.strptime(
            f"{local_now.year} {month} {int(day)} {hms}",
            "%Y %b %d %H:%M:%S",
        ).replace(tzinfo=tz)
    except ValueError:
        return None
    if parsed > local_now + timedelta(minutes=5):
        try:
            parsed = parsed.replace(year=parsed.year - 1)
        except ValueError:
            return None
    return parsed


def _parse_iso_time(value: str) -> datetime | None:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        local = datetime.now().astimezone().tzinfo
        parsed = parsed.replace(tzinfo=local)
    return parsed


def _line_time(line: str, now: datetime) -> datetime | None:
    iso = _ISO.match(line)
    if iso:
        return _parse_iso_time(iso.group(1))
    classic = _SYSLOG.match(line)
    if classic:
        return _parse_syslog_time(classic.group(1), classic.group(2), classic.group(3), now)
    return None


def _journal_complete(proc: subprocess.CompletedProcess[str]) -> bool:
    if proc.returncode != 0:
        return False
    err = proc.stderr or ""
    return not any(marker in err for marker in _JOURNAL_INCOMPLETE)


def _failed_logins_from_journal() -> int | None:
    journalctl = shutil.which("journalctl")
    if journalctl is None:
        return None
    proc = _run(
        [
            journalctl,
            "-t",
            "sshd",
            "--since",
            "1 hour ago",
            "--no-pager",
            "-o",
            "short",
        ],
        timeout=20,
    )
    if proc is None or not _journal_complete(proc):
        return None
    count = 0
    for line in proc.stdout.splitlines():
        count += _count_login_line(line, require_sshd_tag=False)
    return count


def _failed_logins_from_auth_log(now: datetime) -> int | None:
    paths = ("/var/log/auth.log", "/var/log/auth.log.1")
    readable = 0
    count = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except FileNotFoundError:
            continue
        except OSError:
            continue
        readable += 1
        for line in lines:
            when = _line_time(line, now)
            if when is None or not _in_last_hour(when, now):
                continue
            count += _count_login_line(line, require_sshd_tag=True)
    if readable == 0:
        return None
    return count


def failed_logins_last_hour(now: datetime | None = None) -> int | None:
    if not sys.platform.startswith("linux"):
        return None
    current = now or datetime.now().astimezone()
    try:
        from_journal = _failed_logins_from_journal()
        if from_journal is not None:
            return from_journal
        return _failed_logins_from_auth_log(current)
    except Exception:
        print("collect_metrics: login log read failed", file=sys.stderr)
        return None


def build_check(psutil) -> dict:
    return {
        "timestamp": _utc_timestamp(),
        "host": _hostname(),
        "role": "unknown",
        "cpu_percent": _metric(lambda: psutil.cpu_percent(interval=1)),
        "memory_percent": _metric(lambda: psutil.virtual_memory().percent),
        "disk_percent": _metric(lambda: psutil.disk_usage("/").percent),
        "services": _service_map(),
        "failed_logins_last_hour": failed_logins_last_hour(),
        "anomaly_injected": None,
        "note": "Real metrics",
    }


def main() -> int:
    try:
        import psutil
    except ImportError:
        print(
            "psutil is not installed. From the repo root: python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    try:
        payload = {"checks": [build_check(psutil)]}
        json.dump(payload, sys.stdout, indent=2, allow_nan=False)
        sys.stdout.write("\n")
    except Exception:
        print("collect_metrics: could not write the JSON document", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
