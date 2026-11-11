import unittest

from prototype.znca_n3a_dirty_set import (
    ScheduleStatus,
    build_dependency_index,
    schedule_dirty_set,
)


class DirtySetSchedulerTests(unittest.TestCase):
    def test_direct_and_transitive_dependents_are_ordered(self):
        index = build_dependency_index((
            ("event", "b"), ("event", "a"), ("a", "c"), ("b", "d")
        ))
        result = schedule_dirty_set(("event",), index, max_hops=2)
        self.assertEqual(result.affected_ids, ("event", "a", "b", "c", "d"))
        self.assertEqual(result.status, ScheduleStatus.COMPLETE)
        self.assertEqual(result.max_depth_reached, 2)

    def test_hop_limit_stops_expansion(self):
        index = build_dependency_index((("a", "b"), ("b", "c")))
        result = schedule_dirty_set(("a",), index, max_hops=1)
        self.assertEqual(result.affected_ids, ("a", "b"))
        self.assertEqual(result.status, ScheduleStatus.COMPLETE)

    def test_node_budget_returns_explicit_frontier(self):
        index = build_dependency_index((
            ("root", "a"), ("root", "b"), ("a", "c"), ("b", "d")
        ))
        result = schedule_dirty_set(("root",), index, max_hops=3, max_nodes=2)
        self.assertEqual(result.affected_ids, ("root", "a"))
        self.assertEqual(result.frontier_ids, ("b", "c"))
        self.assertEqual(result.status, ScheduleStatus.BUDGET_EXHAUSTED)

    def test_multiple_roots_are_deduplicated(self):
        index = build_dependency_index((("a", "c"), ("b", "c")))
        result = schedule_dirty_set(("b", "a", "a"), index, max_hops=1)
        self.assertEqual(result.affected_ids, ("a", "b", "c"))

    def test_cycles_do_not_repeat_nodes(self):
        index = build_dependency_index((("a", "b"), ("b", "a"), ("b", "c")))
        result = schedule_dirty_set(("a",), index, max_hops=10)
        self.assertEqual(result.affected_ids, ("a", "b", "c"))

    def test_empty_roots_are_complete(self):
        result = schedule_dirty_set((), {}, max_hops=3)
        self.assertEqual(result.affected_ids, ())
        self.assertEqual(result.status, ScheduleStatus.COMPLETE)

    def test_invalid_budgets_and_edges_are_rejected(self):
        with self.assertRaises(ValueError):
            schedule_dirty_set(("a",), {}, max_hops=-1)
        with self.assertRaises(ValueError):
            schedule_dirty_set(("a",), {}, max_nodes=0)
        with self.assertRaises(ValueError):
            build_dependency_index((("a", "a"),))
        with self.assertRaises(ValueError):
            build_dependency_index((("", "b"),))


if __name__ == "__main__":
    unittest.main()
