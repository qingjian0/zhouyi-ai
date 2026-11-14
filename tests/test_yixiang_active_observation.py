import unittest

from prototype.yixiang_active_observation import (
    HypothesisPrior, ObservationCandidate, score_observation, select_observation,
)


class ActiveObservationTests(unittest.TestCase):
    def setUp(self):
        self.priors = (
            HypothesisPrior("H1", 0.5),
            HypothesisPrior("H2", 0.5),
        )
        self.discriminating = ObservationCandidate(
            "inspect-season", "observe seasonal timing",
            (("H1", "early", 1.0), ("H1", "late", 0.0),
             ("H2", "early", 0.0), ("H2", "late", 1.0)),
        )
        self.uninformative = ObservationCandidate(
            "inspect-color", "observe a feature shared by both hypotheses",
            (("H1", "dark", 0.7), ("H1", "light", 0.3),
             ("H2", "dark", 0.7), ("H2", "light", 0.3)),
        )

    def test_discriminating_observation_has_one_bit_gain(self):
        score = score_observation(self.priors, self.discriminating)
        self.assertAlmostEqual(score.information_gain_bits, 1.0)
        self.assertAlmostEqual(score.expected_posterior_entropy_bits, 0.0)
        self.assertEqual(dict(score.expected_outcomes), {"early": 0.5, "late": 0.5})

    def test_shared_feature_has_zero_information_gain(self):
        score = score_observation(self.priors, self.uninformative)
        self.assertAlmostEqual(score.information_gain_bits, 0.0)

    def test_selection_prefers_information_and_penalizes_cost_risk_bias(self):
        expensive = ObservationCandidate(
            "expensive", "same discriminating measurement",
            self.discriminating.likelihoods, cost=10.0,
        )
        risky = ObservationCandidate(
            "risky", "same discriminating measurement",
            self.discriminating.likelihoods, risk=1.0,
        )
        selected = select_observation(
            self.priors, (self.uninformative, expensive, risky, self.discriminating)
        )
        self.assertEqual(selected.selected.observation_id, "inspect-season")
        self.assertEqual(selected.evidence_status, "prospective_only")

    def test_no_candidates_returns_none(self):
        self.assertIsNone(select_observation(self.priors, ()))

    def test_ties_are_deterministic(self):
        a = ObservationCandidate("a", "measure A", self.discriminating.likelihoods)
        b = ObservationCandidate("b", "measure B", self.discriminating.likelihoods)
        self.assertEqual(select_observation(self.priors, (b, a)).selected.observation_id, "a")

    def test_unknown_or_incomplete_hypothesis_distribution_is_rejected(self):
        bad = ObservationCandidate("bad", "incomplete", (("H1", "x", 1.0),))
        with self.assertRaisesRegex(ValueError, "every hypothesis"):
            score_observation(self.priors, bad)

    def test_every_hypothesis_must_explicitly_cover_every_outcome(self):
        incomplete = ObservationCandidate(
            "incomplete-outcomes", "missing outcome row",
            (("H1", "early", 1.0), ("H2", "late", 1.0)),
        )
        with self.assertRaisesRegex(ValueError, "every outcome explicitly"):
            score_observation(self.priors, incomplete)

    def test_likelihood_distribution_must_sum_to_one(self):
        bad = ObservationCandidate(
            "bad", "invalid distribution",
            (("H1", "x", 0.8), ("H1", "y", 0.8),
             ("H2", "x", 0.5), ("H2", "y", 0.5)),
        )
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            score_observation(self.priors, bad)

    def test_invalid_probabilities_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            score_observation((HypothesisPrior("H1", 1.2),), self.discriminating)
        with self.assertRaises(ValueError):
            select_observation(self.priors, (self.discriminating, self.discriminating))

    def test_bias_and_risk_are_bounded(self):
        bad = ObservationCandidate(
            "bad", "biased", self.discriminating.likelihoods, selection_bias=1.1
        )
        with self.assertRaisesRegex(ValueError, "selection_bias"):
            score_observation(self.priors, bad)


if __name__ == "__main__":
    unittest.main()
