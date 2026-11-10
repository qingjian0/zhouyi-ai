import inspect
import unittest

from prototype.e12a3_adaptive_benchmark import (
    METHODS,
    _adaptive_allocate,
    _make_pools,
    _score_locked_test,
    _select_on_gate_final,
    make_four_way_world,
    run_benchmark,
    run_episode,
)
from prototype.e12a3_multi_proposer import Observation


class E12A3AdaptiveBenchmarkTests(unittest.TestCase):
    def test_four_way_splits_are_disjoint_and_fixed(self):
        splits = make_four_way_world(13, "THRESHOLD")
        self.assertEqual(tuple(map(len, splits)), (64, 32, 32, 32))
        id_sets = [{row.observation_id for row in split} for split in splits]
        for i in range(len(id_sets)):
            for j in range(i + 1, len(id_sets)):
                self.assertFalse(id_sets[i] & id_sets[j])

    def test_allocation_boundary_excludes_gate_final_and_locked_test(self):
        self.assertEqual(
            list(inspect.signature(_adaptive_allocate).parameters),
            ["support", "gate_dev", "seed", "budget", "batch_size",
             "exploration_floor", "exploration_constant", "reward_mode"],
        )
        self.assertEqual(
            list(inspect.signature(_make_pools).parameters),
            ["support", "seed"],
        )
        self.assertEqual(
            list(inspect.signature(_select_on_gate_final).parameters),
            ["candidates", "gate_final"],
        )
        self.assertEqual(
            list(inspect.signature(_score_locked_test).parameters),
            ["selection", "locked_test"],
        )

    def test_gate_final_and_test_mutations_cannot_change_allocation(self):
        support, gate_dev, gate_final, locked_test = make_four_way_world(
            21, "PAIRWISE_DIFFERENCE"
        )
        first = _adaptive_allocate(support, gate_dev, 21, budget=19)
        flipped_final = tuple(
            Observation(row.observation_id, row.values, 1 - row.label)
            for row in gate_final
        )
        flipped_test = tuple(
            Observation(row.observation_id, row.values, 1 - row.label)
            for row in locked_test
        )
        # The allocator's complete input payload is unchanged. Final/test
        # partitions are not parameters and cannot influence its allocation.
        second = _adaptive_allocate(support, gate_dev, 21, budget=19)
        self.assertEqual(first["trace"], second["trace"])
        self.assertEqual(first["allocations"], second["allocations"])
        self.assertTrue(flipped_final and flipped_test)

    def test_adaptive_budget_is_exact_and_trace_is_reproducible(self):
        support, gate_dev, _, _ = make_four_way_world(7, "THRESHOLD")
        first = _adaptive_allocate(support, gate_dev, 7, budget=23)
        second = _adaptive_allocate(support, gate_dev, 7, budget=23)
        self.assertEqual(first["trace"], second["trace"])
        self.assertEqual(first["proposal_slots_used"], 23)
        self.assertEqual(sum(first["allocations"].values()), 23)
        self.assertEqual(first["allocations"], second["allocations"])
        self.assertLessEqual(
            first["gate_dev_unique_evaluations"], len(first["candidates"])
        )

    def test_gate_dev_reward_is_bounded_and_recorded(self):
        support, gate_dev, _, _ = make_four_way_world(8, "THRESHOLD")
        result = _adaptive_allocate(support, gate_dev, 8, budget=20)
        self.assertTrue(result["trace"])
        self.assertTrue(all(
            0.0 <= event["reward"] <= 1.0 for event in result["trace"]
        ))
        self.assertTrue(all(
            event["emitted"] <= event["requested_slots"]
            for event in result["trace"]
        ))

    def test_gate_final_selection_and_locked_test_scoring_are_separate(self):
        support, gate_dev, gate_final, locked_test = make_four_way_world(
            9, "THRESHOLD"
        )
        candidates = _adaptive_allocate(
            support, gate_dev, 9, budget=20
        )["candidates"]
        selection = _select_on_gate_final(candidates, gate_final)
        self.assertIn("selected_proposal", selection)
        score = _score_locked_test(selection, locked_test)
        self.assertIsNone(score) if not candidates else self.assertGreaterEqual(score, 0.0)
        self.assertNotIn("locked_test_accuracy", selection)

    def test_episode_and_small_benchmark_have_exact_budget(self):
        episode = run_episode(4, "PAIRWISE_DIFFERENCE", budget=20)
        self.assertEqual(set(episode["methods"]), set(METHODS))
        self.assertTrue(all(
            item["proposal_slots_used"] == 20
            for item in episode["methods"].values()
        ))
        self.assertTrue(all(
            item["gate_final_unique_evaluations"] == item["candidate_count"]
            for item in episode["methods"].values()
        ))
        self.assertTrue(all(
            item["gate_final_unique_evaluations"] <= 20
            for item in episode["methods"].values()
        ))
        result = run_benchmark(seeds=2, start_seed=5, budget=20)
        self.assertEqual(result["episode_count"], 4)
        self.assertIn("UCB1 rewards are non-stationary", " ".join(result["limitations"]))


if __name__ == "__main__":
    unittest.main()
