import unittest

from prototype.yixiang_bidirectional_constraints import (
    LocalObservation, WholeHypothesis, assess_hypotheses,
)


class BidirectionalConstraintTests(unittest.TestCase):
    def test_local_evidence_ranks_competing_wholes(self):
        observations = (
            LocalObservation("shape", "round", 0.95, "text:1"),
            LocalObservation("motion", "rolling", 0.9, "text:2"),
        )
        hypotheses = (
            WholeHypothesis("wheel", {"shape": "round", "motion": "rolling"}),
            WholeHypothesis("block", {"shape": "square", "motion": "sliding"}),
        )
        result = assess_hypotheses(observations, hypotheses)
        self.assertEqual(result.winner.hypothesis_id, "wheel")
        self.assertEqual(result.winner.matched_features, ("motion", "shape"))
        self.assertEqual(len(result.ranked[1].residuals), 2)

    def test_whole_expectations_do_not_invent_missing_observations(self):
        result = assess_hypotheses(
            (LocalObservation("shape", "round", 0.8, "source:1"),),
            (WholeHypothesis("candidate", {"shape": "round", "material": "wood"}),),
        )
        self.assertEqual(result.winner.unobserved_features, ("material",))
        self.assertEqual(result.winner.residuals, ())

    def test_counterexample_is_preserved_as_residual(self):
        result = assess_hypotheses(
            (LocalObservation("temperature", "cold", 0.99, "source:counterexample"),),
            (WholeHypothesis("warm_state", {"temperature": "warm"}),),
        )
        residual = result.winner.residuals[0]
        self.assertEqual(residual.observed, "cold")
        self.assertEqual(residual.expected, "warm")
        self.assertEqual(residual.evidence_ref, "source:counterexample")

    def test_duplicate_observation_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_hypotheses(
                (
                    LocalObservation("shape", "round", 0.8, "s1"),
                    LocalObservation("shape", "square", 0.8, "s2"),
                ),
                (WholeHypothesis("candidate", {"shape": "round"}),),
            )

    def test_reliability_and_evidence_are_validated(self):
        with self.assertRaises(ValueError):
            assess_hypotheses(
                (LocalObservation("shape", "round", 0.0, "s1"),),
                (WholeHypothesis("candidate", {"shape": "round"}),),
            )

    def test_ties_are_deterministic(self):
        result = assess_hypotheses(
            (LocalObservation("shape", "round", 0.5, "s1"),),
            (
                WholeHypothesis("zeta", {"shape": "round"}),
                WholeHypothesis("alpha", {"shape": "round"}),
            ),
        )
        self.assertEqual(
            tuple(item.hypothesis_id for item in result.ranked),
            ("alpha", "zeta"),
        )


if __name__ == "__main__":
    unittest.main()
