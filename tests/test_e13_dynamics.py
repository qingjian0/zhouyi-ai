import unittest

from prototype.e13_dynamics import (
    TransitionContractError, TransitionMap, TransitionRule, TransitionSystem,
    TrajectoryQuery, forecast_target_trajectory, observe_target_trajectory, rollout,
    select_discriminating_trajectory, update_trajectory_version_space,
    validate_trajectory,
)


class MultiStepDynamicsTests(unittest.TestCase):
    def setUp(self):
        # A two-state oscillator: feedback returns the system to its prior phase.
        self.source = TransitionSystem(
            "source-oscillator", ("phase",), ("tick",),
            (
                TransitionRule("tick", (("phase", "low"),), (("phase", "high"),)),
                TransitionRule("tick", (("phase", "high"),), (("phase", "low"),)),
            ),
        )
        self.target = TransitionSystem(
            "target-oscillator", ("stage",), ("advance",),
            (
                TransitionRule("advance", (("stage", "quiet"),), (("stage", "active"),)),
                TransitionRule("advance", (("stage", "active"),), (("stage", "quiet"),)),
            ),
        )
        self.mapping = TransitionMap(
            "oscillator-map",
            state_variables=(("phase", "stage"),),
            state_values=(("phase", "low", "quiet"), ("phase", "high", "active")),
            actions=(("tick", "advance"),),
            provenance="explicit cross-domain state mapping",
            rationale="test preservation of a feedback trajectory",
        )

    def test_full_multi_step_feedback_trajectory_is_preserved(self):
        actions = ("tick", "tick", "tick", "tick")
        predicted = forecast_target_trajectory(
            self.source, self.mapping, (("phase", "low"),), actions
        )
        observed = observe_target_trajectory(
            self.target, self.mapping, (("stage", "quiet"),), actions
        )
        result = validate_trajectory(predicted, observed)
        self.assertEqual(result.status, "VALID_FOR_TRAJECTORY")
        self.assertEqual(len(predicted.states), 5)

    def test_single_step_match_does_not_hide_later_feedback_divergence(self):
        divergent = TransitionSystem(
            "divergent-target", ("stage",), ("advance",),
            (
                TransitionRule("advance", (("stage", "quiet"),), (("stage", "active"),)),
                TransitionRule("advance", (("stage", "active"),), (("stage", "active"),)),
            ),
        )
        actions = ("tick", "tick", "tick")
        predicted = forecast_target_trajectory(
            self.source, self.mapping, (("phase", "low"),), actions
        )
        observed = observe_target_trajectory(
            divergent, self.mapping, (("stage", "quiet"),), actions
        )
        result = validate_trajectory(predicted, observed)
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.mismatch_step, 2)

    def test_missing_transition_is_unknown_not_guessed(self):
        partial = TransitionSystem(
            "partial", ("stage",), ("advance",),
            (TransitionRule("advance", (("stage", "quiet"),), (("stage", "active"),)),),
        )
        predicted = forecast_target_trajectory(
            self.source, self.mapping, (("phase", "low"),), ("tick", "tick")
        )
        observed = observe_target_trajectory(
            partial, self.mapping, (("stage", "quiet"),), ("tick", "tick")
        )
        self.assertEqual(predicted.status, "COMPLETE")
        self.assertEqual(observed.status, "NO_TRANSITION")
        self.assertEqual(validate_trajectory(predicted, observed).status, "UNKNOWN")

    def test_nondeterministic_transition_is_rejected(self):
        with self.assertRaises(TransitionContractError):
            TransitionSystem("bad", ("x",), ("go",), (
                TransitionRule("go", (("x", "a"),), (("x", "b"),)),
                TransitionRule("go", (("x", "a"),), (("x", "c"),)),
            ))

    def test_incomplete_state_assignment_is_rejected(self):
        with self.assertRaises(TransitionContractError):
            TransitionSystem("bad", ("x", "y"), ("go",), (
                TransitionRule("go", (("x", "a"),), (("x", "b"),)),
            ))

    def test_noninjective_state_value_map_is_rejected(self):
        with self.assertRaises(TransitionContractError):
            TransitionMap(
                "bad", (("phase", "stage"),),
                (("phase", "low", "same"), ("phase", "high", "same")),
                (("tick", "advance"),), "test provenance", "test rationale",
            )

    def test_rollout_reports_exact_missing_transition_step(self):
        result = rollout(self.target, (("stage", "quiet"),), ("advance", "unknown"))
        self.assertEqual(result.status, "NO_TRANSITION")
        self.assertEqual(result.stopped_at_step, 1)

    def test_active_trajectory_selection_uses_candidate_disagreement_without_target(self):
        alternative = TransitionMap(
            "alternative",
            state_variables=(("phase", "stage"),),
            state_values=(("phase", "low", "quiet"), ("phase", "high", "dormant")),
            actions=(("tick", "advance"),),
            provenance="independent alternative mapping",
            rationale="test active selection between competing trajectory hypotheses",
        )
        selection = select_discriminating_trajectory(
            self.source, (self.mapping, alternative),
            (("phase", "low"),),
            (TrajectoryQuery("one-step", ("tick",)),
             TrajectoryQuery("two-step", ("tick", "tick"))),
        )
        self.assertEqual(selection.status, "SELECTED")
        self.assertEqual(selection.selected.disagreement, 1.0)

    def test_incomplete_observed_trajectory_does_not_create_false_contradiction(self):
        update = update_trajectory_version_space(
            self.source, (self.mapping,), (("phase", "low"),),
            TrajectoryQuery("incomplete", ("tick",)),
            rollout(self.target, (("stage", "quiet"),), ("advance", "missing")),
        )
        self.assertEqual(update.status, "REJECTED_INCOMPLETE_EVIDENCE")
        self.assertEqual(update.retained_candidate_ids, ())

    def test_observed_target_trajectory_updates_candidate_version_space(self):
        alternative = TransitionMap(
            "alternative",
            state_variables=(("phase", "stage"),),
            state_values=(("phase", "low", "quiet"), ("phase", "high", "dormant")),
            actions=(("tick", "advance"),),
            provenance="independent alternative mapping",
            rationale="test evidence-based trajectory candidate rejection",
        )
        observed = rollout(
            self.target, (("stage", "quiet"),), ("advance",)
        )
        update = update_trajectory_version_space(
            self.source, (self.mapping, alternative),
            (("phase", "low"),), TrajectoryQuery("one-step", ("tick",)),
            observed,
        )
        self.assertEqual(update.status, "UPDATED")
        self.assertEqual(update.retained_candidate_ids, ("oscillator-map",))
        self.assertEqual(update.rejected_candidate_ids, ("alternative",))


if __name__ == "__main__":
    unittest.main()
