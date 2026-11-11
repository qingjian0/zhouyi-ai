import unittest

from prototype.e10c_drift_representability import run


class E10CDriftRepresentabilityTests(unittest.TestCase):
    def test_stationary_fit_cannot_represent_two_drift_epochs(self):
        result = run()
        self.assertTrue(result["checks"]["combined_drift_is_inconsistent"])
        self.assertTrue(result["checks"]["epoch_1_is_identifiable"])
        self.assertTrue(result["checks"]["epoch_2_is_identifiable"])
        self.assertTrue(result["checks"]["no_drift_control_remains_identifiable"])


if __name__ == "__main__":
    unittest.main()
