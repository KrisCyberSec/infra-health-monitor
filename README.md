# Infrastructure Health & Anomaly Monitor

AIOps-style project demonstrating a Grok Bot that monitors system health, detects anomalies, and generates actionable alerts/reports using simulated data.

It shows proactive monitoring, noise reduction, scripting, and AI agent integration.

## Goals
- Build a persistent Grok Bot that acts as an infrastructure health monitor
- Use simulated metrics so the project is fully self-contained
- Generate clear alerts and daily reports
- Maintain historical baselines in bot memory

## Steps

1. **Review the repository structure** (this repo)
   - `scripts/health_check.py` — generates simulated system metrics
   - `data/` — sample metric files and baselines
   - `examples/` — sample alert and daily report outputs
   - `bot-prompt.md` — exact Grok Bot description and routine prompts

2. **Run the sample health check**
   ```bash
   python scripts/health_check.py
   ```
   This produces JSON output with CPU, memory, disk, services, and simulated anomalies.

3. **Create the Grok Bot**
   - Name: `Infra Health Monitor`
   - Use the description and instructions from `bot-prompt.md`
   - The bot will keep memory of baselines and past incidents

4. **Set up a routine**
   - Schedule the bot to check metrics periodically (or on demand)
   - Instruct it to compare against baselines, flag anomalies, and produce a concise report

5. **Document results**
   - Capture sample alerts and reports (see `examples/`)
   - Update the README with real outputs from your runs
   - Note what the bot remembered over multiple runs

6. **Optional extensions**
   - Point the bot at real systems (SSH, APIs, Prometheus, etc.)
   - Add security checks
   - Integrate with Slack or email for alerts

## Why Simulated Data?
Simulated metrics let you fully demonstrate the bot’s reasoning, anomaly detection, and reporting without needing live infrastructure. You can also inject known problems (high CPU, disk full, failed service) to show clear before/after examples.

## Next Steps
- Customize thresholds in the bot prompt or script
- Add more realistic metrics or log samples
- Expand to multi-host monitoring
