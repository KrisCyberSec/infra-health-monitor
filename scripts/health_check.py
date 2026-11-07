#!/usr/bin/env python3
"""
Simulated health check script for the Infra Health Monitor lab.
Supports multiple hosts and injects realistic anomalies for documentation.
"""

import json
import random
from datetime import datetime, timezone

HOSTS = [
    {
        "name": "lab-server-01",
        "role": "web",
        "baseline": {"cpu": (15, 50), "memory": (30, 70), "disk": (40, 75)}
    },
    {
        "name": "lab-db-01",
        "role": "database",
        "baseline": {"cpu": (20, 60), "memory": (40, 80), "disk": (50, 80)}
    }
]

def generate_metrics(host_config, force_anomaly=None):
    name = host_config["name"]
    baseline = host_config["baseline"]

    cpu = random.randint(*baseline["cpu"])
    memory = random.randint(*baseline["memory"])
    disk = random.randint(*baseline["disk"])

    services = {
        "nginx": "running" if host_config["role"] == "web" else "not-installed",
        "sshd": "running",
        "postgres": "running" if host_config["role"] == "database" else "not-installed"
    }

    anomaly = force_anomaly
    if not anomaly and random.random() < 0.3:
        anomaly = random.choice(["high_cpu", "high_disk", "service_failed", "login_spike"])

    if anomaly == "high_cpu":
        cpu = random.randint(88, 97)
    elif anomaly == "high_disk":
        disk = random.randint(91, 98)
    elif anomaly == "service_failed":
        key = "postgres" if host_config["role"] == "database" else "nginx"
        services[key] = "failed"
    elif anomaly == "login_spike":
        failed_logins = random.randint(12, 25)
    else:
        failed_logins = random.randint(0, 4)

    if anomaly != "login_spike":
        failed_logins = random.randint(0, 4)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": name,
        "role": host_config["role"],
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "services": services,
        "failed_logins_last_hour": failed_logins,
        "anomaly_injected": anomaly,
        "note": "Simulated metrics for lab demonstration"
    }

def main():
    results = []
    for host in HOSTS:
        # Force one interesting anomaly on the first host for demos
        force = "high_disk" if host["name"] == "lab-server-01" else None
        results.append(generate_metrics(host, force_anomaly=force))

    print(json.dumps({"checks": results}, indent=2))

if __name__ == "__main__":
    main()
