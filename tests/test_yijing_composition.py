import unittest

from prototype.yijing_composition import (
    CompositionPlanner, CompositionPlanningError,
)


class CompositionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = CompositionPlanner()

    def test_plan_respects_repeated_input_type_multiplicity(self):
        report = self.planner.plan(
            ("DualAxis", "DualState", "DualState"), "candidate"
        )
        self.assertEqual(len(report.plans), 1)
        self.assertEqual(report.plans[0].operators, ("YY_COMPLEMENT",))

    def test_missing_second_state_prevents_application(self):
        report = self.planner.plan(("DualAxis", "DualState"), "candidate")
        self.assertEqual(report.plans, ())

    def test_parallel_frontier_lists_independent_applicable_operators(self):
        frontier = self.planner.parallel_frontier(
            ("InfluenceEdge", "Context", "float", "DualAxis",
             "DualState", "DualState")
        )
        self.assertIn("YY_COMPLEMENT", frontier)
        self.assertIn("WX_INFLUENCE", frontier)

    def test_non_adjacent_composition_is_found_when_types_connect(self):
        # A small local registry demonstrates A -> C -> E without B.
        from prototype.yijing_operators import OperatorContract
        registry = {
            "A_TO_C": OperatorContract("A_TO_C", "test", ("A",), "C", "v1"),
            "B_UNUSED": OperatorContract("B_UNUSED", "test", ("A",), "B", "v1"),
            "C_TO_E": OperatorContract("C_TO_E", "test", ("C",), "E", "v1"),
        }
        report = CompositionPlanner(registry).plan(("A",), "E", max_depth=3)
        self.assertEqual(report.plans[0].operators, ("A_TO_C", "C_TO_E"))

    def test_cycles_are_bounded_by_no_reuse(self):
        from prototype.yijing_operators import OperatorContract
        registry = {
            "A_B": OperatorContract("A_B", "test", ("A",), "B", "v1"),
            "B_A": OperatorContract("B_A", "test", ("B",), "A", "v1"),
        }
        report = CompositionPlanner(registry).plan(("A",), "Z", max_depth=20)
        self.assertEqual(report.plans, ())
        self.assertLessEqual(report.explored_states, 3)

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(CompositionPlanningError):
            self.planner.plan(("A",), "B", max_states=0)


if __name__ == "__main__":
    unittest.main()
