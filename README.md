# Infrastructure Health & Anomaly Monitor

A sysadmin-focused lab. A Python script generates simulated health metrics for two servers, and an AI bot (a Grok Bot) compares them to baselines, flags anomalies, and writes short alerts with suggested next steps.

I built it to practice the monitoring side of systems administration: defining what "normal" looks like, spotting what isn't, and turning raw numbers into an alert someone can act on.

## What's in the repo

| Path | What it is |
|---|---|
| `scripts/health_check.py` | Generates simulated metrics for two hosts and prints JSON |
| `data/sample-metrics.json`, `data/multi-host-sample.json` | Sample metric snapshots, including injected problems |
| `bot-prompt.md` | The bot's standing description and routine prompt |
| `examples/` | Sample alerts and a daily report, plus a real bot analysis of the multi-host sample |

## How it works

1. **The script** simulates two hosts, `lab-server-01` (web) and `lab-db-01` (database). Each has its own baseline range for CPU, memory, and disk. Metrics are random within those ranges.
2. **Anomalies are injected** on purpose: high CPU, high disk, a failed service, or a spike in failed logins. `lab-server-01` is forced to have a high-disk anomaly on every run so there is always something to catch, and `lab-db-01` gets a random anomaly about 30% of the time.
3. **The bot** gets that JSON, compares it to the baselines in `bot-prompt.md`, and returns a severity, the affected component, current value vs baseline, and a suggested next step.

## Run it

Requires Python 3. There are no other dependencies.

```bash
python scripts/health_check.py
```

Example output from one run (values change every run):

```json
{
  "checks": [
    {
      "timestamp": "2026-11-07T15:14:44.976643Z",
      "host": "lab-server-01",
      "role": "web",
      "cpu_percent": 16,
      "memory_percent": 43,
      "disk_percent": 95,
      "services": {
        "nginx": "running",
        "sshd": "running",
        "postgres": "not-installed"
      },
      "failed_logins_last_hour": 4,
      "anomaly_injected": "high_disk",
      "note": "Simulated metrics for lab demonstration"
    },
    {
      "timestamp": "2026-11-07T15:14:44.976901Z",
      "host": "lab-db-01",
      "role": "database",
      "cpu_percent": 48,
      "memory_percent": 67,
      "disk_percent": 54,
      "services": {
        "nginx": "not-installed",
        "sshd": "running",
        "postgres": "running"
      },
      "failed_logins_last_hour": 3,
      "anomaly_injected": null,
      "note": "Simulated metrics for lab demonstration"
    }
  ]
}
```

Then give the JSON to the bot using the instructions in [`bot-prompt.md`](bot-prompt.md).

## Example results

- [`examples/bot-analysis-multi-host.md`](examples/bot-analysis-multi-host.md): the bot's analysis of the multi-host sample. It ranks a failed Postgres service as critical and a 95% full disk as high, suggests next commands (`systemctl status`, `journalctl`, `du`), and recommends the fix order.
- [`examples/multi-host-alert.md`](examples/multi-host-alert.md) and [`examples/sample-alert.md`](examples/sample-alert.md): sample alerts.
- [`examples/sample-daily-report.md`](examples/sample-daily-report.md): sample daily digest.

## Why simulated data?

Simulated metrics let me inject known problems (full disk, failed service, login spike) and check that the analysis catches them. That makes the project self-contained and repeatable with no live servers.

## Limitations

- All metrics are simulated. Nothing is collected from a real machine.
- Alert thresholds live in the bot prompt, not in code or a config file.
- The script does not store history, run on a schedule, or send notifications.
- The bot is run by hand against the script's output.

## Roadmap

- [ ] Collect real CPU, memory, and disk metrics from my own machine (`psutil`)
- [ ] Move thresholds into a config file
- [ ] Schedule runs with cron or a systemd timer
- [ ] Monitor more than two hosts
- [ ] Send alerts by email or Slack
- [ ] Add security checks such as failed logins and open ports
