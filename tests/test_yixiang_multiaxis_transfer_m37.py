import unittest
from prototype.yixiang_multiaxis_transfer_m37 import *


def fixtures():
    versions = (
        SourceVersion("src-work", "v-source", "w-source", "lineage-source", "classical_text", "Xiaoqu:locator"),
        SourceVersion("target-study", "v-target", "w-target", "lineage-target", "observation", "study:locator"),
    )
    evidence = (
        AxisEvidence("e-rel-s", Axis.RELATION, EvidenceSide.SOURCE, "src", "v-source",
                     EvidenceKind.CLASSICAL_TEXT, ReviewState.REVIEWED),
        AxisEvidence("e-rel-t", Axis.RELATION, EvidenceSide.TARGET, "tgt", "v-target",
                     EvidenceKind.OBSERVATION, ReviewState.REVIEWED),
        AxisEvidence("e-time-s", Axis.TIME, EvidenceSide.SOURCE, "src", "v-source",
                     EvidenceKind.CLASSICAL_TEXT, ReviewState.REVIEWED),
        AxisEvidence("e-time-t", Axis.TIME, EvidenceSide.TARGET, "tgt", "v-target",
                     EvidenceKind.OBSERVATION, ReviewState.REVIEWED),
    )
    mappings = (
        AxisMapping("m-rel", Axis.RELATION, "r1", "r2", "rule-rel", "scope",
                    ("e-rel-s", "e-rel-t"), MappingOutcome.PRESERVED, (), ("reviewer",), "audited"),
        AxisMapping("m-time", Axis.TIME, "t1", "t2", "rule-time", "scope",
                    ("e-time-s", "e-time-t"), MappingOutcome.PRESERVED, (), ("reviewer",), "audited"),
    )
    constraint = CrossAxisConstraint(
        "c1", ("m-rel", "m-time"), "cross-axis-rule",
        ("e-rel-s", "e-time-s"), ConstraintOutcome.SATISFIED, "joint scope", (), ("reviewer",), "checked"
    )
    candidate = TransferCandidate("cand1", "src", "tgt", (Axis.RELATION, Axis.TIME),
                                  mappings, (constraint,), "bounded scope", ("not causal proof",))
    return candidate, versions, evidence


