import unittest

from prototype.yixiang_family_generalization_m52 import (
    FamilySplitRecord, audit_family_split, audit_comparison_protocol,
    family_macro_average, paired_family_bootstrap,
)


def row(episode, split, family, template, lineage, seed_group):
    return FamilySplitRecord(
        episode, split, family, template, "linear-gaussian", lineage, seed_group
    )


class M52Tests(unittest.TestCase):
    def valid_records(self):
        return (
            row("tr-1", "train", "fam-tr", "template-tr", "generator-tr", "seed-tr"),
            row("tr-2", "train", "fam-tr", "template-tr", "generator-tr", "seed-tr"),
            row("va-1", "validation", "fam-va", "template-va", "generator-va", "seed-va"),
            row("te-1", "test", "fam-te", "template-te", "generator-te", "seed-te"),
        )

    def test_disjoint_family_split_passes(self):
        audit = audit_family_split(self.valid_records())
        self.assertTrue(audit.valid)
        self.assertEqual(dict(audit.counts_by_split),
                         {"train": 2, "validation": 1, "test": 1})

    def test_family_leakage_rejected(self):
        records = self.valid_records() + (
            row("te-2", "test", "fam-tr", "template-new", "generator-new", "seed-new"),
        )
        audit = audit_family_split(records)
        self.assertFalse(audit.valid)
        self.assertTrue(any("cross_split_leakage:family_id:fam-tr" in e
                            for e in audit.errors))

    def test_template_leakage_rejected(self):
        records = self.valid_records() + (
            row("te-2", "test", "fam-new", "template-tr", "generator-new", "seed-new"),
        )
        self.assertFalse(audit_family_split(records).valid)

    def test_generator_lineage_leakage_rejected(self):
        records = self.valid_records() + (
            row("te-2", "test", "fam-new", "template-new", "generator-tr", "seed-new"),
        )
        self.assertFalse(audit_family_split(records).valid)

    def test_seed_group_leakage_rejected(self):
        records = self.valid_records() + (
            row("te-2", "test", "fam-new", "template-new", "generator-new", "seed-tr"),
        )
        self.assertFalse(audit_family_split(records).valid)

    def test_duplicate_episode_rejected(self):
        records = self.valid_records() + (
            row("tr-1", "test", "fam-new", "template-new", "generator-new", "seed-new"),
        )
        audit = audit_family_split(records)
        self.assertFalse(audit.valid)
        self.assertTrue(any("duplicate_or_empty_episode_id" in e for e in audit.errors))

    def test_missing_split_rejected(self):
        audit = audit_family_split(self.valid_records()[:2])
        self.assertFalse(audit.valid)
        self.assertIn("missing_split:test", audit.errors)

    def test_invalid_split_rejected(self):
        records = self.valid_records() + (
            row("x", "holdout-ish", "f", "t", "g", "s"),
        )
        self.assertFalse(audit_family_split(records).valid)

    def test_empty_group_rejected(self):
        records = self.valid_records() + (
            row("x", "test", "f", "", "g", "s"),
        )
        self.assertFalse(audit_family_split(records).valid)

    def test_macro_average_weights_families_equally(self):
        self.assertAlmostEqual(family_macro_average({"large": 1.0, "small": 0.0}), 0.5)

    def test_macro_average_rejects_empty_and_non_finite(self):
        with self.assertRaisesRegex(ValueError, "empty_family_scores"):
            family_macro_average({})
        with self.assertRaisesRegex(ValueError, "non_finite"):
            family_macro_average({"f": float("nan")})

    def test_macro_average_rejects_boolean_score(self):
        with self.assertRaisesRegex(ValueError, "invalid_family_score"):
            family_macro_average({"f": True})

    def test_paired_family_bootstrap_reproducible(self):
        a = {"f1": 0.8, "f2": 0.6, "f3": 0.7}
        b = {"f1": 0.5, "f2": 0.4, "f3": 0.6}
        first = paired_family_bootstrap(a, b, samples=500, seed=9)
        second = paired_family_bootstrap(a, b, samples=500, seed=9)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.mean_difference, 0.2)
        self.assertEqual(first.family_count, 3)

    def test_paired_bootstrap_requires_identical_families(self):
        with self.assertRaisesRegex(ValueError, "paired_family_sets_must_match"):
            paired_family_bootstrap({"f1": 0.8}, {"f2": 0.4})

    def test_paired_bootstrap_validates_samples_and_confidence(self):
        with self.assertRaisesRegex(ValueError, "at_least_100"):
            paired_family_bootstrap({"f": 1}, {"f": 0}, samples=10)
        with self.assertRaisesRegex(ValueError, "invalid_confidence"):
            paired_family_bootstrap({"f": 1}, {"f": 0}, confidence_level=1.0)

    def test_comparison_protocol_combines_splits(self):
        records = self.valid_records()
        audit = audit_comparison_protocol(records[:2], records[2:3], records[3:])
        self.assertTrue(audit.valid)

    def test_comparison_protocol_rejects_partition_label_mismatch(self):
        records = self.valid_records()
        audit = audit_comparison_protocol(
            train_records=records[2:3],
            validation_records=records[:2],
            test_records=records[3:],
        )
        self.assertFalse(audit.valid)
        self.assertTrue(any(error.startswith("partition_split_mismatch:")
                            for error in audit.errors))


if __name__ == "__main__":
    unittest.main()
