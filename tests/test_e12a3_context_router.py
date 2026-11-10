import inspect
import unittest

from prototype.e12a3_adaptive_benchmark import make_four_way_world, _make_pools
from prototype.e12a3_context_router import (
    METHODS,
    _context_descriptors,
    _context_route_allocate,
    run_benchmark,
    run_episode,
    split_support_context,
)


class E12A3ContextRouterTests(unittest.TestCase):
    def test_support_is_split_into_disjoint_proposal_and_context_sets(self):
        support, _, _, _ = make_four_way_world(41, "PARITY")
        proposal, context = split_support_context(support, 41)
        self.assertEqual((len(proposal), len(context)), (48, 16))
        self.assertFalse(
            {r.observation_id for r in proposal}
            & {r.observation_id for r in context}
        )
        self.assertEqual({r.label for r in context}, {0, 1})

    def test_proposal_generation_receives_no_context_rows(self):
        support, _, _, _ = make_four_way_world(42, "THRESHOLD")
        proposal, context = split_support_context(support, 42)
        first = _make_pools(proposal, 42)
        flipped_context = tuple(
            type(row)(row.observation_id, row.values, 1 - row.label)
            for row in context
        )
        second = _make_pools(proposal, 42)
        self.assertEqual(first, second)
        self.assertTrue(flipped_context)

    def test_parity_is_a_new_task_expressible_by_stat_grammar(self):
        support, _, _, _ = make_four_way_world(43, "PARITY")
        proposal, context = split_support_context(support, 43)
        pools = _make_pools(proposal, 43)
        self.assertTrue(any(
            p.expression.operator == "PARITY" for p in pools["STAT"]
        ))
        self.assertEqual({r.label for r in context}, {0, 1})

    def test_context_router_api_excludes_gate_and_test_data(self):
        self.assertEqual(
            list(inspect.signature(_context_route_allocate).parameters),
            ["proposal_support", "context_support", "seed", "budget", "batch_size"],
        )

    def test_context_descriptors_are_bounded_and_deterministic(self):
        support, _, _, _ = make_four_way_world(44, "PAIRWISE_DIFFERENCE")
        proposal, context = split_support_context(support, 44)
        pools = _make_pools(proposal, 44)
        first = _context_descriptors(pools, context)
        second = _context_descriptors(pools, context)
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"STAT", "RELATIONAL", "RANDOM"})
        self.assertTrue(all(0.0 <= value <= 1.0 for value in first.values()))

    def test_context_router_conserves_budget_and_is_reproducible(self):
        support, _, _, _ = make_four_way_world(45, "THRESHOLD")
        proposal, context = split_support_context(support, 45)
        first = _context_route_allocate(proposal, context, 45, budget=23)
        second = _context_route_allocate(proposal, context, 45, budget=23)
        self.assertEqual(first["trace"], second["trace"])
        self.assertEqual(first["allocations"], second["allocations"])
        self.assertEqual(first["proposal_slots_used"], 23)
        self.assertEqual(sum(first["allocations"].values()), 23)
        self.assertEqual(sum(event["slots"] for event in first["trace"]), 23)

    def test_router_requires_exploration_budget(self):
        support, _, _, _ = make_four_way_world(46, "THRESHOLD")
        proposal, context = split_support_context(support, 46)
        with self.assertRaises(ValueError):
            _context_route_allocate(proposal, context, 46, budget=11)

    def test_three_task_benchmark_has_exact_budgets(self):
        episode = run_episode(47, "PARITY", budget=20)
        self.assertEqual(set(episode["methods"]), set(METHODS))
        self.assertTrue(all(
            result["proposal_slots_used"] == 20
            for result in episode["methods"].values()
        ))
        result = run_benchmark(seeds=2, start_seed=48, budget=20)
        self.assertEqual(result["episode_count"], 6)
        self.assertIn("PARITY", result["task_metrics"])
        self.assertIn("SUPPORT_CONTEXT_ROUTER", result["aggregate"])


if __name__ == "__main__":
    unittest.main()
