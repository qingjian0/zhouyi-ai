from __future__ import annotations

import unittest

from prototype.m2_extraction_evaluation import (
    ExtractionGoldCase,
    ExtractionPrediction,
    GoldSemanticUnit,
    evaluate_extraction_cases,
)
from prototype.observation_contract import (
    EpistemicStatus,
    EvidenceRef,
    GroundingStatus,
    RecordEnvelope,
    RoleBinding,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
)


def candidate(
    record_id: str,
    *,
    kind: UnitKind = UnitKind.CONCEPT,
    key: str | None = "concept:a",
    roles: tuple[tuple[str, str], ...] = (),
    confidence: float | None = 0.9,
) -> SemanticUnitCandidate:
    source = EvidenceRef(
        document_id="doc", chunk_id="chunk", content_sha256="a" * 64,
        byte_start=0, byte_end=4, source_version="v1",
    )
    envelope = RecordEnvelope(
        schema_version="m2-record-v1", record_id=record_id,
        record_kind="SemanticUnitCandidate", producer="test", producer_version="1",
        recorded_at="2026-11-12T00:00:00Z", scope="test",
        source_refs=(source,),
    )
    return SemanticUnitCandidate(
        envelope=envelope, kind=kind, surface_forms=("source phrase",),
        role_bindings=tuple(RoleBinding(role, target) for role, target in roles),
        canonical_key=key, grounding_status=GroundingStatus.UNRESOLVED,
        epistemic_status=EpistemicStatus.UNKNOWN, extractor_confidence=confidence,
        truth_status=TruthStatus.UNKNOWN,
    )


class ExtractionEvaluationTests(unittest.TestCase):
    def test_exact_unit_and_ordered_role_binding_match(self):
        gold = ExtractionGoldCase(
            "case-1", "general",
            (GoldSemanticUnit(
                UnitKind.EVENT, "event:transfer",
                (("agent", "entity:a"), ("recipient", "entity:b")),
            ),),
        )
        prediction = ExtractionPrediction("case-1", (
            candidate(
                "pred-1", kind=UnitKind.EVENT, key="event:transfer",
                roles=(("agent", "entity:a"), ("recipient", "entity:b")),
            ),
        ))
        result = evaluate_extraction_cases([gold], [prediction])
        self.assertEqual(result["unit"]["true_positive"], 1)
        self.assertEqual(result["unit"]["f1"], 1.0)

    def test_role_order_is_not_discarded(self):
        gold = ExtractionGoldCase(
            "case-1", "general",
            (GoldSemanticUnit(
                UnitKind.EVENT, "event:transfer",
                (("agent", "entity:a"), ("recipient", "entity:b")),
            ),),
        )
        prediction = ExtractionPrediction("case-1", (
            candidate(
                "pred-1", kind=UnitKind.EVENT, key="event:transfer",
                roles=(("recipient", "entity:b"), ("agent", "entity:a")),
            ),
        ))
        result = evaluate_extraction_cases([gold], [prediction])
        self.assertEqual(result["unit"]["false_positive"], 1)
        self.assertEqual(result["unit"]["false_negative"], 1)

    def test_abstention_and_coverage_are_measured_separately(self):
        gold = [
            ExtractionGoldCase("positive", "general", (GoldSemanticUnit(UnitKind.CONCEPT, "x"),)),
            ExtractionGoldCase("negative", "general", ()),
        ]
        predictions = [
            ExtractionPrediction("positive", (), abstained=True),
            ExtractionPrediction("negative", (), abstained=True),
        ]
        result = evaluate_extraction_cases(gold, predictions)
        self.assertEqual(result["abstention"]["true_positive"], 1)
        self.assertEqual(result["abstention"]["false_positive"], 1)
        self.assertEqual(result["abstention"]["recall"], 1.0)
        self.assertEqual(result["abstention"]["coverage"], 0.0)
        self.assertEqual(result["unit"]["false_negative"], 1)

    def test_confidence_brier_and_ece_are_reported(self):
        gold = ExtractionGoldCase(
            "case-1", "finance", (GoldSemanticUnit(UnitKind.CONCEPT, "right"),),
        )
        predictions = [ExtractionPrediction("case-1", (
            candidate("correct", key="right", confidence=0.8),
            candidate("wrong", key="wrong", confidence=0.2),
        ))]
        result = evaluate_extraction_cases(gold_cases=[gold], predictions=predictions, calibration_bins=2)
        self.assertAlmostEqual(result["calibration"]["brier_score"], 0.04)
        self.assertAlmostEqual(result["calibration"]["expected_calibration_error"], 0.2)
        self.assertEqual(result["calibration"]["count"], 2)

    def test_missing_confidence_is_not_imputed(self):
        gold = ExtractionGoldCase("case-1", "general", ())
        prediction = ExtractionPrediction("case-1", (candidate("p", confidence=None),))
        result = evaluate_extraction_cases([gold], [prediction])
        self.assertEqual(result["calibration"]["predictions_without_confidence"], 1)
        self.assertEqual(result["calibration"]["count"], 0)

    def test_missing_or_extra_prediction_cases_fail_closed(self):
        gold = ExtractionGoldCase("case-1", "general", ())
        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            evaluate_extraction_cases([gold], [])

    def test_duplicate_case_ids_are_rejected(self):
        case = ExtractionGoldCase("case-1", "general", ())
        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate_extraction_cases([case, case], [
                ExtractionPrediction("case-1", (), abstained=True),
            ])

    def test_missing_canonical_key_counts_as_invalid_false_positive(self):
        gold = ExtractionGoldCase("case-1", "general", ())
        prediction = ExtractionPrediction("case-1", (candidate("p", key=None),))
        result = evaluate_extraction_cases([gold], [prediction])
        self.assertEqual(result["unit"]["invalid_predictions"], 1)
        self.assertEqual(result["unit"]["false_positive"], 1)


if __name__ == "__main__":
    unittest.main()
