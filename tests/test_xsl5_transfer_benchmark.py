import unittest

from prototype.xsl5_transfer_benchmark import (
    build_synthetic_suite,
    evaluate,
    lexical_baseline,
    perspective_aware_selector,
    run_suite,
    structural_baseline,
)


class XSL5TransferBenchmarkTests(unittest.TestCase):
    def test_suite_is_balanced_and_deterministic(self):
        first = build_synthetic_suite()
        second = build_synthetic_suite()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 48)
        self.assertEqual(sum(bool(x.accepted_candidate_ids) for x in first), 24)

    def test_lexical_baseline_falls_for_surface_distractor(self):
        metrics, predictions = evaluate(build_synthetic_suite(), lexical_baseline)
        self.assertEqual(metrics.correct_selected, 0)
        self.assertEqual(metrics.false_transfer, 48)
        self.assertTrue(all(x.selected_candidate_id == "candidate-lexical" for x in predictions))

    def test_structure_only_baseline_ignores_scope_and_negative_context(self):
        metrics, predictions = evaluate(build_synthetic_suite(), structural_baseline)
        self.assertEqual(metrics.correct_selected, 24)
        self.assertEqual(metrics.false_transfer, 24)
        self.assertEqual(metrics.false_transfer_on_no_transfer_cases, 24)
        self.assertEqual(metrics.negative_transfer_rate, 1.0)
        self.assertTrue(all(x.selected_candidate_id == "candidate-structural" for x in predictions))

    def test_perspective_selector_transfers_when_scoped_and_abstains_otherwise(self):
        metrics, predictions = evaluate(build_synthetic_suite(), perspective_aware_selector)
        self.assertEqual(metrics.correct_selected, 24)
        self.assertEqual(metrics.false_transfer, 0)
        self.assertEqual(metrics.false_transfer_on_no_transfer_cases, 0)
        self.assertEqual(metrics.abstained_correctly, 24)
        self.assertEqual(metrics.coverage, 0.5)
        self.assertEqual(metrics.precision, 1.0)
        self.assertEqual(metrics.recall, 1.0)
        self.assertEqual(metrics.negative_transfer_rate, 0.0)
        self.assertEqual(metrics.abstention_accuracy, 1.0)
        self.assertTrue(all(
            p.selected_candidate_id == ("candidate-structural" if i < 24 else None)
            for i, p in enumerate(predictions)
        ))

    def test_unknown_evidence_never_qualifies_for_transfer(self):
        case = build_synthetic_suite(1, 1)[0]
        unknown_only = case.candidates[-1]
        modified = type(case)(
            case.case_id, case.query_terms, case.query_relations,
            case.context, (unknown_only,), frozenset({"candidate-unknown"})
        )
        prediction = perspective_aware_selector(modified)
        self.assertIsNone(prediction.selected_candidate_id)

    def test_evaluator_rejects_empty_candidates_and_unknown_gold_ids(self):
        case = build_synthetic_suite(1, 1)[0]
        empty = type(case)(
            case.case_id, case.query_terms, case.query_relations,
            case.context, (), frozenset()
        )
        with self.assertRaises(ValueError):
            evaluate((empty,), lexical_baseline)
        invalid_gold = type(case)(
            case.case_id, case.query_terms, case.query_relations,
            case.context, case.candidates, frozenset({"missing"})
        )
        with self.assertRaises(ValueError):
            evaluate((invalid_gold,), lexical_baseline)

    def test_evaluator_rejects_duplicate_case_ids(self):
        case = build_synthetic_suite(1, 1)[0]
        duplicate = type(case)(
            case.case_id, case.query_terms, case.query_relations,
            case.context, case.candidates, case.accepted_candidate_ids
        )
        with self.assertRaises(ValueError):
            evaluate((case, duplicate), lexical_baseline)

    def test_empty_or_invalid_suite_size_rejected(self):
        with self.assertRaises(ValueError):
            build_synthetic_suite(0, 1)
        with self.assertRaises(ValueError):
            build_synthetic_suite(1, 0)

    def test_metrics_are_exposed_for_all_baselines(self):
        results = run_suite()
        self.assertEqual(set(results), {"lexical", "structural", "perspective_aware"})
        self.assertIn("negative_transfer_rate", results["perspective_aware"])
        self.assertIn("abstention_accuracy", results["perspective_aware"])


if __name__ == "__main__":
    unittest.main()
