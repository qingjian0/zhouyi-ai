import unittest

from prototype.yixiang_contextual_transfer import (
    ContextualTransferContext,
    ContextTransferDecision,
    assess_contextual_transfer,
)


def context(cid, axes, refs=("evidence:1",)):
    return ContextualTransferContext(cid, tuple(axes.items()), tuple(refs))


class ContextualTransferTests(unittest.TestCase):
    def setUp(self):
        self.source = context("source", {
            "agent_capability": "trained",
            "task_or_goal": "catch_fish",
            "environment": "river",
            "time_phase": "day",
            "observer_standpoint": "shore",
            "reference_frame": "upstream",
            "process_path": "net_cast",
            "outcome": "fish_caught",
            "normative_basis": "none",
        })
        self.target = context("target", {
            "agent_capability": "trained",
            "task_or_goal": "catch_fish",
            "environment": "river",
            "time_phase": "day",
            "observer_standpoint": "shore",
            "reference_frame": "upstream",
            "process_path": "net_cast",
            "outcome": "fish_caught",
            "normative_basis": "none",
        }, refs=("evidence:2",))

    def assess(self, required_axes=("agent_capability", "task_or_goal", "environment")):
        return assess_contextual_transfer(
            self.source, self.target, required_axes=required_axes
        )

    def test_matching_required_context_axes_are_scope_supported(self):
        result = self.assess()
        self.assertEqual(result.decision, ContextTransferDecision.SCOPE_SUPPORTED)
        self.assertEqual(result.matched_axes, ("agent_capability", "task_or_goal", "environment"))
        self.assertTrue(result.scope_only)

    def test_same_object_different_agent_use_is_not_transferred(self):
        target = context("target", dict(self.target.axes, agent_capability="untrained"),
                         refs=("evidence:2",))
        result = assess_contextual_transfer(
            self.source, target, required_axes=("agent_capability", "task_or_goal")
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertEqual(result.mismatched_axes, ("agent_capability",))

    def test_same_outcome_different_process_does_not_claim_mechanism_identity(self):
        target = context("target", dict(self.target.axes, process_path="rod_fishing"),
                         refs=("evidence:2",))
        result = assess_contextual_transfer(
            self.source, target, required_axes=("outcome", "process_path")
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertEqual(result.matched_axes, ("outcome",))
        self.assertEqual(result.mismatched_axes, ("process_path",))

    def test_viewpoint_and_reference_frame_are_separate_axes(self):
        target = context("target", dict(self.target.axes, observer_standpoint="boat"))
        result = assess_contextual_transfer(
            self.source, target,
            required_axes=("observer_standpoint", "reference_frame"),
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertEqual(result.mismatched_axes, ("observer_standpoint",))

    def test_time_and_environment_are_separate_axes(self):
        target = context("target", dict(self.target.axes, time_phase="night"))
        result = assess_contextual_transfer(
            self.source, target, required_axes=("time_phase", "environment")
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertEqual(result.matched_axes, ("environment",))

    def test_missing_required_axis_abstains(self):
        source = context("source", {"task_or_goal": "catch_fish"})
        target = context("target", {"task_or_goal": "catch_fish"})
        result = assess_contextual_transfer(
            source, target, required_axes=("task_or_goal", "agent_capability")
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertEqual(result.missing_axes, ("agent_capability",))

    def test_missing_side_specific_evidence_abstains(self):
        target = context("target", dict(self.target.axes), refs=())
        result = assess_contextual_transfer(
            self.source, target, required_axes=("task_or_goal",)
        )
        self.assertEqual(result.decision, ContextTransferDecision.ABSTAIN)
        self.assertIn("MISSING_SIDE_SPECIFIC_EVIDENCE", result.reason_codes)

    def test_duplicate_or_malformed_axes_are_rejected(self):
        duplicate = ContextualTransferContext(
            "bad", (("task_or_goal", "a"), ("task_or_goal", "b")), ("evidence:1",)
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            assess_contextual_transfer(
                duplicate, self.target, required_axes=("task_or_goal",)
            )
        with self.assertRaisesRegex(ValueError, "required_axes"):
            self.assess(required_axes=())


if __name__ == "__main__":
    unittest.main()
