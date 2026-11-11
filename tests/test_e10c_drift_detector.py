import unittest

from prototype.e10c_drift_detector import BernoulliCUSUM
from prototype.e10c_drift_detection_experiment import run


class E10CDriftDetectorTests(unittest.TestCase):
    def test_rejects_invalid_configuration_and_non_boolean_signal(self):
        with self.assertRaises(ValueError):
            BernoulliCUSUM(baseline_rate=0.4, alternative_rate=0.2)
        with self.assertRaises(TypeError):
            BernoulliCUSUM().update(1)

    def test_persistent_error_increase_triggers_alarm(self):
        detector = BernoulliCUSUM(threshold=8.0)
        alarms = detector.run([False] * 100 + [True] * 20)
        self.assertTrue(alarms)
        self.assertGreater(alarms[0].index, 100)
        self.assertLessEqual(alarms[0].index, 120)

    def test_stationary_control_and_change_scenarios_are_reported(self):
        result = run(seeds=10, start_seed=3100)
        self.assertEqual(
            set(result["scenarios"]),
            {"stationary", "abrupt", "gradual", "noise_burst"},
        )
        self.assertIsNotNone(result["scenarios"]["stationary"]["alarm_run_rate"])
        self.assertIsNotNone(result["scenarios"]["abrupt"]["detection_rate"])
        self.assertIsNotNone(result["scenarios"]["gradual"]["detection_rate"])
        self.assertIsNotNone(result["scenarios"]["noise_burst"]["alarm_run_rate"])


if __name__ == "__main__":
    unittest.main()