class M37Tests(unittest.TestCase):
    def test_complete_declarations_are_only_eligible_for_external_validation(self):
        c, v, e = fixtures()
        r = audit_multiaxis_transfer(c, v, e)
        self.assertEqual(r.disposition, AuditDisposition.ELIGIBLE_FOR_EXTERNAL_VALIDATION)
        self.assertFalse(r.semantic_equivalence_established)
        self.assertFalse(r.causal_equivalence_established)

    def test_missing_required_axis_blocks(self):
        c, v, e = fixtures()
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              (Axis.RELATION, Axis.TIME, Axis.POTENTIAL), c.mappings,
                              c.constraints, c.scope, c.limitations)
        self.assertIn("missing_required_axis:potential", audit_multiaxis_transfer(c, v, e).issues)

    def test_source_and_target_evidence_are_both_required(self):
        c, v, e = fixtures()
        m = c.mappings[0]
        bad = AxisMapping(m.mapping_id, m.axis, m.source_value, m.target_value, m.mapping_rule_ref,
                          m.scope, ("e-rel-s",), m.outcome, (), m.reviewer_ids, m.rationale)
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, (bad, c.mappings[1]), c.constraints,
                              c.scope, c.limitations)
        self.assertIn("mapping_evidence_must_cover_source_and_target:m-rel",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_wrong_evidence_axis_blocks(self):
        c, v, e = fixtures()
        wrong = AxisEvidence("e-rel-t", Axis.TIME, EvidenceSide.TARGET, "tgt", "v-target",
                             EvidenceKind.OBSERVATION, ReviewState.REVIEWED)
        e = tuple(wrong if x.evidence_id == "e-rel-t" else x for x in e)
        self.assertIn("mapping_evidence_axis_mismatch:m-rel", audit_multiaxis_transfer(c, v, e).issues)

    def test_unknown_source_version_blocks(self):
        c, v, e = fixtures()
        bad = AxisEvidence("e-rel-s", Axis.RELATION, EvidenceSide.SOURCE, "src", "missing",
                           EvidenceKind.CLASSICAL_TEXT, ReviewState.REVIEWED)
        e = tuple(bad if x.evidence_id == "e-rel-s" else x for x in e)
        self.assertIn("unknown_source_version:e-rel-s", audit_multiaxis_transfer(c, v, e).issues)

    def test_preserved_mapping_requires_reviewed_evidence(self):
        c, v, e = fixtures()
        bad = AxisEvidence("e-rel-t", Axis.RELATION, EvidenceSide.TARGET, "tgt", "v-target",
                           EvidenceKind.OBSERVATION, ReviewState.UNREVIEWED)
        e = tuple(bad if x.evidence_id == "e-rel-t" else x for x in e)
        self.assertIn("preserved_mapping_requires_reviewed_evidence:m-rel",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_violation_requires_counterexample(self):
        c, v, e = fixtures()
        m = c.mappings[0]
        bad = AxisMapping(m.mapping_id, m.axis, m.source_value, m.target_value, m.mapping_rule_ref,
                          m.scope, m.evidence_refs, MappingOutcome.VIOLATED, (), m.reviewer_ids, m.rationale)
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, (bad, c.mappings[1]), c.constraints, c.scope, c.limitations)
        self.assertIn("violated_mapping_requires_counterexample:m-rel",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_counterexample_rejects_candidate_when_linked(self):
        c, v, e = fixtures()
        m = c.mappings[0]
        m = AxisMapping(m.mapping_id, m.axis, m.source_value, m.target_value, m.mapping_rule_ref,
                        m.scope, m.evidence_refs, MappingOutcome.VIOLATED,
                        ("e-rel-t",), m.reviewer_ids, m.rationale)
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, (m, c.mappings[1]), c.constraints,
                              c.scope, c.limitations)
        r = audit_multiaxis_transfer(c, v, e)
        self.assertEqual(r.disposition, AuditDisposition.REJECTED)
        self.assertEqual(r.rejected_axes, ("relation",))

    def test_cross_axis_constraint_must_span_distinct_mappings(self):
        c, v, e = fixtures()
        bad = CrossAxisConstraint("c1", ("m-rel", "m-rel"), "rule", ("e-rel-s", "e-time-s"),
                                  ConstraintOutcome.SATISFIED, "scope", (), ("reviewer",), "checked")
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, c.mappings, (bad,), c.scope, c.limitations)
        self.assertIn("cross_axis_constraint_requires_distinct_mappings:c1",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_cross_axis_evidence_must_cover_multiple_axes(self):
        c, v, e = fixtures()
        bad = CrossAxisConstraint("c1", ("m-rel", "m-time"), "rule", ("e-rel-s", "e-rel-t"),
                                  ConstraintOutcome.SATISFIED, "scope", (), ("reviewer",), "checked")
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, c.mappings, (bad,), c.scope, c.limitations)
        self.assertIn("constraint_evidence_must_cover_multiple_axes:c1",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_cross_axis_evidence_must_cover_source_and_target(self):
        c, v, e = fixtures()
        bad = CrossAxisConstraint("c1", ("m-rel", "m-time"), "rule",
                                  ("e-rel-s", "e-time-s"),
                                  ConstraintOutcome.SATISFIED, "scope", (), ("reviewer",), "checked")
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, c.mappings, (bad,), c.scope, c.limitations)
        self.assertIn("constraint_evidence_must_cover_source_and_target:c1",
                      audit_multiaxis_transfer(c, v, e).issues)

    def test_unresolved_constraint_is_conditional(self):
        c, v, e = fixtures()
        bad = CrossAxisConstraint("c1", ("m-rel", "m-time"), "rule", ("e-rel-s", "e-rel-t", "e-time-s", "e-time-t"),
                                  ConstraintOutcome.UNRESOLVED, "scope", (), ("reviewer",), "pending")
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, c.mappings, (bad,), c.scope, c.limitations)
        self.assertEqual(audit_multiaxis_transfer(c, v, e).disposition, AuditDisposition.CONDITIONAL)

    def test_conflict_is_review_required(self):
        c, v, e = fixtures()
        m = c.mappings[0]
        conflict = AxisMapping(m.mapping_id, m.axis, m.source_value, m.target_value, m.mapping_rule_ref,
                               m.scope, m.evidence_refs, MappingOutcome.CONFLICTED, (),
                               m.reviewer_ids, m.rationale)
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, (conflict, c.mappings[1]), c.constraints,
                              c.scope, c.limitations)
        self.assertEqual(audit_multiaxis_transfer(c, v, e).disposition, AuditDisposition.REVIEW_REQUIRED)

    def test_no_cross_axis_constraints_is_conditional(self):
        c, v, e = fixtures()
        c = TransferCandidate(c.candidate_id, c.source_context_id, c.target_context_id,
                              c.required_axes, c.mappings, (), c.scope, c.limitations)
        r = audit_multiaxis_transfer(c, v, e)
        self.assertEqual(r.disposition, AuditDisposition.CONDITIONAL)
        self.assertIn("no_cross_axis_constraints_registered", r.warnings)

    def test_duplicate_source_version_blocks(self):
        c, v, e = fixtures()
        self.assertIn("duplicate_source_version_id", audit_multiaxis_transfer(c, v + (v[0],), e).issues)

    def test_same_lineage_is_warned_not_counted_as_independence(self):
        c, v, e = fixtures()
        v2 = SourceVersion("target-study", "v-target", "w-target", "lineage-source", "observation", "study:locator")
        r = audit_multiaxis_transfer(c, (v[0], v2), e)
        self.assertIn("shared_declared_lineage:m-rel", r.warnings)

    def test_same_context_is_invalid(self):
        c, v, e = fixtures()
        c = TransferCandidate(c.candidate_id, "src", "src", c.required_axes, c.mappings,
                              c.constraints, c.scope, c.limitations)
        self.assertIn("source_and_target_context_must_differ", audit_multiaxis_transfer(c, v, e).issues)

    def test_non_empirical_target_support_warns(self):
        c, v, e = fixtures()
        bad = AxisEvidence("e-rel-t", Axis.RELATION, EvidenceSide.TARGET, "tgt", "v-target",
                           EvidenceKind.SYNTHETIC_FIXTURE, ReviewState.REVIEWED)
        e = tuple(bad if x.evidence_id == "e-rel-t" else x for x in e)
        self.assertIn("non_empirical_target_support:m-rel", audit_multiaxis_transfer(c, v, e).warnings)


if __name__ == "__main__":
    unittest.main()
