import unittest
from fractions import Fraction

from prototype.e13_stochastic import ObservationKernel, ObservationRule
from prototype.e13_contextual_stochastic import (
    ContextualTransitionRule, ContextualProbabilisticTransitionSystem,
)
from prototype.e13_contextual_observation import (
    ContextualObservationCandidate, ContextualObservationQuery,
    project_contextual_observation_trajectory,
    select_contextual_observation_query,
)


def system(name, a_outcome, b_outcome):
    return ContextualProbabilisticTransitionSystem(
        name, ("x",), ("mode",), ("a", "b"), (
            ContextualTransitionRule((("mode", "fixed"),), "a", (("x", "s"),),
                ((((("x", a_outcome)),), Fraction(1)),)),
            ContextualTransitionRule((("mode", "fixed"),), "b", (("x", "s"),),
                ((((("x", b_outcome)),), Fraction(1)),)),
        ),
    )


def channel(name, mapping):
    return ObservationKernel(name, tuple(
        ObservationRule((("x", state),), ((symbol, Fraction(1)),))
        for state, symbol in mapping
    ))


class E13ContextualObservationTests(unittest.TestCase):
    def setUp(self):
        self.initial = (("x", "s"),)
        self.context = (("mode", "fixed"),)
        self.query = ContextualObservationQuery(
            "q", "sensor", ("b",), True, Fraction(0), Fraction(1)
        )

    def test_different_latent_mechanisms_can_be_unobservable(self):
        left = system("left", "u", "u")
        right = system("right", "u", "v")
        # Both latent states collapse to the same sensor symbol.
        shared = channel("coarse", (("s", "same"), ("u", "same"), ("v", "same")))
        candidates = (
            ContextualObservationCandidate("left", left, (("sensor", shared),)),
            ContextualObservationCandidate("right", right, (("sensor", shared),)),
        )
        result = select_contextual_observation_query(
            candidates, (self.query,), self.initial, self.context
        )
        self.assertEqual(result.status, "OBSERVATIONALLY_NON_DISCRIMINATING")
        self.assertEqual(result.selected.pairwise_observation_tv_disagreement, Fraction(0))

    def test_same_mechanism_different_channels_are_observational_not_mechanism_difference(self):
        same = system("same", "u", "u")
        channel_a = channel("a", (("s", "zero"), ("u", "zero")))
        channel_b = channel("b", (("s", "zero"), ("u", "one")))
        candidates = (
            ContextualObservationCandidate("model-a", same, (("sensor", channel_a),)),
            ContextualObservationCandidate("model-b", same, (("sensor", channel_b),)),
        )
        result = select_contextual_observation_query(
            candidates, (self.query,), self.initial, self.context
        )
        self.assertEqual(result.status, "SELECTED")
        self.assertEqual(result.selected.pairwise_observation_tv_disagreement, Fraction(1))

    def test_joint_candidates_can_be_separated_by_sensor_choice(self):
        left, right = system("left", "u", "u"), system("right", "u", "v")
        coarse = channel("coarse", (("s", "same"), ("u", "same"), ("v", "same")))
        fine = channel("fine", (("s", "s"), ("u", "u"), ("v", "v")))
        candidates = (
            ContextualObservationCandidate("left", left,
                (("coarse", coarse), ("fine", fine))),
            ContextualObservationCandidate("right", right,
                (("coarse", coarse), ("fine", fine))),
        )
        queries = (
            ContextualObservationQuery("coarse-query", "coarse", ("b",), True,
                                       Fraction(0), Fraction(0)),
            ContextualObservationQuery("fine-query", "fine", ("b",), True,
                                       Fraction(0), Fraction(0)),
        )
        result = select_contextual_observation_query(
            candidates, queries, self.initial, self.context
        )
        self.assertEqual(result.selected.query_id, "fine-query")
        self.assertEqual(result.selected.pairwise_observation_tv_disagreement, Fraction(1))

    def test_missing_observation_support_is_unknown(self):
        incomplete = channel("incomplete", (("s", "s"), ("u", "u")))
        candidates = (
            ContextualObservationCandidate("left", system("left", "u", "u"),
                                           (("sensor", incomplete),)),
            ContextualObservationCandidate("right", system("right", "u", "v"),
                                           (("sensor", incomplete),)),
        )
        result = select_contextual_observation_query(
            candidates, (self.query,), self.initial, self.context
        )
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_OBSERVATION_QUERY")
        self.assertEqual(result.rejected[0][1], "UNKNOWN_INCOMPLETE_OBSERVATION_FORECAST")

    def test_multistep_projection_happens_at_every_step(self):
        model = system("m", "u", "v")
        sensor = channel("sensor", (("s", "S"), ("u", "U"), ("v", "V")))
        observed = project_contextual_observation_trajectory(
            model, sensor, self.initial, ("b", "a"), self.context
        )
        self.assertEqual(observed, (
            (("S", Fraction(1)),),
            (("V", Fraction(1)),),
            (("U", Fraction(1)),),
        ))

    def test_hard_authorization_risk_and_cost_gates(self):
        candidates = (
            ContextualObservationCandidate("left", system("left", "u", "u"),
                (("sensor", channel("s", (("s", "s"), ("u", "u"), ("v", "v")))),)),
            ContextualObservationCandidate("right", system("right", "u", "v"),
                (("sensor", channel("s", (("s", "s"), ("u", "u"), ("v", "v")))),)),
        )
        queries = (
            ContextualObservationQuery("unauthorized", "sensor", ("b",), False,
                                       Fraction(0), Fraction(0)),
            ContextualObservationQuery("risky", "sensor", ("b",), True,
                                       Fraction(1), Fraction(0)),
            ContextualObservationQuery("costly", "sensor", ("b",), True,
                                       Fraction(0), Fraction(5)),
        )
        result = select_contextual_observation_query(
            candidates, queries, self.initial, self.context,
            max_risk=Fraction(1, 2), max_cost=Fraction(2)
        )
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_OBSERVATION_QUERY")
        self.assertEqual(result.rejected, (
            ("unauthorized", "UNAUTHORIZED"),
            ("risky", "RISK_LIMIT_EXCEEDED"),
            ("costly", "COST_LIMIT_EXCEEDED"),
        ))

    def test_selector_returns_no_latent_state_payload(self):
        candidates = (
            ContextualObservationCandidate("left", system("left", "u", "u"),
                (("sensor", channel("s", (("s", "s"), ("u", "u"), ("v", "v")))),)),
            ContextualObservationCandidate("right", system("right", "u", "v"),
                (("sensor", channel("s", (("s", "s"), ("u", "u"), ("v", "v")))),)),
        )
        result = select_contextual_observation_query(
            candidates, (self.query,), self.initial, self.context
        )
        forecast = result.selected.forecasts[0]
        self.assertFalse(hasattr(forecast, "trajectory"))
        self.assertTrue(hasattr(forecast, "observed_trajectory"))


if __name__ == "__main__":
    unittest.main()
