import unittest
from dataclasses import fields

from prototype.e02i2c_adjudication import (
    EvidencePacket, EvidencePolarity, EventType, IdentitySnapshot,
    MissingReason, ObservationOpportunity, adjudicate_event,
)


def opp(window, observed=10, expected=10, coverage=1.0, reason=None):
    return ObservationOpportunity(window, "lab", expected, observed, coverage, reason)


def packet(eid, window, polarity, signature=None, source="v1", sample=None, split="gate"):
    return EvidencePacket(
        eid, sample or f"s{window}-{eid}", window, "lab", split, polarity,
        source, signature, f"raw:{eid}",
    )


def active(status="ACTIVE", signature="a&b", version="v1"):
    return IdentitySnapshot("r1", status, version, signature)


class E02I2CContractsTests(unittest.TestCase):
    def test_insufficient_opportunity_is_not_absence(self):
        opportunity = opp(0, observed=0, coverage=0.0, reason=MissingReason.SENSOR_GAP)
        self.assertFalse(opportunity.sufficient())
        decision = adjudicate_event(active(), (opportunity,), ())
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_evidence_contract_has_no_hidden_truth_fields(self):
        names = {field.name for field in fields(EvidencePacket)}
        self.assertFalse({"true_identity_id", "true_event", "latent_identity",
                          "generator_transition"}.intersection(names))

    def test_locked_test_observations_are_inputs_not_hidden_labels(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("test-observation", 0, EvidencePolarity.SUPPORTS, "a&b", split="test"),
        ))
        self.assertEqual(decision.event, EventType.KEEP)
        names = {field.name for field in fields(EvidencePacket)}
        self.assertFalse({"true_identity_id", "true_event", "latent_identity",
                          "generator_transition"}.intersection(names))

    def test_duplicate_evidence_ids_and_orphan_evidence_rejected(self):
        with self.assertRaises(ValueError):
            adjudicate_event(None, (opp(0), opp(1)), (
                packet("same", 0, EvidencePolarity.SUPPORTS, "x"),
                packet("same", 1, EvidencePolarity.SUPPORTS, "x"),
            ))
        with self.assertRaises(ValueError):
            adjudicate_event(None, (opp(0),), (packet("orphan", 1, EvidencePolarity.SUPPORTS, "x"),))

    def test_create_requires_repeated_independent_support(self):
        one = adjudicate_event(None, (opp(0),), (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "x"),
        ))
        self.assertEqual(one.event, EventType.ABSTAIN)
        decision = adjudicate_event(None, (opp(0), opp(1)), (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "x"),
            packet("e1", 1, EvidencePolarity.SUPPORTS, "x"),
        ))
        self.assertEqual(decision.event, EventType.CREATE)
        self.assertEqual(decision.candidate_signature, "x")

    def test_active_same_signature_support_keeps_identity(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "a&b"),
        ))
        self.assertEqual(decision.event, EventType.KEEP)
        self.assertEqual(decision.identity_id, "r1")

    def test_single_window_rule_change_abstains_not_create_or_modify(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_modify_requires_multiwindow_version_linked_support(self):
        opportunities = (opp(0), opp(1))
        packets = (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
            packet("e1", 1, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        )
        decision = adjudicate_event(active(), opportunities, packets, candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.MODIFY)
        self.assertEqual(set(decision.evidence_refs), {"e0", "e1"})

    def test_competing_current_and_changed_support_abstains_with_both_provenances(self):
        decision = adjudicate_event(active(), (opp(0), opp(1), opp(2)), (
            packet("old", 0, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("new-1", 1, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
            packet("new-2", 2, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertIn("competing support", decision.reason)
        self.assertEqual(set(decision.evidence_refs), {"old", "new-1", "new-2"})

    def test_single_old_support_does_not_mask_multiwindow_change(self):
        decision = adjudicate_event(active(), (opp(0), opp(1), opp(2)), (
            packet("old-1", 0, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("old-2", 1, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("new", 2, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(set(decision.evidence_refs), {"old-1", "old-2", "new"})

    def test_change_evidence_for_another_candidate_does_not_modify_selected_candidate(self):
        decision = adjudicate_event(active(), (opp(0), opp(1)), (
            packet("other-0", 0, EvidencePolarity.SUPPORTS, "a|b", source="v1"),
            packet("other-1", 1, EvidencePolarity.SUPPORTS, "a|b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_candidate_filter_cannot_hide_current_support_from_contradiction(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("current-positive", 0, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("contradiction", 0, EvidencePolarity.CONTRADICTS, signature=None, source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(
            set(decision.evidence_refs),
            {"current-positive", "contradiction"},
        )

    def test_unlinked_changed_rule_does_not_modify(self):
        decision = adjudicate_event(active(), (opp(0), opp(1)), (
            packet("e0", 0, EvidencePolarity.SUPPORTS, "a^b", source="other"),
            packet("e1", 1, EvidencePolarity.SUPPORTS, "a^b", source="other"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_one_absence_window_does_not_suspend(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("absence", 0, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_recent_absence_streak_supersedes_older_keep_support(self):
        decision = adjudicate_event(active(), (opp(0), opp(1), opp(2)), (
            packet("old-support", 0, EvidencePolarity.SUPPORTS, "a&b"),
            packet("absence-1", 1, EvidencePolarity.ABSENCE, signature=None),
            packet("absence-2", 2, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.SUSPEND)
        self.assertEqual(set(decision.evidence_refs), {"absence-1", "absence-2"})

    def test_support_and_absence_in_same_window_abstain(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("support", 0, EvidencePolarity.SUPPORTS, "a&b"),
            packet("absence", 0, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(set(decision.evidence_refs), {"support", "absence"})

    def test_two_consecutive_sufficient_absence_windows_suspend(self):
        decision = adjudicate_event(active(), (opp(0), opp(1)), (
            packet("a0", 0, EvidencePolarity.ABSENCE, signature=None),
            packet("a1", 1, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.SUSPEND)

    def test_old_absence_sample_cannot_validate_reused_recent_absence_tail(self):
        decision = adjudicate_event(active(), (opp(0), opp(1), opp(2), opp(3)), (
            packet("old", 0, EvidencePolarity.ABSENCE, signature=None, sample="old-sample"),
            packet("tail-2", 2, EvidencePolarity.ABSENCE, signature=None, sample="reused-tail"),
            packet("tail-3", 3, EvidencePolarity.ABSENCE, signature=None, sample="reused-tail"),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_suspension_references_only_qualifying_absence_tail(self):
        decision = adjudicate_event(active(), (opp(0), opp(1), opp(2)), (
            packet("old-absence", 0, EvidencePolarity.ABSENCE, signature=None),
            packet("tail-1", 1, EvidencePolarity.ABSENCE, signature=None),
            packet("tail-2", 2, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.SUSPEND)
        self.assertEqual(set(decision.evidence_refs), {"tail-1", "tail-2"})

    def test_reused_sample_cannot_suspend_across_two_windows(self):
        decision = adjudicate_event(active(), (opp(0), opp(1)), (
            packet("a0", 0, EvidencePolarity.ABSENCE, signature=None, sample="same-sample"),
            packet("a1", 1, EvidencePolarity.ABSENCE, signature=None, sample="same-sample"),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_reused_sample_cannot_retire_across_two_windows(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3)), (
            packet("c2", 2, EvidencePolarity.CONTRADICTS, signature=None, sample="same-sample"),
            packet("c3", 3, EvidencePolarity.CONTRADICTS, signature=None, sample="same-sample"),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_insufficient_window_breaks_absence_streak(self):
        decision = adjudicate_event(active(), (
            opp(0), opp(1, observed=0, coverage=0.0, reason=MissingReason.NO_EXPOSURE), opp(2),
        ), (
            packet("a0", 0, EvidencePolarity.ABSENCE, signature=None),
            packet("a2", 2, EvidencePolarity.ABSENCE, signature=None),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_conflicting_support_and_contradiction_abstains_with_provenance(self):
        decision = adjudicate_event(active(), (opp(0),), (
            packet("positive", 0, EvidencePolarity.SUPPORTS, "a&b"),
            packet("negative", 0, EvidencePolarity.CONTRADICTS, signature=None),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(set(decision.evidence_refs), {"positive", "negative"})
        self.assertIn("conflicting", decision.reason)
    def test_contradiction_is_not_absence_or_immediate_retirement(self):
        decision = adjudicate_event(active(), (opp(0), opp(1)), (
            packet("c0", 0, EvidencePolarity.CONTRADICTS, signature=None),
            packet("c1", 1, EvidencePolarity.CONTRADICTS, signature=None),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_suspended_competing_signatures_abstain_with_both_provenances(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3), opp(4)), (
            packet("same-2", 2, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("changed-3", 3, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
            packet("changed-4", 4, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(
            set(decision.evidence_refs),
            {"same-2", "changed-3", "changed-4"},
        )

    def test_suspended_support_and_absence_same_window_abstain(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3)), (
            packet("support", 2, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("absence", 2, EvidencePolarity.ABSENCE, signature=None, source="v1"),
            packet("support-3", 3, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)
        self.assertEqual(
            set(decision.evidence_refs),
            {"support", "absence", "support-3"},
        )

    def test_suspended_identity_reactivates_only_with_repeated_fresh_support(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3)), (
            packet("fresh-2", 2, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
            packet("fresh-3", 3, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
        ))
        self.assertEqual(decision.event, EventType.REACTIVATE)

    def test_single_fresh_sample_does_not_reactivate(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2),), (
            packet("fresh-once", 2, EvidencePolarity.SUPPORTS, "a&b", source="v1"),
        ))
        self.assertEqual(decision.event, EventType.ABSTAIN)

    def test_suspended_changed_version_requires_linked_multwindow_support(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3)), (
            packet("m2", 2, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
            packet("m3", 3, EvidencePolarity.SUPPORTS, "a^b", source="v1"),
        ), candidate_signature="a^b")
        self.assertEqual(decision.event, EventType.REACTIVATE_MODIFY)

    def test_retire_requires_suspended_and_repeated_contradiction(self):
        decision = adjudicate_event(active("SUSPENDED"), (opp(2), opp(3)), (
            packet("c2", 2, EvidencePolarity.CONTRADICTS, signature=None),
            packet("c3", 3, EvidencePolarity.CONTRADICTS, signature=None),
        ))
        self.assertEqual(decision.event, EventType.RETIRE)

    def test_terminal_identity_abstains(self):
        for status in ("RETIRED", "SPLIT", "MERGED", "REPLACED"):
            decision = adjudicate_event(active(status), (opp(0),), ())
            self.assertEqual(decision.event, EventType.ABSTAIN)


if __name__ == "__main__":
    unittest.main()
