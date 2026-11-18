import unittest
from prototype.cpg_ei_relation_operators import (
    RelationRule, evaluate_rule, rule_manifest, truth_table,
)


class TestRelationOperators(unittest.TestCase):
    def test_boolean_operators(self):
        state = (1, 0, 1)
        expected = {
            "xor": 0, "and": 0, "or": 1, "nand": 1,
        }
        for operator, result in expected.items():
            with self.subTest(operator=operator):
                self.assertEqual(evaluate_rule(state, RelationRule(operator, (0, 1, 2))), result)

    def test_implication_is_order_sensitive(self):
        self.assertEqual(evaluate_rule((1, 0), RelationRule("implies", (0, 1))), 0)
        self.assertEqual(evaluate_rule((0, 1), RelationRule("implies", (0, 1))), 1)
        self.assertEqual(evaluate_rule((1, 0), RelationRule("implies", (1, 0))), 1)

    def test_threshold(self):
        rule = RelationRule("threshold", (0, 1, 2, 3), threshold=3)
        self.assertEqual(evaluate_rule((1, 1, 1, 0), rule), 1)
        self.assertEqual(evaluate_rule((1, 1, 0, 0), rule), 0)

    def test_conditional_xor_and_counterfactual_pair(self):
        rule = RelationRule("conditional_xor", (0, 1), context_index=2, context_value=1)
        self.assertEqual(evaluate_rule((1, 0, 1), rule), 1)
        self.assertEqual(evaluate_rule((1, 0, 0), rule), 0)

    def test_truth_table_is_complete_and_deterministic(self):
        rule = RelationRule("implies", (0, 1))
        table = truth_table(2, rule)
        self.assertEqual(len(table), 4)
        self.assertEqual(table, truth_table(2, rule))
        self.assertEqual(dict(table)[(1, 0)], 0)

    def test_manifest_preserves_role_order(self):
        manifest = rule_manifest(RelationRule("implies", (2, 0)), 3)
        self.assertEqual(manifest["support"], [2, 0])
        self.assertEqual(manifest["role_order"], [2, 0])

    def test_invalid_rules_are_rejected(self):
        cases = [
            (RelationRule("unknown", (0,)), 2),
            (RelationRule("implies", (0,)), 2),
            (RelationRule("threshold", (0, 1), threshold=0), 2),
            (RelationRule("conditional_xor", (0,), context_index=None), 2),
            (RelationRule("xor", (0, 0)), 2),
            (RelationRule("xor", (2,)), 2),
        ]
        for rule, dimension in cases:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                rule.validate(dimension)
        with self.assertRaises(ValueError):
            evaluate_rule((0, 2), RelationRule("xor", (0, 1)))


if __name__ == "__main__":
    unittest.main()
