import unittest

from prototype.e02g_multienvironment import run_episode, wilson_interval


class E02GTests(unittest.TestCase):
    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(90, 100)
        self.assertLessEqual(low, 0.9)
        self.assertGreaterEqual(high, 0.9)

    def test_stable_relation_classified(self):
        result = run_episode(seed=17, regime="stable")
        self.assertEqual(result["classification"], "stable")
        self.assertEqual(set(result["candidate_members"]),
                         set(result["target_for_audit_only"]))

    def test_conditional_relation_classified(self):
        result = run_episode(seed=29, regime="conditional")
        self.assertEqual(result["classification"], "conditional")

    def test_sign_drift_classified(self):
        result = run_episode(seed=41, regime="drift")
        self.assertEqual(result["classification"], "drift")
        self.assertNotEqual(
            result["environments"][0]["direction"],
            result["environments"][1]["direction"],
        )

    def test_repeated_gates_are_reported(self):
        result = run_episode(seed=53, regime="stable", repeats=3)
        self.assertEqual(len(result["environments"][0]["repeat_accuracies"]), 3)
        self.assertEqual(result["environments"][0]["total"], 3 * 256)


if __name__ == "__main__":
    unittest.main()
