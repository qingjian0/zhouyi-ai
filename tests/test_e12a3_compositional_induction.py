import unittest

from prototype.e12a1_typed_predicate_induction import (
    Example, FeatureSpec, LearnerView, Predicate,
)
from prototype.e12a3_compositional_induction import (
    Expr,
    canonical_key,
    generate_candidates,
    infer_compositions,
)


class E12A3CompositionTests(unittest.TestCase):
    def setUp(self):
        self.primitives = tuple(
            Predicate(name, "numeric", "GE", 0.5)
            for name in ("a", "b", "c", "d", "e")
        )

    def test_sparse_non_contiguous_ace_candidate_is_generated(self):
        candidates = generate_candidates(self.primitives, max_arity=3, max_depth=1)
        target = Expr("ALL_OF", (self.primitives[0], self.primitives[2], self.primitives[4]))
        keys = {canonical_key(candidate) for candidate in candidates}
        self.assertIn(canonical_key(target), keys)

    def test_sparse_candidate_ignores_b_and_d(self):
        target = Expr("ALL_OF", (self.primitives[0], self.primitives[2], self.primitives[4]))
        rows = (
            (1, 0, 1, 1, 1),
            (1, 1, 1, 0, 1),
            (1, 1, 1, 1, 0),
            (0, 1, 1, 0, 1),
            (1, 0, 0, 1, 1),
        )
        for row in rows:
            ex = Example(tuple(zip(("a", "b", "c", "d", "e"), row)), int(bool(row[0] and row[2] and row[4])))
            self.assertEqual(target.evaluate(ex), ex.label)

    def test_commutative_expressions_have_same_canonical_key(self):
        left = Expr("AND", (self.primitives[0], self.primitives[2]))
        right = Expr("AND", (self.primitives[2], self.primitives[0]))
        self.assertEqual(canonical_key(left), canonical_key(right))

    def test_candidate_order_is_deterministic(self):
        forward = generate_candidates(self.primitives, max_arity=3, max_depth=2)
        reverse = generate_candidates(reversed(self.primitives), max_arity=3, max_depth=2)
        self.assertEqual(
            tuple(map(canonical_key, forward)),
            tuple(map(canonical_key, reverse)),
        )

    def test_candidate_budget_exhaustion_is_explicit(self):
        view = self._view()
        result = infer_compositions(view, candidate_budget=2)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertIsNone(result["selected"])
        self.assertEqual(result["evaluated_count"], 0)

    def test_ill_typed_primitive_evaluation_is_rejected(self):
        bad = Predicate("a", "numeric", "GE", 0.5)
        ex = Example((("a", "one"),), 1)
        with self.assertRaises(TypeError):
            bad.evaluate(ex.value("a"))

    def test_unidentifiable_view_remains_ambiguous(self):
        view = LearnerView(
            schema=(FeatureSpec("x", "numeric"), FeatureSpec("z", "numeric")),
            train=(
                Example((("x", 0), ("z", 0)), 0),
                Example((("x", 1), ("z", 1)), 1),
                Example((("x", 0), ("z", 0)), 0),
            ),
            gate=(
                Example((("x", 1), ("z", 1)), 1),
                Example((("x", 0), ("z", 0)), 0),
            ),
        )
        result = infer_compositions(view, max_arity=2, max_depth=1, candidate_budget=5000)
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertIsNone(result["selected"])
        self.assertGreater(result["gate_consistent_count"], 1)

    def test_learner_api_does_not_accept_test_or_oracle_truth(self):
        import inspect
        self.assertEqual(
            list(inspect.signature(infer_compositions).parameters),
            ["view", "max_arity", "max_depth", "max_nodes", "candidate_budget"],
        )

    def _view(self):
        schema = tuple(FeatureSpec(name, "numeric") for name in ("a", "b", "c"))
        train = (
            Example((("a", 0), ("b", 0), ("c", 0)), 0),
            Example((("a", 1), ("b", 1), ("c", 1)), 1),
            Example((("a", 1), ("b", 0), ("c", 1)), 1),
        )
        gate = (
            Example((("a", 0), ("b", 1), ("c", 0)), 0),
            Example((("a", 1), ("b", 1), ("c", 1)), 1),
        )
        return LearnerView(schema, train, gate)


if __name__ == "__main__":
    unittest.main()
