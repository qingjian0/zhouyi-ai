import unittest
from fractions import Fraction

from prototype.e13_stochastic import ObservationKernel, ObservationRule
from prototype.e13_contextual_stochastic import (
    ContextualTransitionRule, ContextualProbabilisticTransitionSystem,
)
from prototype.e13_contextual_bayes import (
    BayesianObservationCandidate, initialize_observation_belief,
)
from prototype.e13_contextual_eig import (
    BayesianExperimentQuery, select_bayesian_experiment,
)


def make_system(name, outcomes):
    rules = tuple(ContextualTransitionRule(
        (("mode", "fixed"),), "step", (("x", state),),
        tuple(((("x", next_state),), Fraction(probability))
              for next_state, probability in next_states),
    ) for state, next_states in outcomes)
    return ContextualProbabilisticTransitionSystem(
        name, ("x",), ("mode",), ("step",), rules
    )


def make_channel(name, rows):
    return ObservationKernel(name, tuple(
        ObservationRule((("x", state),), tuple(
            (symbol, Fraction(probability)) for symbol, probability in outputs
        ))
        for state, outputs in rows
    ))


class E13BayesianEIGTests(unittest.TestCase):
    def belief(self, candidates, initial_obs="start"):
        return initialize_observation_belief(
            candidates,
            tuple((candidate.candidate_id, Fraction(1, len(candidates)))
                  for candidate in candidates),
            (((("x", "s"),), Fraction(1)),),
            (("mode", "fixed"),), "initial", initial_obs, "e0"
        ).belief

    def test_perfectly_discriminating_query_has_one_bit_eig(self):
        left = BayesianObservationCandidate(
            "left", make_system("left", (("s", (("u", 1),)),)),
            (("initial", make_channel("init", (("s", (("start", 1),)),))),
             ("sensor", make_channel("left-sensor", (("u", (("L", 1),)),)))),
            "mechanism-left", "channel-shared",
        )
        right = BayesianObservationCandidate(
            "right", make_system("right", (("s", (("v", 1),)),)),
            (("initial", make_channel("init", (("s", (("start", 1),)),))),
             ("sensor", make_channel("right-sensor", (("v", (("R", 1),)),)))),
            "mechanism-right", "channel-shared",
        )
        belief = self.belief((left, right))
        result = select_bayesian_experiment(
            belief, (BayesianExperimentQuery("q", ("step",), ("sensor",)),)
        )
        self.assertEqual(result.status, "SELECTED")
        self.assertAlmostEqual(result.selected.expected_information_gain_bits, 1.0)

    def test_identical_observation_forecasts_have_zero_eig(self):
        system = make_system("same", (("s", (("u", 1),)),))
        shared = make_channel("shared", (("s", (("start", 1),)),
                                         ("u", (("same", 1),))))
        candidates = (
            BayesianObservationCandidate("a", system,
                (("initial", shared), ("sensor", shared)), "m1", "c"),
            BayesianObservationCandidate("b", system,
                (("initial", shared), ("sensor", shared)), "m2", "c"),
        )
        result = select_bayesian_experiment(
            self.belief(candidates),
            (BayesianExperimentQuery("q", ("step",), ("sensor",)),)
        )
        self.assertEqual(result.status, "NO_EXPECTED_INFORMATION_GAIN")
        self.assertAlmostEqual(result.selected.expected_information_gain_bits, 0.0)

    def test_information_target_separates_mechanism_and_channel(self):
        system = make_system("same", (("s", (("u", 1),)),))
        initial = make_channel("init", (("s", (("start", 1),)),))
        c1 = BayesianObservationCandidate(
            "a", system,
            (("initial", initial),
             ("sensor", make_channel("sensor-a", (("u", (("A", 1),)),)))),
            "same-mechanism", "channel-a",
        )
        c2 = BayesianObservationCandidate(
            "b", system,
            (("initial", initial),
             ("sensor", make_channel("sensor-b", (("u", (("B", 1),)),)))),
            "same-mechanism", "channel-b",
        )
        belief = self.belief((c1, c2))
        mechanism = select_bayesian_experiment(
            belief, (BayesianExperimentQuery("m", ("step",), ("sensor",),
                                             target="mechanism"),)
        )
        channel = select_bayesian_experiment(
            belief, (BayesianExperimentQuery("c", ("step",), ("sensor",),
                                             target="channel"),)
        )
        self.assertAlmostEqual(
            mechanism.selected.expected_information_gain_bits, 0.0
        )
        self.assertAlmostEqual(
            channel.selected.expected_information_gain_bits, 1.0
        )

    def test_multistep_forecast_is_joint_sequence_distribution(self):
        # A single latent bit persists. The sequence (zero, one) is impossible
        # after observing zero initially, even though one is a valid marginal
        # observation under the unconditioned initial distribution.
        identity = make_system("identity", (
            ("zero", (("zero", 1),)), ("one", (("one", 1),)),
        ))
        sensor = make_channel("sensor", (
            ("zero", (("zero", 1),)), ("one", (("one", 1),)),
        ))
        candidate = BayesianObservationCandidate(
            "id", identity, (("initial", sensor), ("sensor", sensor)), "m", "c"
        )
        # Initial belief after observing zero has only latent state zero.
        belief = initialize_observation_belief(
            (candidate,), (("id", Fraction(1)),),
            (((("x", "zero"),), Fraction(1, 2)),
             ((("x", "one"),), Fraction(1, 2))),
            (("mode", "fixed"),), "initial", "zero", "e0"
        ).belief
        result = select_bayesian_experiment(
            belief, (BayesianExperimentQuery("q", ("step", "step"),
                                             ("sensor", "sensor")),)
        )
        forecast = result.selected.forecasts[0]
        self.assertEqual(forecast.probabilities, ((("zero", "zero"), Fraction(1)),))

    def test_missing_support_is_unknown(self):
        partial = make_system("partial", (("s", (("u", 1),)),))
        initial = make_channel("init", (("s", (("start", 1),)),))
        incomplete = make_channel("sensor", (("u", (("seen", 1),)),))
        candidate = BayesianObservationCandidate(
            "partial", partial, (("initial", initial), ("sensor", incomplete))
        )
        belief = self.belief((candidate,))
        result = select_bayesian_experiment(
            belief, (BayesianExperimentQuery("q", ("step", "step"),
                                             ("sensor", "sensor")),)
        )
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_QUERY")
        self.assertEqual(result.rejected[0][1], "UNKNOWN_INCOMPLETE_PREDICTIVE_SUPPORT")

    def test_hard_authorization_risk_and_cost_gates(self):
        system = make_system("m", (("s", (("u", 1),)),))
        initial = make_channel("init", (("s", (("start", 1),)),))
        sensor = make_channel("sensor", (("u", (("seen", 1),)),))
        candidate = BayesianObservationCandidate(
            "m", system, (("initial", initial), ("sensor", sensor)), "m", "c"
        )
        queries = (
            BayesianExperimentQuery("unauthorized", ("step",), ("sensor",),
                                    authorized=False),
            BayesianExperimentQuery("risky", ("step",), ("sensor",),
                                    risk=Fraction(1)),
            BayesianExperimentQuery("costly", ("step",), ("sensor",),
                                    cost=Fraction(5)),
        )
        result = select_bayesian_experiment(
            self.belief((candidate,)), queries,
            max_risk=Fraction(1, 2), max_cost=Fraction(2)
        )
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_QUERY")
        self.assertEqual(result.rejected, (
            ("unauthorized", "UNAUTHORIZED"),
            ("risky", "RISK_LIMIT_EXCEEDED"),
            ("costly", "COST_LIMIT_EXCEEDED"),
        ))

    def test_target_requires_explicit_hypothesis_labels(self):
        system = make_system("m", (("s", (("u", 1),)),))
        initial = make_channel("init", (("s", (("start", 1),)),))
        sensor = make_channel("sensor", (("u", (("seen", 1),)),))
        candidate = BayesianObservationCandidate(
            "m", system, (("initial", initial), ("sensor", sensor))
        )
        result = select_bayesian_experiment(
            self.belief((candidate,)),
            (BayesianExperimentQuery("q", ("step",), ("sensor",),
                                     target="mechanism"),)
        )
        self.assertEqual(result.status, "NO_SAFE_COMPLETE_QUERY")
        self.assertEqual(result.rejected[0][1], "MISSING_MECHANISM_HYPOTHESIS_ID")


if __name__ == "__main__":
    unittest.main()
