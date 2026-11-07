#!/usr/bin/env python3
"""Rules engine: turn raw metrics into alerts.

Input is one "check" dict, the shape printed by health_check.py and
collect_metrics.py. Output is a list of alert dicts, worst first.

The logic is deliberately plain. Each number is compared to a warn and a
critical limit from config/thresholds.json, and each service status is
mapped to a severity. There is no hidden state and no AI, so the same input
always gives the same alerts, and the rules can be unit tested.
"""

import json
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "thresholds.json"

SEVERITY_RANK = {"critical": 2, "warning": 1}
EXIT_CODES = {"OK": 0, "WARNING": 1, "CRITICAL": 2}  # same convention Nagios-style tools use

LABELS = {
    "cpu_percent": "CPU",
    "memory_percent": "Memory",
    "disk_percent": "Disk",
    "failed_logins_last_hour": "Failed logins in the last hour",
}

# What a sys admin would run first for each kind of alert.
NEXT_STEPS = {
    "cpu_percent": (
        "Find the busy process with `top` (press P to sort by CPU) or "
        "`ps aux --sort=-%cpu | head`. Then ask what changed: a deploy, a cron job, a runaway process."
    ),
    "memory_percent": (
        "Check memory and swap with `free -h`, find the biggest user with "
        "`ps aux --sort=-%mem | head`, and look for OOM kills with `dmesg | grep -i 'out of memory'`."
    ),
    "disk_percent": (
        "Confirm with `df -h`, then find what is large with "
        "`du -xh / --max-depth=2 | sort -h | tail`. Logs are the usual cause, so check /var/log and logrotate."
    ),
    "failed_logins_last_hour": (
        "Review the attempts with `journalctl -t sshd --since '1 hour ago'` and look at the source "
        "addresses. Key-only SSH and a firewall rule or fail2ban reduce this."
    ),
    "service": (
        "Run `systemctl status {svc}` and `journalctl -u {svc} -n 50 --no-pager` "
        "to find the cause before restarting it."
    ),
}


def load_thresholds(path=DEFAULT_CONFIG):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _level(value, limits):
    """Return 'critical', 'warning', or None. A missing reading never alerts."""
    if value is None:
        return None
    if value >= limits["critical"]:
        return "critical"
    if value >= limits["warn"]:
        return "warning"
    return None


def evaluate(check, thresholds):
    """Return the alerts for one host's check, worst first."""
    host = check.get("host", "unknown")
    alerts = []

    for metric, label in LABELS.items():
        limits = thresholds.get(metric)
        if not limits:
            continue
        value = check.get(metric)
        level = _level(value, limits)
        if level is None:
            continue
        limit = limits["critical"] if level == "critical" else limits["warn"]
        unit = "" if metric == "failed_logins_last_hour" else "%"
        alerts.append(
            {
                "host": host,
                "severity": level,
                "component": metric,
                "value": value,
                "threshold": limit,
                "message": f"{label}: {value}{unit} (limit {limit}{unit})",
                "next_step": NEXT_STEPS[metric],
            }
        )

    # failed = crashed, so it is critical. inactive = installed but stopped,
    # which may be intentional, so it is only a warning. running, not-installed
    # and unknown do not alert (unknown means we could not tell).
    service_severity = {"failed": "critical", "inactive": "warning"}
    for name, status in (check.get("services") or {}).items():
        level = service_severity.get(status)
        if level is None:
            continue
        alerts.append(
            {
                "host": host,
                "severity": level,
                "component": f"service:{name}",
                "value": status,
                "threshold": "running",
                "message": f"Service {name} is {status}",
                "next_step": NEXT_STEPS["service"].format(svc=name),
            }
        )

    alerts.sort(key=lambda a: -SEVERITY_RANK[a["severity"]])
    return alerts


def overall_status(alerts):
    """'CRITICAL' if any alert is critical, 'WARNING' if any exist, else 'OK'."""
    if any(a["severity"] == "critical" for a in alerts):
        return "CRITICAL"
    if alerts:
        return "WARNING"
    return "OK"
