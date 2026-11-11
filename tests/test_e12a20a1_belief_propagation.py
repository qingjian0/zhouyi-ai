import unittest

from prototype.e12a20_factor_graph import Budget, Factor, Problem, Variable, infer as infer_exact
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
        exact = infer_exact(problem, budget=Budget(max_assignments=4, top_k=4))
        weights = [__import__("math").exp(-hypothesis.energy) for hypothesis in exact.hypotheses]
        normalizer = sum(weights)
        exact_marginals = {"x": {"0": 0.0, "1": 0.0}, "y": {"0": 0.0, "1": 0.0}}
        for hypothesis, weight in zip(exact.hypotheses, weights):
            for variable_id, value in hypothesis.assignment:
                exact_marginals[variable_id][value] += weight / normalizer
        for marginal in result.marginals:
            for value, probability in marginal.probabilities:
                self.assertAlmostEqual(probability, exact_marginals[marginal.variable_id][value], places=10)
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

    def test_globally_impossible_unary_factor_is_explicit(self):
        problem = Problem(
            (Variable("x", ("0", "1")),),
            (Factor("impossible", ("x",), "HARD",
                    forbidden_assignments=(("0",), ("1",)), default_cost=None),),
        )
        result = infer_beliefs(problem, budget=BPBudget(damping=1.0))
        self.assertEqual(result.status, "INCONSISTENT_MESSAGES")

    def test_isolated_variable_is_uniform(self):
        result = infer_beliefs(Problem((Variable("z", ("0", "1", "2")),), ()))
        self.assertEqual(result.status, "CONVERGED")
        for _, probability in result.marginals[0].probabilities:
            self.assertAlmostEqual(probability, 1 / 3)

    def test_non_lexicographic_factor_scope_order_is_respected(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("ordered-pair", ("y", "x"), "SOFT",
                    (( ("0", "0"), 0.0), (("1", "1"), 0.0),
                     (("0", "1"), 3.0), (("1", "0"), 3.0)), default_cost=4.0),),
        )
        result = infer_beliefs(problem, budget=BPBudget(damping=1.0))
        self.assertEqual(result.status, "CONVERGED")
        exact = infer_exact(problem, budget=Budget(max_assignments=4, top_k=4))
        weights = [__import__("math").exp(-item.energy) for item in exact.hypotheses]
        normalizer = sum(weights)
        expected = {"x": {"0": 0.0, "1": 0.0}, "y": {"0": 0.0, "1": 0.0}}
        for hypothesis, weight in zip(exact.hypotheses, weights):
            for variable_id, value in hypothesis.assignment:
                expected[variable_id][value] += weight / normalizer
        for marginal in result.marginals:
            for value, probability in marginal.probabilities:
                self.assertAlmostEqual(probability, expected[marginal.variable_id][value], places=10)

    def test_factor_table_budget_fails_closed(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("pair", ("x", "y"), "SOFT"),),
        )
        result = infer_beliefs(problem, budget=BPBudget(max_factor_entries=3))
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.marginals, ())

    def test_repeated_factor_evaluation_budget_fails_closed(self):
        problem = Problem(
            (Variable("x", ("0", "1")),),
            (Factor("unary", ("x",), "SOFT"),),
        )
        result = infer_beliefs(problem, budget=BPBudget(max_factor_evaluations=1))
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.factor_evaluations, 0)

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
            (Variable("x", ("0", "1")),),
            (Factor("unary", ("x",), "SOFT",
                    ((("0",), 1.0), (("1",), 0.0)), default_cost=2.0),),
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
