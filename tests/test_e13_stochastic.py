import unittest
from fractions import Fraction
from prototype.e13_stochastic import (
    ObservationKernel, ObservationRule, ProbabilisticTransitionRule,
    ProbabilisticTransitionSystem, RiskAwareQuery, StochasticContractError,
    jensen_shannon_divergence, observation_distribution,
    propagate_latent_distribution, run_stochastic_trajectory,
    select_risk_aware_query,
)


class E13StochasticMechanismTests(unittest.TestCase):
    def setUp(self):
        self.system = ProbabilisticTransitionSystem("coin", ("x",), ("flip",), (
            ProbabilisticTransitionRule("flip", (("x", "start"),), (
                ((("x", "heads"),), Fraction(1, 2)),
                ((("x", "tails"),), Fraction(1, 2)),
            )),
        ))
        self.channel = ObservationKernel("identity", (
            ObservationRule((("x", "start"),), (("start", Fraction(1)),)),
            ObservationRule((("x", "heads"),), (("heads", Fraction(1)),)),
            ObservationRule((("x", "tails"),), (("tails", Fraction(1)),)),
        ))

    def test_rows_must_sum_to_one(self):
        with self.assertRaises(StochasticContractError):
            ProbabilisticTransitionSystem("bad", ("x",), ("go",), (
                ProbabilisticTransitionRule("go", (("x", "a"),),
                    (((("x", "b"),), Fraction(1, 3)),)),
            ))

    def test_negative_probability_rejected(self):
        with self.assertRaises(StochasticContractError):
            ProbabilisticTransitionSystem("bad", ("x",), ("go",), (
                ProbabilisticTransitionRule("go", (("x", "a"),), (
                    ((("x", "b"),), Fraction(-1, 2)),
                    ((("x", "c"),), Fraction(3, 2)),
                )),
            ))

    def test_float_probability_rejected(self):
        with self.assertRaises(StochasticContractError):
            ProbabilisticTransitionSystem("bad", ("x",), ("go",), (
                ProbabilisticTransitionRule("go", (("x", "a"),),
                    (((("x", "b"),), 0.5), ((("x", "c"),), 0.5))),
            ))

    def test_multiple_outcomes_exactly_normalized(self):
        result = propagate_latent_distribution(self.system, (("x", "start"),), ("flip",))[-1]
        self.assertEqual(result, (
            ((("x", "heads"),), Fraction(1, 2)),
            ((("x", "tails"),), Fraction(1, 2)),
        ))

    def test_observation_noise_does_not_change_latent_dynamics(self):
        noisy = ObservationKernel("noisy", (
            ObservationRule((("x", "start"),), (("start", Fraction(1)),)),
            ObservationRule((("x", "heads"),), (("heads", Fraction(3, 4)), ("tails", Fraction(1, 4)))),
            ObservationRule((("x", "tails"),), (("heads", Fraction(1, 4)), ("tails", Fraction(3, 4)))),
        ))
        latent = propagate_latent_distribution(self.system, (("x", "start"),), ("flip",))[-1]
        observed = observation_distribution(latent, noisy)
        self.assertEqual(sum((p for _, p in latent), Fraction(0)), 1)
        self.assertEqual(observed, (("heads", Fraction(1, 2)), ("tails", Fraction(1, 2))))

    def test_deterministic_mechanism_can_have_noisy_sensor(self):
        deterministic = ProbabilisticTransitionSystem("det", ("x",), ("go",), (
            ProbabilisticTransitionRule("go", (("x", "start"),),
                (((("x", "heads"),), Fraction(1)),)),
        ))
        noisy = ObservationKernel("sensor", (
            ObservationRule((("x", "start"),), (("start", Fraction(1)),)),
            ObservationRule((("x", "heads"),), (("heads", Fraction(3, 4)), ("tails", Fraction(1, 4)))),
        ))
        result = run_stochastic_trajectory(deterministic, noisy, (("x", "start"),), ("go",))
        self.assertEqual(result[-1].latent, (((("x", "heads"),), Fraction(1)),))
        self.assertEqual(result[-1].observed, (("heads", Fraction(3, 4)), ("tails", Fraction(1, 4))))

    def test_zero_probability_is_not_raised(self):
        system = ProbabilisticTransitionSystem("zero", ("x",), ("go",), (
            ProbabilisticTransitionRule("go", (("x", "a"),), (
                ((("x", "b"),), Fraction(1)), ((("x", "c"),), Fraction(0)),
            )),
        ))
        self.assertEqual(propagate_latent_distribution(system, (("x", "a"),), ("go",))[-1],
                         (((("x", "b"),), Fraction(1)),))

    def test_missing_row_fails_closed(self):
        with self.assertRaisesRegex(StochasticContractError, "MISSING_TRANSITION_ROW"):
            propagate_latent_distribution(self.system, (("x", "heads"),), ("flip",))

    def test_multistep_distribution_normalized(self):
        system = ProbabilisticTransitionSystem("cycle", ("x",), ("go",), (
            ProbabilisticTransitionRule("go", (("x", "a"),), (
                ((("x", "a"),), Fraction(1, 2)), ((("x", "b"),), Fraction(1, 2)))),
            ProbabilisticTransitionRule("go", (("x", "b"),), (
                ((("x", "a"),), Fraction(1, 4)), ((("x", "b"),), Fraction(3, 4)))),
        ))
        for dist in propagate_latent_distribution(system, (("x", "a"),), ("go",) * 3):
            self.assertEqual(sum((p for _, p in dist), Fraction(0)), 1)

    def test_js_identity(self):
        p = (("a", Fraction(1, 2)), ("b", Fraction(1, 2)))
        self.assertAlmostEqual(jensen_shannon_divergence(p, p), 0.0)

    def test_hard_risk_gate_before_ranking(self):
        unsafe = RiskAwareQuery("unsafe", (
            ("m1", (("a", Fraction(1)),)), ("m2", (("b", Fraction(1)),))),
            True, Fraction(9, 10), Fraction(0))
        safe = RiskAwareQuery("safe", (
            ("m1", (("a", Fraction(1)),)), ("m2", (("b", Fraction(1)),))),
            True, Fraction(1, 10), Fraction(1, 2))
        result = select_risk_aware_query((unsafe, safe), ("m1", "m2"),
                                         max_risk=Fraction(1, 4))
        self.assertEqual(result.selected.query_id, "safe")
        self.assertIn(("unsafe", "HARD_RISK_LIMIT_EXCEEDED"), result.rejected)

    def test_unauthorized_query_rejected(self):
        query = RiskAwareQuery("forbidden", (
            ("m1", (("a", Fraction(1)),)), ("m2", (("b", Fraction(1)),))),
            False, Fraction(0), Fraction(0))
        result = select_risk_aware_query((query,), ("m1", "m2"),
                                         max_risk=Fraction(1))
        self.assertEqual(result.status, "NO_SAFE_QUERY")
        self.assertEqual(result.rejected, (("forbidden", "UNAUTHORIZED"),))


if __name__ == "__main__":
    unittest.main()
