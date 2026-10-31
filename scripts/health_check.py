#!/usr/bin/env python3
"""
Simple simulated health check script for the Infra Health Monitor lab.
Outputs JSON metrics. Can be extended to call real system commands later.
"""

import json
import random
from datetime import datetime

def generate_metrics():
    # Simulate mostly healthy system with occasional anomalies
    cpu = random.randint(10, 45)
    memory = random.randint(30, 70)
    disk = random.randint(40, 75)
    
    # Occasionally inject an anomaly for demo purposes
    if random.random() < 0.25:
        anomaly = random.choice(["cpu", "disk", "service"])
        if anomaly == "cpu":
            cpu = random.randint(88, 98)
        elif anomaly == "disk":
            disk = random.randint(92, 99)
        # service failure is handled below
    else:
        anomaly = None

    services = {
        "nginx": "running",
        "sshd": "running",
        "postgres": "running"
    }
    if anomaly == "service" or random.random() < 0.1:
        services["postgres"] = "failed"

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "host": "lab-server-01",
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "services": services,
        "failed_logins_last_hour": random.randint(0, 3),
        "note": "Simulated metrics for lab demonstration"
    }

if __name__ == "__main__":
    print(json.dumps(generate_metrics(), indent=2))
