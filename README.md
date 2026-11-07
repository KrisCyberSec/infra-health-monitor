# Infrastructure Health & Anomaly Monitor

A small monitoring tool for Linux hosts. It collects CPU, memory, disk, service status and failed SSH logins, compares them to thresholds, prints an alert that includes the commands to run next, logs every run, and exits with a status code that cron or a script can act on.

I built it to practice the monitoring side of systems administration: defining what "normal" looks like, spotting what isn't, and turning raw numbers into an alert someone can act on.

**History:** version 1 used an AI bot (a Grok Bot) to analyze the metrics. I no longer had access to that bot, so I rebuilt the analysis as plain rules in Python with unit tests (v2). A monitoring tool shouldn't depend on a chat service, and rules in code give the same answer every time. The v1 files are still in the repo, see [Original version](#original-version-v1).

## Quick start

Python 3 only. Simulated mode needs no install:

```bash
python3 scripts/run_monitor.py --simulate
```

Real metrics from the machine you run it on:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/run_monitor.py
```

Example output from a simulated run (values change every run):

```
== Infra monitor 2026-11-07T17:04:59.827668Z: CRITICAL ==
lab-server-01: CRITICAL
  [CRITICAL] Disk: 98% (limit 90%)
      next: Confirm with `df -h`, then find what is large with `du -xh / --max-depth=2 | sort -h | tail`. Logs are the usual cause, so check /var/log and logrotate.
lab-db-01: OK
```

Options: `--json` prints machine-readable results, `--config` points to a different thresholds file, `--history` and `--no-history` control the run log.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | WARNING |
| 2 | CRITICAL |
| 3 | Could not run (missing psutil, unreadable config) |

## How it works

1. **Collect.** `scripts/collect_metrics.py` reads real metrics with `psutil`. `scripts/health_check.py` generates simulated metrics for two hosts and can inject failures, which is what the tests and `--simulate` use.
2. **Evaluate.** `scripts/evaluate.py` compares each number to the warn and critical limits in `config/thresholds.json`, maps service states to a severity, and attaches next-step commands.
3. **Report.** `scripts/run_monitor.py` prints the report, appends the run to `logs/history.jsonl`, and exits with the worst status.

### Thresholds (`config/thresholds.json`)

| Metric | Warning | Critical |
|---|---|---|
| CPU % | 85 | 95 |
| Memory % | 85 | 95 |
| Disk % | 85 | 90 |
| Failed logins in the last hour | 10 | 25 |

Services: `failed` is critical, `inactive` (installed but stopped) is a warning, and `running`, `not-installed` and `unknown` do not alert. Limits are inclusive. A reading that is missing (`null`) never alerts.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

There are 14 tests, using only the standard library. They cover the threshold boundaries, service states, missing readings and alert ordering. They also use the simulator to inject a full disk, high CPU, a failed service and a login spike, 100 runs each, and check that every one is detected.

## Scheduling with cron

An example crontab line that runs a check every 5 minutes. I have not yet run this on a server.

```bash
mkdir -p logs
crontab -e
# add:
*/5 * * * * cd /path/to/infra-health-monitor && .venv/bin/python scripts/run_monitor.py >> logs/cron.log 2>&1
```

Run the command by hand first and confirm it works. `logs/` is gitignored.

## Collecting real metrics

`scripts/collect_metrics.py` prints one JSON document on stdout. It takes about one second, because the CPU sample uses `psutil.cpu_percent(interval=1)`.

Service status is one of `running`, `failed`, `inactive` (installed but stopped), `not-installed`, or `unknown` (no `systemctl`, such as on macOS). `failed_logins_last_hour` is `null` off Linux or when the logs can't be read, and `0` means the logs were read and had no matching line. A one-line `collect_metrics: percent metric failed` on stderr means that percent is `null` because the read failed.

If `python3 -m venv` on Ubuntu says the `venv` module is missing:

```bash
sudo apt-get install -y python3-venv
```

If `pip` tries to compile `psutil` and fails, install `build-essential` and `python3-dev`, then run the pip command again.

To check the collector's output shape (this does not check the numeric values):

```bash
python - <<'PY'
import json, subprocess, sys
raw = subprocess.check_output([sys.executable, "scripts/collect_metrics.py"])
data = json.loads(raw)
check = data["checks"][0]
assert list(check) == [
    "timestamp", "host", "role", "cpu_percent", "memory_percent",
    "disk_percent", "services", "failed_logins_last_hour",
    "anomaly_injected", "note",
]
assert check["timestamp"].endswith("Z")
assert check["role"] == "unknown"
assert check["note"] == "Real metrics"
assert check["anomaly_injected"] is None
for key in ("cpu_percent", "memory_percent", "disk_percent"):
    assert isinstance(check[key], int)
