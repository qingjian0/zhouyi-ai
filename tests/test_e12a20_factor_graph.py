import unittest

from prototype.e12a20_factor_graph import (
    Budget, Factor, Problem, Variable, infer,
)


class FactorGraphReferenceTests(unittest.TestCase):
    def test_finds_lowest_energy_assignment(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (
                Factor("prior-x", ("x",), "PRIOR", ((("0",), 0.0), (("1",), 1.0)), default_cost=2.0),
                Factor("evidence-y", ("y",), "EVIDENCE", ((("1",), 0.0),), default_cost=2.0,
                       evidence_refs=("obs-17",)),
            ),
        )
        result = infer(problem)
        self.assertEqual(result.status, "CONVERGED")
        self.assertEqual(result.hypotheses[0].assignment, (("x", "0"), ("y", "1")))
        self.assertEqual(result.hypotheses[0].energy, 0.0)
        self.assertEqual(result.hypotheses[0].evidence_refs, ("obs-17",))

    def test_hard_factor_rejects_forbidden_assignments(self):
        problem = Problem(
            (Variable("x", ("0", "1")), Variable("y", ("0", "1"))),
            (Factor("not-both-one", ("x", "y"), "HARD",
                    forbidden_assignments=(("1", "1"),), default_cost=None),),
        )
        result = infer(problem)
        self.assertEqual(result.feasible_assignments, 3)
        self.assertEqual(result.rejected_assignments, 1)
        self.assertEqual(result.hard_conflict_counts, (("not-both-one", 1),))

    def test_no_feasible_assignment_is_explicit(self):
        problem = Problem(
            (Variable("x", ("0", "1")),),
            (Factor("forbid-both", ("x",), "HARD",
                    forbidden_assignments=(("0",), ("1",)), default_cost=None),),
        )
        result = infer(problem)
        self.assertEqual(result.status, "NO_FEASIBLE_ASSIGNMENT")
        self.assertEqual(result.hypotheses, ())

    def test_budget_exhaustion_never_claims_convergence(self):
        problem = Problem((Variable("x", ("0", "1")), Variable("y", ("0", "1"))), ())
        result = infer(problem, budget=Budget(max_assignments=2, top_k=2))
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.assignments_examined, 2)
        self.assertEqual(result.state_space_size, 4)

    def test_order_invariance(self):
        variables = (Variable("x", ("0", "1")), Variable("y", ("0", "1")))
        factors = (Factor("a", ("x",), "PRIOR", ((("1",), 0.2),), default_cost=0.8),
                   Factor("b", ("y",), "PRIOR", ((("0",), 0.1),), default_cost=0.9))
        a = infer(Problem(variables, factors))
        b = infer(Problem(tuple(reversed(variables)), tuple(reversed(factors))))
        self.assertEqual(a, b)

    def test_factor_cost_order_does_not_change_result(self):
        factor_a = Factor("f", ("x",), "SOFT",
                          ((("0",), 0.0), (("1",), 1.0)), default_cost=2.0)
        factor_b = Factor("f", ("x",), "SOFT",
                          ((("1",), 1.0), (("0",), 0.0)), default_cost=2.0)
        problem_a = Problem((Variable("x", ("0", "1")),), (factor_a,))
        problem_b = Problem((Variable("x", ("0", "1")),), (factor_b,))
        self.assertEqual(infer(problem_a), infer(problem_b))

    def test_rejects_invalid_factor_scope_and_domains(self):
        with self.assertRaisesRegex(ValueError, "unknown variable"):
            Problem((Variable("x", ("0", "1")),),
                    (Factor("bad", ("missing",), "SOFT"),))
        with self.assertRaisesRegex(ValueError, "outside variable domain"):
            Problem((Variable("x", ("0", "1")),),
                    (Factor("bad", ("x",), "SOFT", ((("2",), 1.0),)),))

    def test_rejects_invalid_factor_semantics(self):
        with self.assertRaisesRegex(ValueError, "hard factors"):
            Factor("bad", ("x",), "HARD", default_cost=0.0)
        with self.assertRaisesRegex(ValueError, "evidence_refs"):
            Factor("bad", ("x",), "EVIDENCE")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            Factor("bad", ("x",), "SOFT", ((("0",), -1.0),))

    def test_empty_domains_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            Variable("x", ())
        with self.assertRaisesRegex(ValueError, "duplicate variable"):
            Problem((Variable("x", ("0",)), Variable("x", ("1",))), ())


if __name__ == "__main__":
    unittest.main()
