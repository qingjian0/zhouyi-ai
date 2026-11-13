import unittest

from prototype.yixiang_relation_taxonomy import (
    CausalStatus, EvidenceLayer, RelationFamily, RelationMapping,
    TransferDecision, assess_relation_mapping,
)


class RelationTaxonomyTests(unittest.TestCase):
    def mapping(self, **overrides):
        values = dict(
            mapping_id="map-001",
            source_family=RelationFamily.FUNCTION,
            target_family=RelationFamily.FUNCTION,
            shared_basis=("same task-conditioned role",),
            non_shared_basis=("different material substrate",),
            scope_conditions=("same agent class and task",),
            source_evidence_refs=("source:edition-a:chapter-1",),
            target_evidence_refs=("target:edition-b:chapter-2",),
            source_layer=EvidenceLayer.CLASSICAL_TEXT,
            target_layer=EvidenceLayer.OBSERVATION,
            causal_status=CausalStatus.NOT_ASSERTED,
        )
        values.update(overrides)
        return RelationMapping(**values)

    def test_scope_supported_is_not_claimed_as_truth(self):
        result = assess_relation_mapping(self.mapping())
        self.assertEqual(result.decision, TransferDecision.SCOPE_SUPPORTED)
        self.assertTrue(result.scope_only)
        self.assertEqual(result.reason_codes, ())

    def test_relation_family_mismatch_is_refused(self):
        result = assess_relation_mapping(self.mapping(target_family=RelationFamily.CAUSAL))
        self.assertEqual(result.decision, TransferDecision.REFUSE)
        self.assertIn("RELATION_FAMILY_MISMATCH", result.reason_codes)

    def test_missing_shared_basis_is_refused(self):
        result = assess_relation_mapping(self.mapping(shared_basis=()))
        self.assertEqual(result.decision, TransferDecision.REFUSE)

    def test_missing_scope_or_evidence_abstains(self):
        result = assess_relation_mapping(self.mapping(scope_conditions=(), target_evidence_refs=()))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("MISSING_SCOPE_CONDITIONS", result.reason_codes)
        self.assertIn("MISSING_SIDE_SPECIFIC_EVIDENCE", result.reason_codes)

    def test_known_counterexample_requires_review(self):
        result = assess_relation_mapping(self.mapping(known_counterexamples=("counterexample-1",)))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)

    def test_unknown_causality_does_not_pass(self):
        result = assess_relation_mapping(self.mapping(causal_status=CausalStatus.UNKNOWN))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)

    def test_model_generated_layer_cannot_authenticate(self):
        result = assess_relation_mapping(self.mapping(target_layer=EvidenceLayer.MODEL_GENERATED))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("MODEL_OUTPUT_CANNOT_AUTHENTICATE_MAPPING", result.reason_codes)

    def test_malformed_tuple_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "shared_basis"):
            assess_relation_mapping(self.mapping(shared_basis=["not-a-tuple"]))


if __name__ == "__main__":
    unittest.main()
