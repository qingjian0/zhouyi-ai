import unittest

from prototype.e12a3_adaptive_allocator import UCB1Allocator


class E12A3AdaptiveAllocatorTests(unittest.TestCase):
    def test_exploration_floor_visits_every_family_before_adaptation(self):
        allocator = UCB1Allocator(
            ["STAT", "RELATIONAL", "RANDOM"],
            total_budget=12,
            batch_size=2,
            exploration_floor=1,
        )
        visited = []
        for reward in (0.1, 0.2, 0.3):
            family = allocator.choose_next_family()
            visited.append(family)
            allocator.observe_batch(family, reward)
        self.assertEqual(visited, ["RANDOM", "RELATIONAL", "STAT"])

    def test_ucb_prefers_higher_reward_after_floor(self):
        allocator = UCB1Allocator(
            ["A", "B"], total_budget=20, batch_size=2,
            exploration_floor=1, exploration_constant=0.1,
        )
        first = allocator.choose_next_family()
        allocator.observe_batch(first, 0.9 if first == "A" else 0.1)
        second = allocator.choose_next_family()
        allocator.observe_batch(second, 0.9 if second == "A" else 0.1)
        self.assertEqual(allocator.choose_next_family(), "A")

    def test_ucb_ties_break_by_stable_family_id(self):
        allocator = UCB1Allocator(
            ["B", "A"], total_budget=3, batch_size=1,
            exploration_floor=1, exploration_constant=0.0,
        )
        for expected in ("A", "B"):
            family = allocator.choose_next_family()
            self.assertEqual(family, expected)
            allocator.observe_batch(family, 0.5)
        self.assertEqual(allocator.choose_next_family(), "A")

    def test_budget_is_conserved_with_final_partial_batch(self):
        allocator = UCB1Allocator(
            ["A", "B"], total_budget=5, batch_size=2,
            exploration_floor=1,
        )
        used = 0
        while True:
            family = allocator.choose_next_family()
            if family is None:
                break
            pending_family, slots = allocator.pending
            event = allocator.observe_batch(pending_family, 0.0)
            used += event.slots
            self.assertEqual(slots, event.slots)
        self.assertEqual(used, 5)
        self.assertEqual(sum(allocator.allocations.values()), 5)
        self.assertEqual(allocator.remaining_budget, 0)

    def test_cannot_choose_twice_without_reward(self):
        allocator = UCB1Allocator(["A", "B"], total_budget=4, batch_size=1)
        allocator.choose_next_family()
        with self.assertRaises(RuntimeError):
            allocator.choose_next_family()

    def test_reward_must_match_pending_family(self):
        allocator = UCB1Allocator(["A", "B"], total_budget=4, batch_size=1)
        family = allocator.choose_next_family()
        wrong = "B" if family == "A" else "A"
        with self.assertRaises(ValueError):
            allocator.observe_batch(wrong, 0.5)

    def test_non_finite_reward_is_rejected_without_consuming_budget(self):
        allocator = UCB1Allocator(["A"], total_budget=2, batch_size=1)
        family = allocator.choose_next_family()
        with self.assertRaises(ValueError):
            allocator.observe_batch(family, float("nan"))
        self.assertEqual(allocator.remaining_budget, 2)
        self.assertEqual(allocator.pulls[family], 0)

    def test_exploration_floor_must_fit_budget(self):
        with self.assertRaises(ValueError):
            UCB1Allocator(["A", "B", "C"], total_budget=5,
                          batch_size=2, exploration_floor=1)

    def test_trace_is_immutable_snapshot(self):
        allocator = UCB1Allocator(["A"], total_budget=2, batch_size=1)
        family = allocator.choose_next_family()
        allocator.observe_batch(family, 0.25)
        trace = allocator.allocation_trace()
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0].reward, 0.25)


if __name__ == "__main__":
    unittest.main()
