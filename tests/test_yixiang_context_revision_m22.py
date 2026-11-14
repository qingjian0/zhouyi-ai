import unittest

from prototype.yixiang_context_revision_m22 import (
    ContextRevision, ContextSnapshot, RevisionKind, RevisionStatus,
    assess_context_revision,
)


def snapshot(version=1, active=("shape",), assumptions=("same_scale",), goal="identify"):
    return ContextSnapshot("ctx-1", version, "objects", goal, active, (), assumptions)


def revision(**overrides):
    before = snapshot()
    after = snapshot(version=2, active=("shape", "function"))
    values = dict(
        revision_id="rev-1", before=before, after=after, kind=RevisionKind.EXPAND,
        trigger_evidence_refs=("ev-1",), rationale="The task now asks about function as well as shape.",
        affected_claim_ids=("claim-1",), revalidated_claim_ids=("claim-1",),
        added_dimensions=("function",), retired_dimensions=(), added_excluded_dimensions=(), retired_excluded_dimensions=(), added_assumptions=(),
        retired_assumptions=(), changed_axes=(), reviewed=True,
    )
    values.update(overrides)
    return ContextRevision(**values)


class ContextRevisionTests(unittest.TestCase):
    def test_expansion_is_recorded_without_truth_claim(self):
        result = assess_context_revision(revision())
        self.assertEqual(result.status, RevisionStatus.CONTEXT_EXPANDED)
        self.assertFalse(result.semantic_validity_established)

    def test_unreviewed_revision_is_not_accepted(self):
        self.assertEqual(assess_context_revision(revision(reviewed=False)).status, RevisionStatus.UNREVIEWED)

    def test_missing_trigger_evidence_is_rejected(self):
        self.assertEqual(assess_context_revision(revision(trigger_evidence_refs=())).status, RevisionStatus.MISSING_TRIGGER_EVIDENCE)

    def test_wrong_version_increment_is_rejected(self):
        self.assertEqual(assess_context_revision(revision(after=snapshot(version=3, active=("shape", "function")))).status, RevisionStatus.INVALID_VERSION)

    def test_undeclared_added_dimension_is_detected(self):
        result = assess_context_revision(revision(added_dimensions=()))
        self.assertEqual(result.status, RevisionStatus.UNDECLARED_CHANGE)
        self.assertIn("added_dimensions", result.undeclared_changes)

    def test_stale_claims_are_exposed(self):
        result = assess_context_revision(revision(revalidated_claim_ids=()))
        self.assertEqual(result.status, RevisionStatus.STALE_CLAIMS)
        self.assertEqual(result.stale_claim_ids, ("claim-1",))

    def test_contracting_context_is_distinguished(self):
        before = snapshot(active=("shape", "function"))
        after = snapshot(version=2, active=("shape",))
        result = assess_context_revision(revision(before=before, after=after, kind=RevisionKind.CONTRACT, added_dimensions=(), retired_dimensions=("function",)))
        self.assertEqual(result.status, RevisionStatus.CONTEXT_CONTRACTED)

    def test_goal_change_requires_explicit_axis_declaration(self):
        after = snapshot(version=2, active=("shape", "function"), goal="predict")
        result = assess_context_revision(revision(after=after, changed_axes=()))
        self.assertEqual(result.status, RevisionStatus.UNDECLARED_CHANGE)
        self.assertIn("changed_axes", result.undeclared_changes)

    def test_goal_revision_requires_revalidation(self):
        after = snapshot(version=2, active=("shape", "function"), goal="predict")
        result = assess_context_revision(revision(after=after, kind=RevisionKind.REVISE, changed_axes=("goal",), revalidated_claim_ids=()))
        self.assertEqual(result.status, RevisionStatus.STALE_CLAIMS)

    def test_expand_cannot_silently_retire_assumptions(self):
        before = snapshot(assumptions=("same_scale", "same_actor"))
        after = snapshot(version=2, active=("shape", "function"), assumptions=("same_scale",))
        result = assess_context_revision(revision(before=before, after=after, added_dimensions=("function",)))
        self.assertEqual(result.status, RevisionStatus.UNDECLARED_CHANGE)

    def test_noop_is_not_a_revision(self):
        result = assess_context_revision(revision(after=snapshot(version=2), added_dimensions=(), affected_claim_ids=(), revalidated_claim_ids=()))
        self.assertEqual(result.status, RevisionStatus.NO_OP)

    def test_context_identity_cannot_change(self):
        after = ContextSnapshot("ctx-2", 2, "objects", "identify", ("shape", "function"), (), ("same_scale",))
        with self.assertRaises(ValueError):
            assess_context_revision(revision(after=after))

    def test_duplicate_evidence_refs_are_invalid(self):
        with self.assertRaises(ValueError):
            assess_context_revision(revision(trigger_evidence_refs=("ev-1", "ev-1")))

    def test_bool_version_is_invalid(self):
        bad = ContextSnapshot("ctx-1", True, "objects", "identify", ("shape",), (), ("same_scale",))
        with self.assertRaises(ValueError):
            assess_context_revision(revision(before=bad))

    def test_excluded_dimension_change_must_be_declared(self):
        before = ContextSnapshot("ctx-1", 1, "objects", "identify", ("shape",), ("function",), ("same_scale",))
        after = ContextSnapshot("ctx-1", 2, "objects", "identify", ("shape",), (), ("same_scale",))
        result = assess_context_revision(revision(before=before, after=after, kind=RevisionKind.REVISE, added_dimensions=(), changed_axes=()))
        self.assertEqual(result.status, RevisionStatus.UNDECLARED_CHANGE)
        self.assertIn("retired_excluded_dimensions", result.undeclared_changes)

    def test_contract_can_add_an_excluded_dimension(self):
        before = ContextSnapshot("ctx-1", 1, "objects", "identify", ("shape",), (), ("same_scale",))
        after = ContextSnapshot("ctx-1", 2, "objects", "identify", ("shape",), ("function",), ("same_scale",))
        result = assess_context_revision(revision(before=before, after=after, kind=RevisionKind.CONTRACT, added_dimensions=(), added_excluded_dimensions=("function",)))
        self.assertEqual(result.status, RevisionStatus.CONTEXT_CONTRACTED)

    def test_expand_can_remove_an_exclusion(self):
        before = ContextSnapshot("ctx-1", 1, "objects", "identify", ("shape",), ("function",), ("same_scale",))
        after = ContextSnapshot("ctx-1", 2, "objects", "identify", ("shape",), (), ("same_scale",))
        result = assess_context_revision(revision(before=before, after=after, kind=RevisionKind.EXPAND, added_dimensions=(), retired_excluded_dimensions=("function",)))
        self.assertEqual(result.status, RevisionStatus.CONTEXT_EXPANDED)

    def test_revise_without_change_is_noop(self):
        result = assess_context_revision(revision(kind=RevisionKind.REVISE, after=snapshot(version=2), added_dimensions=()))
        self.assertEqual(result.status, RevisionStatus.NO_OP)


if __name__ == "__main__":
    unittest.main()
