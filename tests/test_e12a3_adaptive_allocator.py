import math
import unittest

from prototype.e12a3_adaptive_allocator import (
    UCB1Allocator,
    allocate_equal_budget,
    replay_ucb1,
)


class E12A3AdaptiveAllocatorTests(unittest.TestCase):
    def test_equal_control_conserves_budget(self):
        allocation = allocate_equal_budget(("C", "A", "B"), 11)
        self.assertEqual(allocation, {"A": 4, "B": 4, "C": 3})
        self.assertEqual(sum(allocation.values()), 11)

    def test_ucb_respects_exploration_floor_and_global_budget(self):
        result = replay_ucb1(
            {"STAT": (0.2,) * 8, "RELATIONAL": (0.8,) * 8, "RANDOM": (0.1,) * 8},
            total_budget=12,
            exploration_floor=2,
        )
        self.assertEqual(result["status"], "FROZEN")
        self.assertEqual(result["used_budget"], 12)
        self.assertEqual(result["remaining_budget"], 0)
        self.assertEqual(sum(result["allocations"].values()), 12)
        self.assertTrue(all(count >= 2 for count in result["allocations"].values()))

    def test_ucb_shifts_budget_toward_better_reward_after_exploration(self):
        result = replay_ucb1(
            {"STAT": (0.2,) * 20, "RELATIONAL": (0.9,) * 20, "RANDOM": (0.1,) * 20},
            total_budget=18,
        )
        counts = result["allocations"]
        self.assertGreater(counts["RELATIONAL"], counts["STAT"])
        self.assertGreater(counts["RELATIONAL"], counts["RANDOM"])

    def test_tie_breaking_is_deterministic(self):
        first = replay_ucb1(
            {"Z": (0.5,) * 10, "A": (0.5,) * 10, "M": (0.5,) * 10},
            total_budget=12,
        )
        second = replay_ucb1(
            {"M": (0.5,) * 10, "Z": (0.5,) * 10, "A": (0.5,) * 10},
            total_budget=12,
        )
        self.assertEqual(first, second)

    def test_requires_reward_before_next_allocation(self):
        allocator = UCB1Allocator(("A", "B"), 4)
        allocator.next_family()
        with self.assertRaises(RuntimeError):
            allocator.next_family()

    def test_reward_requires_pending_allocation(self):
        allocator = UCB1Allocator(("A", "B"), 4)
        with self.assertRaises(RuntimeError):
            allocator.record_gate_dev_reward(0.5, "g1")

    def test_reward_validation_rejects_bool_string_nan_and_out_of_range(self):
        for bad in (True, "0.5", float("nan"), float("inf"), -0.1, 1.1):
            allocator = UCB1Allocator(("A", "B"), 4)
            allocator.next_family()
            with self.subTest(bad=bad):
                with self.assertRaises((TypeError, ValueError)):
                    allocator.record_gate_dev_reward(bad, "g1")

    def test_evidence_ids_must_be_unique(self):
        allocator = UCB1Allocator(("A", "B"), 4)
        allocator.next_family()
        allocator.record_gate_dev_reward(0.5, "g1")
        allocator.next_family()
        with self.assertRaises(ValueError):
            allocator.record_gate_dev_reward(0.5, "g1")

    def test_freeze_requires_no_pending_reward_and_is_irreversible(self):
        allocator = UCB1Allocator(("A", "B"), 4)
        allocator.next_family()
        with self.assertRaises(RuntimeError):
            allocator.freeze()
        allocator.record_gate_dev_reward(0.5, "g1")
        frozen = allocator.freeze()
        self.assertEqual(frozen["status"], "FROZEN")
        with self.assertRaises(RuntimeError):
            allocator.next_family()
        with self.assertRaises(RuntimeError):
            allocator.record_gate_dev_reward(0.5, "g2")

    def test_budget_must_cover_exploration_floor(self):
        with self.assertRaises(ValueError):
            UCB1Allocator(("A", "B", "C"), 2, exploration_floor=1)

    def test_configuration_validation(self):
        with self.assertRaises(TypeError):
            UCB1Allocator(("A", "B"), True)
        with self.assertRaises(ValueError):
            UCB1Allocator(("A", "B"), 4, exploration_constant=-1)
        with self.assertRaises(ValueError):
            UCB1Allocator(("A", "B"), 4, exploration_constant=math.inf)
        with self.assertRaises(ValueError):
            UCB1Allocator(("A", "A"), 4)

    def test_reward_trace_is_append_ordered_and_auditable(self):
        result = replay_ucb1(
            {"A": (0.2, 0.4, 0.6, 0.5, 0.3, 0.7),
             "B": (0.8, 0.7, 0.9, 0.6, 0.85, 0.75)},
            total_budget=6,
        )
        trace = result["trace"]
        self.assertEqual([item["step"] for item in trace], list(range(1, 7)))
        self.assertEqual(len({item["evidence_id"] for item in trace}), 6)
        expected_reward = sum(
            {"A": (0.2, 0.4, 0.6, 0.5, 0.3, 0.7),
             "B": (0.8, 0.7, 0.9, 0.6, 0.85, 0.75)}[family][index]
            for family, count in result["allocations"].items()
            for index in range(count)
        )
        self.assertAlmostEqual(
            sum(item["reward"] for item in trace), expected_reward
        )


if __name__ == "__main__":
    unittest.main()
