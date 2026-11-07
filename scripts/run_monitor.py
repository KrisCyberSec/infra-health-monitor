#!/usr/bin/env python3
"""Collect metrics, apply the rules, print a report, and log the run.

    python scripts/run_monitor.py             # real metrics from this machine
    python scripts/run_monitor.py --simulate  # simulated hosts, with a failure injected

Exit code follows the usual monitoring convention, so cron or a wrapper
script can react to it: 0 = OK, 1 = WARNING, 2 = CRITICAL, 3 = could not run.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # lets this script import its siblings

import evaluate  # noqa: E402

DEFAULT_HISTORY = HERE.parent / "logs" / "history.jsonl"


def collect_real():
    import psutil

    import collect_metrics

    return [collect_metrics.build_check(psutil)]


def collect_simulated():
    import health_check

    checks = []
    for host in health_check.HOSTS:
        # Same demo as health_check.py: always inject a full disk on the web host.
        force = "high_disk" if host["name"] == "lab-server-01" else None
        checks.append(health_check.generate_metrics(host, force_anomaly=force))
    return checks


def build_results(checks, thresholds):
    results = []
    for check in checks:
        alerts = evaluate.evaluate(check, thresholds)
        results.append({"host": check.get("host", "unknown"), "status": evaluate.overall_status(alerts), "alerts": alerts})
    return results


def worst(results):
    order = ["OK", "WARNING", "CRITICAL"]
    return max((r["status"] for r in results), key=order.index, default="OK")


def format_report(results, overall, timestamp):
    lines = [f"== Infra monitor {timestamp}: {overall} =="]
    for result in results:
        lines.append(f"{result['host']}: {result['status']}")
        for alert in result["alerts"]:
            lines.append(f"  [{alert['severity'].upper()}] {alert['message']}")
            lines.append(f"      next: {alert['next_step']}")
    return "\n".join(lines)


def append_history(path, timestamp, overall, results):
    """One JSON line per run, so trends can be read back later (grep, jq, python)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": timestamp,
        "overall": overall,
        "hosts": [
            {
                "host": r["host"],
                "status": r["status"],
                "alerts": [{"component": a["component"], "severity": a["severity"], "value": a["value"]} for a in r["alerts"]],
            }
            for r in results
        ],
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one monitoring pass.")
    parser.add_argument("--simulate", action="store_true", help="use simulated hosts instead of this machine")
    parser.add_argument("--config", default=str(evaluate.DEFAULT_CONFIG), help="path to thresholds.json")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY), help="path to the history log (JSON lines)")
    parser.add_argument("--no-history", action="store_true", help="do not write to the history log")
    parser.add_argument("--json", action="store_true", help="print results as JSON instead of text")
    args = parser.parse_args(argv)

    try:
        thresholds = evaluate.load_thresholds(args.config)
        checks = collect_simulated() if args.simulate else collect_real()
    except ImportError:
        print("psutil is not installed. Run: python3 -m pip install -r requirements.txt", file=sys.stderr)
        return 3
    except (OSError, ValueError) as exc:
        print(f"run_monitor: could not start: {exc}", file=sys.stderr)
        return 3

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    results = build_results(checks, thresholds)
    overall = worst(results)

    if args.json:
        print(json.dumps({"timestamp": timestamp, "overall": overall, "hosts": results}, indent=2))
    else:
        print(format_report(results, overall, timestamp))

    if not args.no_history:
        try:
            append_history(Path(args.history), timestamp, overall, results)
        except OSError as exc:
            print(f"run_monitor: could not write history: {exc}", file=sys.stderr)

    return evaluate.EXIT_CODES[overall]


if __name__ == "__main__":
    sys.exit(main())
