import unittest

from prototype.active_operator_identification import (
    ActiveOperatorIdentifier,
    IdentificationError,
    OperatorHypothesis,
)
from prototype.operator_induction import OperatorProgram, Primitive


def program(kind):
    return OperatorProgram((Primitive(kind, 0),))


class ActiveIdentificationTests(unittest.TestCase):
    def test_positive_only_data_cannot_identify_identity_vs_abs(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", OperatorProgram(())),
                OperatorHypothesis("absolute", program("abs")),
            ],
            [(1,), (2,), (3,)],
        )
        self.assertEqual(identifier.status().status, "unidentifiable")
        self.assertIsNone(identifier.choose_experiment())

    def test_negative_query_separates_identity_and_abs(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", OperatorProgram(())),
                OperatorHypothesis("absolute", program("abs")),
            ],
            [(-3,), (2,)],
        )
        experiment = identifier.choose_experiment()
        self.assertEqual(experiment.before, (-3.0,))
        status = identifier.observe(experiment.before, (-3,), source_id="test-oracle")
        self.assertEqual(status.status, "identified")
        self.assertEqual(status.surviving_hypotheses, ("identity",))
        self.assertEqual(identifier.records[0].source_id, "test-oracle")
        self.assertEqual(len(identifier.records[0].version_space_digest), 64)

    def test_max_disagreement_prefers_balanced_partition(self):
        hypotheses = [
            OperatorHypothesis("h0", OperatorProgram(())),
            OperatorHypothesis("h1", program("neg")),
            OperatorHypothesis("h2", program("abs")),
            OperatorHypothesis("h3", program("neg")),
        ]
        identifier = ActiveOperatorIdentifier(hypotheses, [(-2,), (0,)])
        ranked = identifier.rank_experiments()
        self.assertEqual(ranked[0].before, (-2.0,))
        self.assertAlmostEqual(ranked[0].entropy_bits, 1.0)

    def test_budget_exhaustion_is_explicit(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", OperatorProgram(())),
                OperatorHypothesis("absolute", program("abs")),
            ],
            [(-1,), (1,)],
            max_experiments=0,
        )
        self.assertEqual(identifier.status().status, "budget_exhausted")
        self.assertIsNone(identifier.choose_experiment())

    def test_conflicting_duplicate_observation_does_not_mutate_state(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", OperatorProgram(())),
                OperatorHypothesis("negative", program("neg")),
            ],
            [(-2,), (2,)],
        )
        experiment = identifier.choose_experiment()
        identifier.observe(experiment.before, (-2,))
        count = len(identifier.observations)
        with self.assertRaises(IdentificationError):
            identifier.observe(experiment.before, (2,))
        self.assertEqual(len(identifier.observations), count)
        self.assertEqual(len(identifier.hypotheses), 1)

    def test_unexplained_observation_preserves_version_space(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", OperatorProgram(())),
                OperatorHypothesis("negative", program("neg")),
            ],
            [(-2,), (2,)],
        )
        experiment = identifier.choose_experiment()
        with self.assertRaises(IdentificationError):
            identifier.observe(experiment.before, (999,))
        self.assertEqual(len(identifier.hypotheses), 2)
        self.assertEqual(len(identifier.observations), 0)


if __name__ == "__main__":
    unittest.main()
