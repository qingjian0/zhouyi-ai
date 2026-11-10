import unittest
from itertools import product

from prototype.e12a5_residual_pair_diagnosis import (
    FeatureSpec, ResidualRecord, ResidualView,
)
from prototype.e12a5_sparse_subset_diagnosis import diagnose_sparse_subsets


def parity_view():
    rows = []
    index = 0
    for a, b, c in product((0.0, 1.0), repeat=3):
        for repeat in range(4):
            residual = int((int(a) + int(b) + int(c)) % 2 == 1)
            rows.append(ResidualRecord(
                f"e{index:03d}",
                (("a", a), ("d", float(repeat % 2)), ("b", b), ("c", c)),
                residual, 0,
            ))
            index += 1
    return ResidualView(
        tuple(FeatureSpec(name) for name in ("a", "d", "b", "c")),
        tuple(rows), "out_of_fold", "a3-parity-fixture",
    )


class SparseSubsetDiagnosisTests(unittest.TestCase):
    def test_discovers_noncontiguous_three_way_interaction(self):
        result = diagnose_sparse_subsets(
            parity_view(), min_order=3, max_order=3,
            quantile_bins=2, min_side_support=2,
            min_balanced_accuracy=0.60, top_k=50,
        )
        self.assertEqual(result["status"], "DIAGNOSED")
        self.assertTrue(any(
            item.features == ("a", "b", "c")
            and item.balanced_accuracy > 0.60
            for item in result["diagnoses"]
        ))
        self.assertTrue(any(item.skipped_positions > 0
                            for item in result["diagnoses"]))

    def test_pairwise_and_higher_order_can_be_compared(self):
        result = diagnose_sparse_subsets(
            parity_view(), min_order=2, max_order=3,
            quantile_bins=2, min_side_support=2,
            min_balanced_accuracy=0.5, top_k=100,
        )
        orders = {len(item.features) for item in result["diagnoses"]}
        self.assertIn(2, orders)
        self.assertIn(3, orders)

    def test_budget_exhaustion_returns_no_partial_diagnoses(self):
        result = diagnose_sparse_subsets(
            parity_view(), max_candidate_evaluations=1,
        )
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["diagnoses"], ())

    def test_subset_budget_is_enforced(self):
        result = diagnose_sparse_subsets(
            parity_view(), max_subset_count=1,
        )
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["budget"], "max_subset_count")

    def test_deterministic_ordering(self):
        view = parity_view()
        a = diagnose_sparse_subsets(view, top_k=30)
        b = diagnose_sparse_subsets(view, top_k=30)
        self.assertEqual(a["diagnoses"], b["diagnoses"])

    def test_rejects_invalid_orders_and_boolean_budget(self):
        with self.assertRaises(ValueError):
            diagnose_sparse_subsets(parity_view(), min_order=1)
        with self.assertRaises(TypeError):
            diagnose_sparse_subsets(parity_view(), max_subset_count=True)

    def test_preserves_provenance_and_matched_evidence(self):
        result = diagnose_sparse_subsets(
            parity_view(), min_order=3, max_order=3, top_k=100,
        )
        item = next(x for x in result["diagnoses"] if x.features == ("a", "b", "c"))
        self.assertEqual(result["prediction_mode"], "out_of_fold")
        self.assertEqual(result["model_version"], "a3-parity-fixture")
        self.assertTrue(item.matched_evidence_ids)
        self.assertTrue(item.unmatched_evidence_ids)

    def test_in_sample_is_rejected(self):
        view = parity_view()
        invalid = ResidualView(view.schema, view.records, "in_sample", view.model_version)
        with self.assertRaises(ValueError):
            diagnose_sparse_subsets(invalid)


if __name__ == "__main__":
    unittest.main()
