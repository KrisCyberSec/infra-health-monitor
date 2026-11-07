"""Tests for the rules engine. Run from the repo root:

    python3 -m unittest discover -s tests -v

These use only the standard library, so no install is needed.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import evaluate  # noqa: E402
import health_check  # noqa: E402

THRESHOLDS = evaluate.load_thresholds()


def make_check(**overrides):
    """A healthy host, with any fields overridden."""
    check = {
        "host": "test-host",
        "cpu_percent": 20,
        "memory_percent": 40,
        "disk_percent": 50,
        "services": {"sshd": "running", "nginx": "running"},
        "failed_logins_last_hour": 1,
    }
    check.update(overrides)
    return check


def components(alerts):
    return {a["component"]: a["severity"] for a in alerts}


class ThresholdTests(unittest.TestCase):
    def test_healthy_host_has_no_alerts(self):
        self.assertEqual(evaluate.evaluate(make_check(), THRESHOLDS), [])

    def test_top_of_normal_baseline_does_not_alert(self):
        # The highest values the simulated baselines produce must stay quiet.
        check = make_check(cpu_percent=60, memory_percent=80, disk_percent=80, failed_logins_last_hour=4)
        self.assertEqual(evaluate.evaluate(check, THRESHOLDS), [])

    def test_disk_warning_and_critical(self):
        self.assertEqual(components(evaluate.evaluate(make_check(disk_percent=87), THRESHOLDS)), {"disk_percent": "warning"})
        self.assertEqual(components(evaluate.evaluate(make_check(disk_percent=95), THRESHOLDS)), {"disk_percent": "critical"})

    def test_limits_are_inclusive(self):
        self.assertEqual(components(evaluate.evaluate(make_check(disk_percent=85), THRESHOLDS)), {"disk_percent": "warning"})
        self.assertEqual(components(evaluate.evaluate(make_check(disk_percent=84), THRESHOLDS)), {})

    def test_cpu_and_memory(self):
        alerts = evaluate.evaluate(make_check(cpu_percent=96, memory_percent=88), THRESHOLDS)
        self.assertEqual(components(alerts), {"cpu_percent": "critical", "memory_percent": "warning"})

    def test_failed_login_spike(self):
        self.assertEqual(components(evaluate.evaluate(make_check(failed_logins_last_hour=12), THRESHOLDS)), {"failed_logins_last_hour": "warning"})
        self.assertEqual(components(evaluate.evaluate(make_check(failed_logins_last_hour=30), THRESHOLDS)), {"failed_logins_last_hour": "critical"})

    def test_missing_readings_never_alert_or_crash(self):
        check = make_check(cpu_percent=None, memory_percent=None, disk_percent=None, failed_logins_last_hour=None)
        self.assertEqual(evaluate.evaluate(check, THRESHOLDS), [])


class ServiceTests(unittest.TestCase):
    def test_failed_service_is_critical(self):
        alerts = evaluate.evaluate(make_check(services={"nginx": "failed"}), THRESHOLDS)
        self.assertEqual(components(alerts), {"service:nginx": "critical"})
        self.assertIn("systemctl status nginx", alerts[0]["next_step"])

    def test_stopped_service_is_only_a_warning(self):
        alerts = evaluate.evaluate(make_check(services={"apache2": "inactive"}), THRESHOLDS)
        self.assertEqual(components(alerts), {"service:apache2": "warning"})

    def test_running_missing_and_unknown_do_not_alert(self):
        services = {"sshd": "running", "nginx": "not-installed", "apache2": "unknown"}
        self.assertEqual(evaluate.evaluate(make_check(services=services), THRESHOLDS), [])


class OrderingAndStatusTests(unittest.TestCase):
    def test_worst_alert_comes_first(self):
        alerts = evaluate.evaluate(make_check(cpu_percent=90, disk_percent=95), THRESHOLDS)
        self.assertEqual([a["severity"] for a in alerts], ["critical", "warning"])

    def test_overall_status(self):
        self.assertEqual(evaluate.overall_status([]), "OK")
        self.assertEqual(evaluate.overall_status([{"severity": "warning"}]), "WARNING")
        self.assertEqual(evaluate.overall_status([{"severity": "warning"}, {"severity": "critical"}]), "CRITICAL")

    def test_exit_codes(self):
        self.assertEqual(evaluate.EXIT_CODES, {"OK": 0, "WARNING": 1, "CRITICAL": 2})


class InjectedFailureTests(unittest.TestCase):
    """Use the simulator to inject each failure, and check the rules catch it.

    The simulator picks random values inside each failure's range, so every
    case runs many times to cover the range, not just one lucky number.
    """

    EXPECTED = {
        "high_cpu": lambda c: c == "cpu_percent",
        "high_disk": lambda c: c == "disk_percent",
        "service_failed": lambda c: c.startswith("service:"),
        "login_spike": lambda c: c == "failed_logins_last_hour",
    }

    def test_every_injected_failure_is_detected(self):
        for anomaly, matches in self.EXPECTED.items():
            for host in health_check.HOSTS:
                for _ in range(100):
                    check = health_check.generate_metrics(host, force_anomaly=anomaly)
                    alerts = evaluate.evaluate(check, THRESHOLDS)
                    with self.subTest(anomaly=anomaly, host=host["name"]):
                        self.assertTrue(any(matches(a["component"]) for a in alerts), f"{anomaly} was not detected: {check}")


if __name__ == "__main__":
    unittest.main()
