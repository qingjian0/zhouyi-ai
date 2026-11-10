import unittest
from prototype.yinfu_interaction_dynamics import (
    InteractionEdge, InteractionGraph, detect_reversal, step, triadic_resource_demo,
)

class YinfuInteractionDynamicsTests(unittest.TestCase):
    def test_context_can_reverse_edge_polarity(self):
        graph = InteractionGraph(("a", "b"), (InteractionEdge("a", "b", 0.2, -0.5),))
        low = dict(step(graph, {"a": 1.0, "b": 0.0}, context=0.0).edge_effects)
        high = dict(step(graph, {"a": 1.0, "b": 0.0}, context=1.0).edge_effects)
        self.assertGreater(low[("a", "b")], 0)
        self.assertLess(high[("a", "b")], 0)

    def test_updates_are_synchronous_and_order_independent(self):
        edges = (
            InteractionEdge("a", "b", 1.0),
            InteractionEdge("b", "c", 2.0),
        )
        states = {"a": 1.0, "b": 1.0, "c": 1.0}
        first = step(InteractionGraph(("a", "b", "c"), edges), states, context=0.0)
        second = step(InteractionGraph(("c", "b", "a"), tuple(reversed(edges))), states, context=0.0)
        self.assertEqual(first.states, second.states)

    def test_reversal_requires_opposite_nontrivial_signs(self):
        self.assertTrue(detect_reversal(1.0, -0.2).reversed)
        self.assertFalse(detect_reversal(1.0, 0.2).reversed)
        self.assertFalse(detect_reversal(0.0, -1.0).reversed)

    def test_triadic_demo_reports_metrics(self):
        result = triadic_resource_demo(5)
        self.assertIn("short_term_agent_delta", result)
        self.assertIn("long_term_joint_delta", result)
        self.assertIsInstance(result["reversal"]["reversed"], bool)

    def test_invalid_graph_endpoint_is_rejected(self):
        graph = InteractionGraph(("a",), (InteractionEdge("a", "missing", 1.0),))
        with self.assertRaises(ValueError):
            step(graph, {"a": 1.0}, context=0.0)

    def test_missing_state_is_rejected(self):
        graph = InteractionGraph(("a", "b"), ())
        with self.assertRaises(ValueError):
            step(graph, {"a": 1.0}, context=0.0)

if __name__ == "__main__":
    unittest.main()
