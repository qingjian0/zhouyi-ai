import unittest

from prototype.tx02_identifiability import audit_episode
from prototype.tx02_multistate_benchmark import episode_to_dict, make_episode


class TX02IdentifiabilityTests(unittest.TestCase):
    def test_rule_ambiguity_and_query_ambiguity_are_distinct(self):
        payload = {
            "cardinality": 3,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0], [0, 1, 1]],
            "queries": [[0, 2]],
            "candidates": [[2, 0, 1]],
            "targets": [0],
        }
        result = audit_episode(payload)
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["consistent_hypotheses"], 1)
        self.assertFalse(result["rule_hypothesis_identifiable"])
        self.assertTrue(result["queries"][0]["answer_identifiable"])
        self.assertEqual(result["queries"][0]["candidate_posterior"], [1.0, 0.0, 0.0])

    def test_ambiguous_query_has_fractional_posterior(self):
        payload = {
            "cardinality": 2,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0]],
            "queries": [[0, 1]],
            "candidates": [[1, 0]],
        }
        result = audit_episode(payload)
        self.assertEqual(result["consistent_hypotheses"], 4)
        self.assertFalse(result["queries"][0]["answer_identifiable"])
        self.assertAlmostEqual(result["queries"][0]["bayes_optimal_accuracy"], 0.5)
        self.assertEqual(result["queries"][0]["candidate_hypothesis_counts"], [2, 2])

    def test_candidate_order_is_respected(self):
        payload = {
            "cardinality": 3,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0], [0, 1, 1]],
            "queries": [[0, 2]],
            "candidates": [[0, 1, 2]],
        }
        result = audit_episode(payload)
        self.assertEqual(result["queries"][0]["candidate_posterior"], [0.0, 0.0, 1.0])

    def test_targets_are_ignored_by_audit(self):
        payload = {
            "cardinality": 2,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0]],
            "queries": [[0, 1]],
            "candidates": [[0, 1]],
            "targets": [0],
        }
        first = audit_episode(payload)
        payload["targets"] = [1]
        second = audit_episode(payload)
        self.assertEqual(first, second)

    def test_permuted_track_enumerates_bijections(self):
        payload = {
            "cardinality": 2,
            "symbol_mapping": "permuted",
            "support": [[1, 1, 1]],
            "queries": [[1, 0]],
            "candidates": [[0, 1]],
        }
        result = audit_episode(payload)
        self.assertEqual(result["hypothesis_space_size"], 8 * 2)
        self.assertGreater(result["consistent_hypotheses"], 0)

    def test_rejects_oversized_exact_search(self):
        payload = {
            "cardinality": 5,
            "symbol_mapping": "permuted",
            "support": [[0, 0, 0]],
            "queries": [[0, 1]],
            "candidates": [[0, 1, 2, 3, 4]],
        }
        with self.assertRaises(ValueError):
            audit_episode(payload, max_hypotheses=100)

    def test_inconsistent_support_is_reported(self):
        payload = {
            "cardinality": 2,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0], [0, 0, 1]],
            "queries": [[0, 1]],
            "candidates": [[0, 1]],
        }
        result = audit_episode(payload)
        self.assertEqual(result["status"], "inconsistent")
        self.assertEqual(result["consistent_hypotheses"], 0)

    def test_generator_ground_truth_is_never_excluded(self):
        for k in (2, 3, 4, 5):
            for mapping in ("canonical", "permuted"):
                episode = make_episode(k, 1000 + k, support_size=2, query_count=2,
                                       symbol_mapping=mapping)
                result = audit_episode(episode_to_dict(episode))
                self.assertEqual(result["status"], "ok")
                for qi, target in enumerate(episode.targets):
                    self.assertGreater(
                        result["queries"][qi]["candidate_hypothesis_counts"][target], 0
                    )
                    self.assertAlmostEqual(
                        sum(result["queries"][qi]["candidate_posterior"]), 1.0
                    )

    def test_invalid_candidate_row_is_rejected(self):
        payload = {
            "cardinality": 2,
            "symbol_mapping": "canonical",
            "support": [[0, 0, 0]],
            "queries": [[0, 1]],
            "candidates": [[0, 0]],
        }
        with self.assertRaises(ValueError):
            audit_episode(payload)


if __name__ == "__main__":
    unittest.main()
