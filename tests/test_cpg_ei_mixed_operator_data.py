import unittest

from prototype.cpg_ei_relation_operators import OPERATORS, RelationRule, evaluate_rule
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestMixedOperatorCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = generate_mixed_corpus()

    def test_default_scale_and_dimensions(self):
        manifest = self.corpus["manifest"]
        self.assertEqual(manifest["family_count"], 40)
        self.assertEqual(manifest["states_per_family"], 256)
        self.assertEqual(manifest["row_count"], 10_240)
        self.assertEqual(manifest["teacher_rule_count"], 320)
        self.assertEqual(manifest["operators"], list(OPERATORS))

    def test_all_operator_families_are_present_and_balanced(self):
        counts = self.corpus["manifest"]["operator_rule_counts"]
        self.assertEqual(set(counts), set(OPERATORS))
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_teacher_rules_reproduce_every_target(self):
        teachers = {t["family_id"]: t for t in self.corpus["teachers"]}
        for row in self.corpus["rows"][::31]:
            rules = teachers[row["family_id"]]["rules"]
            expected = []
            for spec in rules:
                rule = RelationRule(
                    operator=spec["operator"], support=tuple(spec["support"]),
                    threshold=spec["threshold"], context_index=spec["context_index"],
                    context_value=spec["context_value"] if spec["context_value"] is not None else 1,
                )
                expected.append(evaluate_rule(tuple(row["state"]), rule))
            self.assertEqual(row["target"], expected)

    def test_splits_are_complete_and_disjoint(self):
        by_family = {}
        for row in self.corpus["rows"]:
            by_family.setdefault(row["family_id"], []).append(row)
        for rows in by_family.values():
            splits = {
                name: {tuple(r["state"]) for r in rows if r["state_split"] == name}
                for name in ("train", "development", "locked")
            }
            self.assertEqual(tuple(map(len, (splits["train"], splits["development"], splits["locked"]))),
                             (128, 64, 64))
            self.assertFalse(splits["train"] & splits["development"])
            self.assertFalse(splits["train"] & splits["locked"])
            self.assertFalse(splits["development"] & splits["locked"])

    def test_deterministic_and_dimension_generic(self):
        first = generate_mixed_corpus(family_count=5, input_dim=4, output_dim=7, seed=91)
        second = generate_mixed_corpus(family_count=5, input_dim=4, output_dim=7, seed=91)
        self.assertEqual(first["manifest"], second["manifest"])
        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(first["manifest"]["row_count"], 5 * 16)

    def test_invalid_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            generate_mixed_corpus(family_count=4)
        with self.assertRaises(ValueError):
            generate_mixed_corpus(input_dim=2)


if __name__ == "__main__":
    unittest.main()