assert list(check["services"]) == ["sshd", "nginx", "apache2"]
if sys.platform == "darwin":
    assert check["failed_logins_last_hour"] is None
    assert set(check["services"].values()) == {"unknown"}
print("shape ok")
PY
```

On an Ubuntu server, compare the login count with the journal. The two numbers should match when the script used the journal.

```bash
sudo python scripts/collect_metrics.py
sudo journalctl -t sshd --since "1 hour ago" --no-pager -o cat \
  | grep -Eic 'Failed password for |Failed keyboard-interactive' || true
```

## Repository layout

| Path | What it is |
|---|---|
| `scripts/run_monitor.py` | Runs one monitoring pass: collect, evaluate, report, log |
| `scripts/evaluate.py` | The rules engine |
| `scripts/collect_metrics.py` | Collects real metrics with `psutil` |
| `scripts/health_check.py` | Generates simulated metrics and injects failures |
| `config/thresholds.json` | Warn and critical limits |
| `tests/test_evaluate.py` | Unit tests |
| `requirements.txt` | `psutil` (only needed for real metrics) |
| `bot-prompt.md`, `examples/`, `data/` | Version 1 files, see below |

## Limitations

- Real mode checks only the machine it runs on, not several hosts.
- A single reading over a limit alerts immediately. There is no "sustained for N runs" rule yet, so a brief spike can trigger an alert.
- There are no notifications. You read the report or act on the exit code.
- Failed-login counting reads sshd logs and works on Linux only. The service list in the collector is fixed to `sshd`, `nginx` and `apache2`.
- Simulated mode exists for demos and tests. Its numbers are random, with one exception: `--simulate` always injects a full disk on `lab-server-01`, so that mode always exits 2 (CRITICAL). `lab-db-01` is the host whose status changes from run to run. To see exit codes 0 or 1, use real mode or the unit tests.

Last verified 2026-11-07 on a Mac: all 14 tests passed, and four simulated runs all exited 2, with `lab-server-01` critical on disk each time and `lab-db-01` varying between CRITICAL, OK and WARNING.

## Roadmap

- [x] Collect real CPU, memory and disk metrics (`psutil`)
- [x] Move thresholds into a config file
- [x] Rules engine with unit tests
- [x] Run history log
- [ ] Run on a schedule on a real server (cron example above is untested)
- [ ] Alert only after several consecutive breaches, to cut noise
- [ ] Monitor more than one host
- [ ] Send alerts by email or Slack
- [ ] Add port and security checks

## Original version (v1)

Version 1 used simulated data analyzed by a Grok Bot. These files are kept as history:

- [`bot-prompt.md`](bot-prompt.md): the bot's standing description and routine prompt
- [`examples/bot-analysis-multi-host.md`](examples/bot-analysis-multi-host.md): the bot's analysis of a multi-host sample, ranking a failed Postgres service as critical and a 95% full disk as high
- [`examples/multi-host-alert.md`](examples/multi-host-alert.md), [`examples/sample-alert.md`](examples/sample-alert.md) and [`examples/sample-daily-report.md`](examples/sample-daily-report.md): sample alerts and a daily digest
- `data/`: sample metric snapshots, including injected problems
