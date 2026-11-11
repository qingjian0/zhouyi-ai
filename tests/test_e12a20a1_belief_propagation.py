import unittest

from prototype.e12a20_factor_graph import Factor, Problem, Variable
from prototype.e12a20a1_belief_propagation import BPBudget, infer_beliefs


class BeliefPropagationTests(unittest.TestCase):
    def test_tree_marginals_match_exact_distribution(self):
        # x and y are equal with a soft mismatch penalty; unary evidence favors x=1.
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (
                Factor("pair", ("x", "y"), "SOFT",
                       ((("0", "0"), 0.0), (("0", "1"), 2.0),
                        (("1", "0"), 2.0), (("1", "1"), 0.0)), default_cost=3.0),
                Factor("obs", ("x",), "EVIDENCE",
                       ((("0",), 1.5), (("1",), 0.0)), default_cost=2.0,
                       evidence_refs=("observation-1",)),
            ),
        )
        result = infer_beliefs(problem, budget=BPBudget(damping=1.0, tolerance=1e-12))
        self.assertEqual(result.status, "CONVERGED")
        self.assertAlmostEqual(sum(p for _, p in result.marginals[0].probabilities), 1.0)
        self.assertAlmostEqual(sum(p for _, p in result.marginals[1].probabilities), 1.0)
        self.assertGreater(dict(result.marginals[0].probabilities)["1"],
                           dict(result.marginals[0].probabilities)["0"])
        self.assertEqual(result.evidence_refs, ("observation-1",))

    def test_hard_constraint_produces_zero_probability_for_forbidden_state(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("not-both", ("x", "y"), "HARD",
                    forbidden_assignments=(("1", "1"),), default_cost=None),),
        )
        result = infer_beliefs(problem, budget=BPBudget(damping=1.0))
        self.assertEqual(result.status, "CONVERGED")
        self.assertLess(dict(result.marginals[0].probabilities)["1"], 0.5)
        self.assertLess(dict(result.marginals[1].probabilities)["1"], 0.5)

    def test_isolated_variable_is_uniform(self):
        result = infer_beliefs(Problem((Variable("z", ("0", "1", "2")),), ()))
        self.assertEqual(result.status, "CONVERGED")
        for _, probability in result.marginals[0].probabilities:
            self.assertAlmostEqual(probability, 1 / 3)

    def test_factor_table_budget_fails_closed(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("pair", ("x", "y"), "SOFT"),),
        )
        result = infer_beliefs(problem, budget=BPBudget(max_factor_entries=3))
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.marginals, ())

    def test_message_update_budget_fails_closed(self):
        problem = Problem(
            (Variable("x", ("0", "1")),),
            (Factor("u", ("x",), "SOFT"),),
        )
        result = infer_beliefs(problem, budget=BPBudget(max_message_updates=1))
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.message_updates, 0)

    def test_iteration_limit_is_not_reported_as_convergence(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("pair", ("x", "y"), "SOFT",
                    ((("0", "0"), 0.0), (("1", "1"), 0.0)), default_cost=1.0),),
        )
        result = infer_beliefs(problem, budget=BPBudget(max_iterations=1, damping=1.0, tolerance=1e-15))
        self.assertEqual(result.status, "ITERATION_LIMIT")

    def test_order_invariance(self):
        variables = (Variable("x", ("0", "1")), Variable("y", ("0", "1")))
        factors = (
            Factor("pair", ("x", "y"), "SOFT",
                   ((("0", "0"), 0.0), (("0", "1"), 1.0),
                    (("1", "0"), 1.0), (("1", "1"), 0.0)), default_cost=2.0),
            Factor("ux", ("x",), "PRIOR", ((("1",), 0.3),), default_cost=0.8),
        )
        a = infer_beliefs(Problem(variables, factors), budget=BPBudget(damping=1.0))
        b = infer_beliefs(Problem(tuple(reversed(variables)), tuple(reversed(factors))),
                          budget=BPBudget(damping=1.0))
        self.assertEqual(a, b)

    def test_invalid_damping_and_budgets_rejected(self):
        with self.assertRaises(ValueError):
            BPBudget(damping=0)
        with self.assertRaises(ValueError):
            BPBudget(max_iterations=0)


if __name__ == "__main__":
    unittest.main()
