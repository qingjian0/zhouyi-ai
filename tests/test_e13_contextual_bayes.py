import unittest
from fractions import Fraction

from prototype.e13_stochastic import ObservationKernel, ObservationRule
from prototype.e13_contextual_stochastic import (
    ContextualTransitionRule, ContextualProbabilisticTransitionSystem,
)
from prototype.e13_contextual_bayes import (
    BayesianObservationCandidate, initialize_observation_belief,
    advance_observation_belief,
)


def make_system(name, transitions):
    rules = []
    for state, next_state, probability in transitions:
        rules.append(ContextualTransitionRule(
            (("mode", "fixed"),), "step", (("x", state),),
            (((("x", next_state),), Fraction(probability)),),
        ))
    return ContextualProbabilisticTransitionSystem(
        name, ("x",), ("mode",), ("step",), tuple(rules)
    )


def make_channel(name, rows):
    return ObservationKernel(name, tuple(
        ObservationRule((("x", state),), tuple(
            (symbol, Fraction(probability)) for symbol, probability in outputs
        ))
        for state, outputs in rows
    ))


class E13ContextualBayesianFilterTests(unittest.TestCase):
    def setUp(self):
        self.context = (("mode", "fixed"),)

    def candidate(self, candidate_id, transitions, channel):
        return BayesianObservationCandidate(
            candidate_id, make_system(candidate_id, transitions),
            (("sensor", channel),),
        )

    def test_exact_bayes_update_uses_likelihood_and_prior(self):
        c1 = self.candidate("m1", (("s", "u", 1),),
            make_channel("o1", (("s", (("start", 1),)),
                                ("u", (("seen", Fraction(3, 4)),
                                       ("miss", Fraction(1, 4)))))))
        c2 = self.candidate("m2", (("s", "v", 1),),
            make_channel("o2", (("s", (("start", 1),)),
                                ("v", (("seen", Fraction(1, 4)),
                                       ("miss", Fraction(3, 4)))))))
        init = initialize_observation_belief(
            (c1, c2), (("m1", Fraction(1, 2)), ("m2", Fraction(1, 2))),
            (((("x", "s"),), Fraction(1)),), self.context, "sensor", "start", "e0"
        )
        self.assertEqual(init.status, "UPDATED")
        update = advance_observation_belief(init.belief, "step", "sensor", "seen", "e1")
        self.assertEqual(update.status, "UPDATED")
        weights = {x.candidate_id: x.posterior_weight
                   for x in update.belief.candidate_beliefs}
        self.assertEqual(weights, {"m1": Fraction(3, 4), "m2": Fraction(1, 4)})
        self.assertEqual(update.predictive_evidence_probability, Fraction(1, 2))

    def test_sequential_filter_carries_latent_state_posterior(self):
        # Initial state is uncertain; identity dynamics make observations
        # temporally correlated. P(o0=zero)=P(o1=one)=1/2 marginally,
        # but P(zero, one)=0 under a perfect sensor.
        identity = make_system("identity", (("zero", "zero", 1),
                                            ("one", "one", 1)))
        perfect = make_channel("perfect", (
            ("zero", (("zero", 1),)), ("one", (("one", 1),))
        ))
        candidate = BayesianObservationCandidate("identity", identity,
                                                  (("sensor", perfect),))
        init = initialize_observation_belief(
            (candidate,), (("identity", Fraction(1)),),
            (((("x", "zero"),), Fraction(1, 2)),
             ((("x", "one"),), Fraction(1, 2))),
            self.context, "sensor", "zero", "e0"
        )
        self.assertEqual(init.status, "UPDATED")
        update = advance_observation_belief(
            init.belief, "step", "sensor", "one", "e1"
        )
        self.assertEqual(update.status, "CONTRADICTION")
        self.assertEqual(update.predictive_evidence_probability, Fraction(0))
        self.assertIsNone(update.belief)

    def test_missing_transition_support_returns_unknown_without_partial_update(self):
        partial = make_system("partial", (("s", "u", 1),))
        sensor = make_channel("sensor", (("s", (("start", 1),)),
                                         ("u", (("seen", 1),))))
        candidate = BayesianObservationCandidate("partial", partial,
                                                  (("sensor", sensor),))
        init = initialize_observation_belief(
            (candidate,), (("partial", Fraction(1)),),
            (((("x", "s"),), Fraction(1)),), self.context,
            "sensor", "start", "e0"
        )
        update = advance_observation_belief(
            init.belief, "step", "sensor", "seen", "e1"
        )
        self.assertEqual(update.status, "UPDATED")
        unknown = advance_observation_belief(
            update.belief, "step", "sensor", "seen", "e2"
        )
        self.assertEqual(unknown.status, "UNKNOWN")
        self.assertIsNone(unknown.belief)
        self.assertIn("MISSING_CONTEXTUAL_TRANSITION_ROW", unknown.reason)

    def test_missing_observation_support_returns_unknown(self):
        system = make_system("m", (("s", "u", 1),))
        sensor = make_channel("partial", (("s", (("start", 1),)),))
        candidate = BayesianObservationCandidate("m", system, (("sensor", sensor),))
        init = initialize_observation_belief(
            (candidate,), (("m", Fraction(1)),),
            (((("x", "s"),), Fraction(1)),), self.context,
            "sensor", "start", "e0"
        )
        update = advance_observation_belief(
            init.belief, "step", "sensor", "seen", "e1"
        )
        self.assertEqual(update.status, "UNKNOWN")
        self.assertIsNone(update.belief)

    def test_zero_likelihood_under_all_candidates_is_contradiction(self):
        system = make_system("m", (("s", "u", 1),))
        sensor = make_channel("sensor", (("s", (("start", 1),)),
                                         ("u", (("seen", 1),))))
        candidate = BayesianObservationCandidate("m", system, (("sensor", sensor),))
        init = initialize_observation_belief(
            (candidate,), (("m", Fraction(1)),),
            (((("x", "s"),), Fraction(1)),), self.context,
            "sensor", "impossible", "e0"
        )
        self.assertEqual(init.status, "CONTRADICTION")
        self.assertIsNone(init.belief)

    def test_duplicate_evidence_id_is_rejected(self):
        system = make_system("m", (("s", "u", 1),))
        sensor = make_channel("sensor", (("s", (("start", 1),)),
                                         ("u", (("seen", 1),))))
        candidate = BayesianObservationCandidate("m", system, (("sensor", sensor),))
        init = initialize_observation_belief(
            (candidate,), (("m", Fraction(1)),),
            (((("x", "s"),), Fraction(1)),), self.context,
            "sensor", "start", "e0"
        )
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVIDENCE_ID"):
            advance_observation_belief(init.belief, "step", "sensor", "seen", "e0")


if __name__ == "__main__":
    unittest.main()
