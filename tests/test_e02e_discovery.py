import unittest

from prototype.e02e_discovery import (
    accuracy, discover, make_dataset, propose_candidates,
)


class E02EDiscoveryTests(unittest.TestCase):
    def test_hidden_member_set_is_not_passed_to_candidate_generator(self):
        rows, hidden = make_dataset(seed=31, count=600)
        candidates = propose_candidates(rows, top_k=1)
        self.assertEqual(set(candidates[0].members), set(hidden))

    def test_candidate_ranking_recovers_unknown_three_way_relation(self):
        rows, hidden = make_dataset(seed=44, count=700, noise=0.01)
        winner = propose_candidates(rows, top_k=1)[0]
        self.assertEqual(set(winner.members), set(hidden))
        self.assertGreater(accuracy(rows, winner), 0.95)

    def test_independent_gate_and_test_sets_are_used(self):
        result = discover(seed=9, train_n=512, gate_n=256, test_n=256)
        self.assertEqual(set(result["discovered_members"]),
                         set(result["hidden_target_for_audit_only"]))
        self.assertEqual(len(result["ranked_candidates"]), 16)
        self.assertIn("counterexample_count", result)
        self.assertIn("test_accuracy", result)

    def test_noise_is_recorded_as_counterexample_evidence(self):
        result = discover(seed=12, train_n=512, gate_n=256, test_n=256,
                          noise=0.08)
        self.assertGreater(result["counterexample_count"], 0)

    def test_dataset_is_reproducible_and_seed_sensitive(self):
        a, _ = make_dataset(seed=88, count=30)
        b, _ = make_dataset(seed=88, count=30)
        c, _ = make_dataset(seed=89, count=30)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_rejects_invalid_noise(self):
        with self.assertRaises(ValueError):
            make_dataset(seed=1, count=20, noise=0.5)


if __name__ == "__main__":
    unittest.main()
