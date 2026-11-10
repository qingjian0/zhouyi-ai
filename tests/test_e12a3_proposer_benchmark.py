import inspect
import unittest

from prototype.e12a3_proposer_benchmark import (
    FAMILIES, _budgeted_family_pools, _choose_on_gate, _make_world,
    run_benchmark, run_episode,
)


class E12A3ProposerBenchmarkTests(unittest.TestCase):
    def test_world_split_is_deterministic_and_disjoint(self):
        first = _make_world(11, "THRESHOLD")
        second = _make_world(11, "THRESHOLD")
        self.assertEqual(first, second)
        ids = [{row.observation_id for row in split} for split in first]
        self.assertFalse(ids[0] & ids[1])
        self.assertFalse(ids[0] & ids[2])
        self.assertFalse(ids[1] & ids[2])

    def test_proposer_pool_receives_support_only(self):
        support, gate, test = _make_world(3, "PAIRWISE_DIFFERENCE")
        self.assertTrue(_budgeted_family_pools(support, 3))
        self.assertEqual(
            list(inspect.signature(_budgeted_family_pools).parameters),
            ["support", "seed"],
        )
        self.assertTrue(gate and test)

    def test_gate_selector_has_no_locked_test_argument(self):
        self.assertEqual(
            list(inspect.signature(_choose_on_gate).parameters),
            ["candidates", "support", "gate"],
        )

    def test_episode_uses_same_proposal_slot_budget(self):
        result = run_episode(5, "THRESHOLD", budget=16)
        self.assertEqual(set(result["methods"]), set(FAMILIES))
        self.assertTrue(all(
            item["candidate_budget_used"] == 16
            for item in result["methods"].values()
        ))

    def test_benchmark_is_reproducible_and_reports_limitations(self):
        a = run_benchmark(seeds=2, start_seed=9, budget=16)
        b = run_benchmark(seeds=2, start_seed=9, budget=16)
        self.assertEqual(a, b)
        self.assertEqual(a["episode_count"], 4)
        self.assertEqual(set(a["aggregate"]), set(FAMILIES))
        self.assertTrue(a["limitations"])


if __name__ == "__main__":
    unittest.main()
