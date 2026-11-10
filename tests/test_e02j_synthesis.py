import unittest

from prototype.e02j_synthesis import (
    Expr,
    cegis,
    enumerate_programs,
    evaluate,
    synthesize,
    ternary_domain,
    variable,
)


class E02JSynthesisTests(unittest.TestCase):
    def test_non_contiguous_input_roles_are_supported(self):
        domain = ternary_domain((0, 2, 5))
        programs = enumerate_programs((0, 2, 5), max_depth=1)
        target = Expr("add", (variable(0), Expr("mul", (variable(2), variable(5)))))
        self.assertEqual(evaluate(target, (1, 0, 2, 0, 0, 2), 3), 2)
        self.assertTrue(any(evaluate(p, (1, 0, 2, 0, 0, 2), 3) == 2 for p in programs))
        self.assertEqual(len(domain), 27)

    def test_synthesis_recovers_target_semantics(self):
        roles = (0, 2, 5)
        domain = ternary_domain(roles)
        programs = enumerate_programs(roles, max_depth=2)
        target = Expr("add", (variable(0), Expr("mul", (variable(2), variable(5)))))
        observations = [(row, evaluate(target, row, 3)) for row in domain[:8]]
        candidate = synthesize(observations, programs)
        self.assertIsNotNone(candidate)
        self.assertTrue(all(
            evaluate(candidate, row, 3) == evaluate(target, row, 3)
            for row in domain
        ))

    def test_cegis_uses_counterexamples_to_repair_candidate(self):
        roles = (0, 2, 5)
        domain = ternary_domain(roles)
        target = Expr("add", (variable(0), Expr("mul", (variable(2), variable(5)))))
        programs = enumerate_programs(roles, max_depth=2)
        observations = [(domain[0], evaluate(target, domain[0], 3))]
        def oracle(candidate):
            for row in domain:
                expected = evaluate(target, row, 3)
                if evaluate(candidate, row, 3) != expected:
                    return row, expected
            return None
        result = cegis(observations, programs, oracle, query_budget=27)
        self.assertEqual(result.status, "verified")
        self.assertIsNotNone(result.expression)
        self.assertGreater(result.counterexamples, 0)

    def test_synthesis_rejects_empty_observations(self):
        with self.assertRaises(ValueError):
            synthesize([], [])

    def test_unsupported_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(Expr("divide", (variable(0), variable(2))), (1, 0, 2), 3)

    def test_invalid_role_indices_are_rejected(self):
        with self.assertRaises(ValueError):
            enumerate_programs((0, 0, 2))


if __name__ == "__main__":
    unittest.main()
