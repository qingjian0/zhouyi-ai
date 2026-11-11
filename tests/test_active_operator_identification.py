import unittest

from prototype.active_operator_identification import (
    ActiveOperatorIdentifier,
    IdentificationError,
    OperatorHypothesis,
)


class SimpleProgram:
    def __init__(self, operation=None):
        self.operation = operation

    def apply(self, state):
        values = list(float(value) for value in state)
        if self.operation == "abs":
            values[0] = abs(values[0])
        elif self.operation == "neg":
            values[0] = -values[0]
        return tuple(values)


def program(kind):
    return SimpleProgram(kind)


class ActiveIdentificationTests(unittest.TestCase):
    def test_positive_only_data_cannot_identify_identity_vs_abs(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("absolute", program("abs")),
            ],
            [(1,), (2,), (3,)],
        )
        self.assertEqual(identifier.status().status, "unidentifiable")
        self.assertIsNone(identifier.choose_experiment())

    def test_negative_query_separates_identity_and_abs(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
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
            OperatorHypothesis("h0", SimpleProgram()),
            OperatorHypothesis("h1", program("neg")),
            OperatorHypothesis("h2", program("abs")),
            OperatorHypothesis("h3", SimpleProgram()),
        ]
        identifier = ActiveOperatorIdentifier(hypotheses, [(-2,), (0,)])
        ranked = identifier.rank_experiments()
        self.assertEqual(ranked[0].before, (-2.0,))
        self.assertAlmostEqual(ranked[0].entropy_bits, 1.0)

    def test_budget_exhaustion_is_explicit(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
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
                OperatorHypothesis("identity", SimpleProgram()),
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
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("negative", program("neg")),
            ],
            [(-2,), (2,)],
        )
        experiment = identifier.choose_experiment()
        with self.assertRaises(IdentificationError):
            identifier.observe(experiment.before, (999,))
        self.assertEqual(len(identifier.hypotheses), 2)
        self.assertEqual(len(identifier.observations), 0)
        self.assertEqual(len(identifier.rejected_observations), 1)
        self.assertEqual(identifier.rejected_observations[0].after, (999.0,))

    def test_tolerance_partition_is_independent_of_hypothesis_id_order(self):
        class ConstantProgram:
            def __init__(self, value):
                self.value = value
            def apply(self, state):
                return (self.value,)

        first = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("a", ConstantProgram(0.0)),
                OperatorHypothesis("b", ConstantProgram(0.75)),
                OperatorHypothesis("c", ConstantProgram(1.5)),
            ],
            [(0.0,)],
            tolerance=1.0,
        )
        second = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("a", ConstantProgram(1.5)),
                OperatorHypothesis("b", ConstantProgram(0.0)),
                OperatorHypothesis("c", ConstantProgram(0.75)),
            ],
            [(0.0,)],
            tolerance=1.0,
        )
        first_partition = first.rank_experiments()[0].partitions
        second_partition = second.rank_experiments()[0].partitions
        self.assertEqual(
            [len(ids) for _, ids in first_partition],
            [len(ids) for _, ids in second_partition],
        )
        self.assertEqual(
            [output for output, _ in first_partition],
            [(0.0,), (1.5,)],
        )
        self.assertEqual(
            [output for output, _ in second_partition],
            [(0.0,), (1.5,)],
        )
        self.assertEqual(
            [tuple(sorted(ids)) for _, ids in first_partition],
            [("a", "b"), ("c",)],
        )
        self.assertEqual(
            [tuple(sorted(ids)) for _, ids in second_partition],
            [("b", "c"), ("a",)],
        )

    def test_nonfinite_hypothesis_prediction_is_rejected(self):
        class BrokenProgram:
            def apply(self, state):
                return (float("nan"),)
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("broken", BrokenProgram()),
            ],
            [(-1,)],
        )
        with self.assertRaisesRegex(IdentificationError, "invalid state"):
            identifier.rank_experiments()

    def test_hypothesis_must_preserve_state_dimension(self):
        class WrongDimensionProgram:
            def apply(self, state):
                return (1.0, 2.0)
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("wrong-dimension", WrongDimensionProgram()),
            ],
            [(-1,)],
        )
        with self.assertRaisesRegex(IdentificationError, "changed state dimension"):
            identifier.rank_experiments()

    def test_observed_output_dimension_must_match_input(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("negative", program("neg")),
            ],
            [(-2,)],
        )
        experiment = identifier.choose_experiment()
        with self.assertRaisesRegex(IdentificationError, "output dimension"):
            identifier.observe(experiment.before, (1.0, 2.0))
        self.assertEqual(len(identifier.observations), 0)
        self.assertEqual(len(identifier.hypotheses), 2)

    def test_non_integral_experiment_budget_is_rejected(self):
        with self.assertRaises(IdentificationError):
            ActiveOperatorIdentifier(
                [OperatorHypothesis("identity", SimpleProgram())],
                [(1,)],
                max_experiments=1.5,
            )

    def test_nonfinite_tolerance_is_rejected(self):
        with self.assertRaises(IdentificationError):
            ActiveOperatorIdentifier(
                [OperatorHypothesis("identity", SimpleProgram())],
                [(1,)],
                tolerance=float("nan"),
            )

    def test_status_does_not_call_pending_query_unidentifiable(self):
        identifier = ActiveOperatorIdentifier(
            [
                OperatorHypothesis("identity", SimpleProgram()),
                OperatorHypothesis("absolute", program("abs")),
            ],
            [(-2,), (2,)],
        )
        identifier.choose_experiment()
        self.assertEqual(identifier.status().status, "ambiguous")


if __name__ == "__main__":
    unittest.main()
