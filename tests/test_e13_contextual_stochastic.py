import unittest
from fractions import Fraction

from prototype.e13_stochastic import StochasticContractError
from prototype.e13_contextual_stochastic import (
    ContextualTransitionRule, ContextualProbabilisticTransitionSystem,
    ContextualKernelMap, ContextualTrajectoryCase,
    propagate_contextual_distribution, validate_contextual_trajectory,
)


class E13ContextualMechanismTests(unittest.TestCase):
    def test_same_state_action_has_context_dependent_transition(self):
        system = ContextualProbabilisticTransitionSystem("conditional", ("x",), ("weather",),
            ("act",), (
                ContextualTransitionRule((("weather", "dry"),), "act", (("x", "low"),),
                    (((("x", "high"),), Fraction(1)),)),
                ContextualTransitionRule((("weather", "wet"),), "act", (("x", "low"),),
                    (((("x", "low"),), Fraction(1)),)),
            ))
        dry = propagate_contextual_distribution(system, (("x", "low"),), ("act",),
                                                 (("weather", "dry"),))[-1]
        wet = propagate_contextual_distribution(system, (("x", "low"),), ("act",),
                                                 (("weather", "wet"),))[-1]
        self.assertEqual(dry, (((("x", "high"),), Fraction(1)),))
        self.assertEqual(wet, (((("x", "low"),), Fraction(1)),))

    def test_context_is_not_allowed_as_endogenous_state(self):
        with self.assertRaisesRegex(StochasticContractError, "CONTEXT_MUST_NOT_BE_ENDOGENOUS_STATE"):
            ContextualProbabilisticTransitionSystem("bad", ("weather",), ("weather",),
                ("act",), ())

    def test_context_is_fixed_across_multistep_rollout(self):
        system = ContextualProbabilisticTransitionSystem("fixed", ("x",), ("mode",),
            ("step",), (
                ContextualTransitionRule((("mode", "A"),), "step", (("x", "a"),),
                    (((("x", "b"),), Fraction(1)),)),
                ContextualTransitionRule((("mode", "A"),), "step", (("x", "b"),),
                    (((("x", "c"),), Fraction(1)),)),
                ContextualTransitionRule((("mode", "B"),), "step", (("x", "a"),),
                    (((("x", "a"),), Fraction(1)),)),
            ))
        history = propagate_contextual_distribution(system, (("x", "a"),),
                                                     ("step", "step"), (("mode", "A"),))
        self.assertEqual(history[-1], (((("x", "c"),), Fraction(1)),))

    def _mapped_systems(self):
        source = ContextualProbabilisticTransitionSystem("src", ("level",), ("climate",),
            ("push",), (
                ContextualTransitionRule((("climate", "hot"),), "push", (("level", "low"),),
                    (((("level", "high"),), Fraction(1)),)),
                ContextualTransitionRule((("climate", "hot"),), "push", (("level", "high"),),
                    (((("level", "high"),), Fraction(1)),)),
            ))
        target = ContextualProbabilisticTransitionSystem("tgt", ("charge",), ("regime",),
            ("drive",), (
                ContextualTransitionRule((("regime", "warm"),), "drive", (("charge", "empty"),),
                    (((("charge", "full"),), Fraction(1)),)),
                ContextualTransitionRule((("regime", "warm"),), "drive", (("charge", "full"),),
                    (((("charge", "empty"),), Fraction(1)),)),
            ))
        mapping = ContextualKernelMap(
            (("level", "charge"),),
            (("level", "low", "empty"), ("level", "high", "full")),
            (("climate", "regime"),),
            (("climate", "hot", "warm"),),
            (("push", "drive"),),
        )
        case = ContextualTrajectoryCase("case", (("level", "low"),),
            (("charge", "empty"),), (("climate", "hot"),), (("regime", "warm"),),
            ("push", "push"))
        return source, target, mapping, case

    def test_cross_domain_contextual_trajectory_passes(self):
        source, target, mapping, case = self._mapped_systems()
        report = validate_contextual_trajectory(source, target, mapping, case)
        self.assertEqual(report.status, "PASS_ON_SUPPLIED_CONTEXTUAL_TRAJECTORY")
        self.assertTrue(all(x.total_variation_distance == 0 for x in report.steps))

    def test_misaligned_context_is_unknown(self):
        source, target, mapping, case = self._mapped_systems()
        wrong = ContextualTrajectoryCase(case.case_id, case.source_initial, case.target_initial,
            case.source_context, (("regime", "cold"),), case.source_actions)
        report = validate_contextual_trajectory(source, target, mapping, wrong)
        self.assertEqual(report.status, "UNKNOWN_CONTEXT_ALIGNMENT")

    def test_missing_contextual_transition_support_is_unknown(self):
        source, target, mapping, case = self._mapped_systems()
        partial = ContextualProbabilisticTransitionSystem("partial", ("charge",), ("regime",),
            ("drive",), (
                ContextualTransitionRule((("regime", "warm"),), "drive", (("charge", "full"),),
                    (((("charge", "full"),), Fraction(1)),)),
            ))
        report = validate_contextual_trajectory(source, partial, mapping, case)
        self.assertEqual(report.status, "UNKNOWN_TARGET_CONTEXT_SUPPORT")

    def test_context_mapping_must_be_explicit_and_complete(self):
        source, target, mapping, case = self._mapped_systems()
        bad = ContextualKernelMap(mapping.state_variables, mapping.state_values,
            (), mapping.context_values, mapping.actions)
        with self.assertRaisesRegex(StochasticContractError,
                                    "CONTEXT_VARIABLE_MAP_MUST_BE_COMPLETE_BIJECTION"):
            validate_contextual_trajectory(source, target, bad, case)


if __name__ == "__main__":
    unittest.main()
