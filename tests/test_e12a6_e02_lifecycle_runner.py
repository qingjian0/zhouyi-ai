import unittest

from prototype.e02_rule_ood import make_episodes
from prototype.e12a6_e02_lifecycle_runner import run, run_episode


class E12A6E02LifecycleRunnerTests(unittest.TestCase):
    def test_default_run_accounts_for_all_27_rules(self):
        result = run(seed=17, support_size=6)
        self.assertEqual(result["episodes"], 27)
        self.assertEqual(result["hypothesis_class_size"], 27)
        self.assertEqual(result["accepted_primitive_count"],
                         result["mechanism_identification_coverage"] * 27)
        self.assertEqual(result["abstention_count"],
                         27 - result["accepted_primitive_count"])

    def test_ambiguous_mechanisms_are_not_accepted(self):
        episodes = make_episodes(seed=100, support_size=1)
        rows = [run_episode(ep, index) for index, ep in enumerate(episodes)]
        ambiguous = [row for row in rows if row["consistent_hypothesis_count"] > 1]
        self.assertTrue(ambiguous)
        for row in ambiguous:
            self.assertTrue(row["abstained"])
            self.assertIsNone(row["accepted_candidate_id"])
            self.assertEqual(row["candidate_states"].get("gate_validated", 0), 0)

    def test_accepted_candidates_have_gate_final_validation(self):
        episodes = make_episodes(seed=7, support_size=8)
        rows = [run_episode(ep, index) for index, ep in enumerate(episodes)]
        for row in rows:
            if row["accepted_candidate_id"] is not None:
                self.assertEqual(row["candidate_states"].get("gate_validated"), 1)

    def test_prediction_coverage_is_distinct_from_mechanism_identification(self):
        result = run(seed=100, support_size=1)
        self.assertGreaterEqual(result["query_prediction_coverage"],
                                result["mechanism_identification_coverage"])
        self.assertGreater(result["abstention_count"], 0)


if __name__ == "__main__":
    unittest.main()
