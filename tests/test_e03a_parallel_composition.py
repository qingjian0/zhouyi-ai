import unittest

from prototype.e03a_parallel_composition import run_episode


class E03AParallelCompositionTests(unittest.TestCase):
    def test_coordinator_respects_shared_feature_budget(self):
        result = run_episode(1501)
        self.assertLessEqual(result["coordinated"]["union_feature_count"], 5)

    def test_targets_require_non_adjacent_composition(self):
        result = run_episode(1502)
        targets = result["target_members_for_audit_only"]
        self.assertTrue(any(any(b - a > 1 for a, b in zip(t, t[1:])) for t in targets))

    def test_all_heads_are_evaluated_on_locked_tests(self):
        result = run_episode(1503)
        self.assertEqual(len(result["coordinated"]["per_head_test_accuracy"]), 3)
        self.assertEqual(len(result["independent_gate_selection"]["per_head_test_accuracy"]), 3)


if __name__ == "__main__":
    unittest.main()
