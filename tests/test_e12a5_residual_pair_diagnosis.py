import unittest

from prototype.e12a5_residual_pair_diagnosis import (
    FeatureSpec, ResidualRecord, ResidualView, diagnose_pairs,
)


def record(eid, x, y, z, w, residual):
    label = 1 if residual else 0
    prediction = 0 if residual else 0
    return ResidualRecord(eid, (("x", x), ("y", y), ("z", z), ("w", w)),
                          label, prediction)


class ResidualPairDiagnosisTests(unittest.TestCase):
    def view(self):
        # abs(x-y) separates A3 residuals perfectly at threshold 2.5.
        rows = (
            record("r1", 0, 1, 0, 1, False),
            record("r2", 2, 3, 1, 2, False),
            record("r3", 0, 4, 2, 3, True),
            record("r4", 1, 5, 3, 4, True),
            record("r5", 2, 7, 4, 5, True),
            record("r6", 3, 8, 5, 6, True),
        )
        return ResidualView(
            (FeatureSpec("x"), FeatureSpec("y"), FeatureSpec("z"), FeatureSpec("w")),
            rows, "prequential", "A3-test-v1",
        )

    def test_diagnoses_pair_correlated_with_residuals(self):
        result = diagnose_pairs(self.view(), min_side_support=2, top_k=3)
        self.assertEqual(result["status"], "DIAGNOSED")
        xy = next(item for item in result["diagnoses"]
                  if (item.left, item.right) == ("x", "y"))
        self.assertAlmostEqual(xy.balanced_accuracy, 1.0)
        self.assertEqual(xy.polarity, "HIGH_ERROR")
        self.assertAlmostEqual(xy.threshold, 2.5)
        self.assertEqual(result["counterexample_pairs"][0], ("x", "y"))

    def test_only_prequential_or_oof_predictions_are_accepted(self):
        view = self.view()
        with self.assertRaises(ValueError):
            diagnose_pairs(ResidualView(view.schema, view.records,
                                        "in_sample", view.model_version))

    def test_requires_both_residual_classes(self):
        view = self.view()
        all_correct = tuple(ResidualRecord(item.evidence_id, item.values,
                                           item.label, item.label)
                            for item in view.records)
        with self.assertRaises(ValueError):
            diagnose_pairs(ResidualView(view.schema, all_correct,
                                        "prequential", view.model_version))

    def test_minimum_side_support_prevents_tiny_split(self):
        result = diagnose_pairs(self.view(), min_side_support=4,
                                min_balanced_accuracy=0.65)
        self.assertEqual(result["status"], "NO_SUPPORTED_PAIR")

    def test_gate_or_test_is_not_part_of_diagnosis_interface(self):
        view = self.view()
        self.assertFalse(hasattr(view, "gate"))
        self.assertFalse(hasattr(view, "test"))

    def test_evidence_and_model_provenance_are_retained(self):
        result = diagnose_pairs(self.view())
        xy = next(item for item in result["diagnoses"]
                  if (item.left, item.right) == ("x", "y"))
        self.assertEqual(xy.evidence_ids, tuple(f"r{i}" for i in range(1, 7)))
        self.assertEqual(result["model_version"], "A3-test-v1")
        self.assertEqual(result["prediction_mode"], "prequential")

    def test_invalid_numeric_and_threshold_parameters_fail_closed(self):
        view = self.view()
        bad_record = ResidualRecord("bad", (("x", True), ("y", 1),
                                            ("z", 0), ("w", 1)), 0, 0)
        bad = ResidualView(view.schema, (bad_record,) + view.records[1:],
                           "prequential", view.model_version)
        with self.assertRaises(TypeError):
            diagnose_pairs(bad)
        with self.assertRaises(ValueError):
            diagnose_pairs(view, min_balanced_accuracy=0.4)
        with self.assertRaises(TypeError):
            diagnose_pairs(view, top_k=True)


if __name__ == "__main__":
    unittest.main()
