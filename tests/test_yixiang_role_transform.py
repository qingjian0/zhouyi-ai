import unittest

from prototype.yixiang_analogy import Relation
from prototype.yixiang_role_transform import (
    RoleTransform,
    apply_role_transform,
    compose_argument_permutations,
)


class XSL3RoleTransformTests(unittest.TestCase):
    def test_identity_transform_preserves_argument_order(self):
        source = Relation("supports", ("evidence", "claim"))
        transform = RoleTransform("identity", "1", "supports", "supports", (0, 1))
        result = apply_role_transform(source, transform)
        self.assertEqual(result.transformed_relation, source)
        self.assertEqual(result.semantic_status, "HYPOTHESIS_ONLY")

    def test_explicit_reversal_changes_order_only_when_declared(self):
        source = Relation("causes", ("cause", "effect"))
        transform = RoleTransform(
            "reverse-roles", "1.0", "causes", "candidate_causes_reverse",
            (1, 0), scope_conditions=("scope:test",), evidence_refs=("evidence:1",))
        result = apply_role_transform(source, transform)
        self.assertEqual(result.transformed_relation,
                         Relation("candidate_causes_reverse", ("effect", "cause")))
        self.assertEqual(result.transform_version, "1.0")
        self.assertEqual(result.semantic_status, "HYPOTHESIS_ONLY")

    def test_ternary_permutation_is_explicit(self):
        source = Relation("ternary", ("a", "b", "c"))
        transform = RoleTransform("cycle", "2", "ternary", "ternary", (1, 2, 0))
        result = apply_role_transform(source, transform)
        self.assertEqual(result.transformed_relation.arguments, ("b", "c", "a"))

    def test_wrong_relation_type_rejected(self):
        with self.assertRaisesRegex(ValueError, "relation type"):
            apply_role_transform(
                Relation("owns", ("a", "b")),
                RoleTransform("reverse", "1", "causes", "causes", (1, 0)))

    def test_wrong_arity_rejected(self):
        with self.assertRaisesRegex(ValueError, "arity"):
            apply_role_transform(
                Relation("causes", ("a", "b", "c")),
                RoleTransform("reverse", "1", "causes", "causes", (1, 0)))

    def test_invalid_duplicate_position_rejected(self):
        with self.assertRaisesRegex(ValueError, "permutation"):
            RoleTransform("bad", "1", "r", "r", (0, 0))

    def test_boolean_position_rejected(self):
        with self.assertRaisesRegex(ValueError, "integers"):
            RoleTransform("bad", "1", "r", "r", (False, 1))

    def test_composition_order_is_documented_and_deterministic(self):
        first = (1, 0, 2)
        second = (2, 1, 0)
        self.assertEqual(compose_argument_permutations(first, second), (2, 0, 1))

    def test_composition_rejects_different_arities(self):
        with self.assertRaisesRegex(ValueError, "same arity"):
            compose_argument_permutations((0, 1), (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
