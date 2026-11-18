"""Tests for bounded operator induction."""
import random
import unittest

from prototype.operator_induction import (
    InductionError, OperatorInducer, OperatorProgram, Primitive, Transition,
)


def make_rows(seed, count, program):
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        state = tuple(float(rng.randint(-9, 9)) for _ in range(4))
        rows.append(Transition(state, program.apply(state)))
    return rows


class OperatorInductionTests(unittest.TestCase):
    def test_discovers_composed_hidden_operator_and_generalizes(self):
        hidden = OperatorProgram((Primitive("swap", 0, 2), Primitive("neg", 1)))
        train = make_rows(17, 10, hidden)
        validation = make_rows(29, 8, hidden)
        inducer = OperatorInducer(4, max_depth=2, max_programs=100_000)
        report = inducer.discover(train, validation=validation)
        exact = [
            candidate for candidate in report.candidates
            if candidate.program == hidden
        ]
        self.assertTrue(exact)
        self.assertEqual(exact[0].validation_accuracy, 1.0)
        self.assertFalse(report.search_truncated)

    def test_rejects_wrong_dimension_and_nonfinite_values(self):
        inducer = OperatorInducer(3)
        with self.assertRaises(InductionError):
            inducer.discover([Transition((1.0, 2.0), (1.0, 2.0))])
        with self.assertRaises(InductionError):
            inducer.discover([Transition((1.0, float("nan"), 3.0), (1.0, 2.0, 3.0))])

    def test_search_budget_is_reported(self):
        hidden = OperatorProgram((Primitive("neg", 0),))
        rows = make_rows(3, 4, hidden)
        report = OperatorInducer(4, max_depth=3, max_programs=5).discover(rows)
        self.assertEqual(report.programs_examined, 5)
        self.assertTrue(report.search_truncated)

    def test_validation_does_not_change_training_support(self):
        hidden = OperatorProgram((Primitive("abs", 2),))
        train = make_rows(4, 5, hidden)
        valid = [Transition((1.0, 2.0, 3.0, 4.0), (1.0, 2.0, 99.0, 4.0))]
        report = OperatorInducer(4, max_depth=1).discover(train, validation=valid)
        self.assertTrue(report.candidates)
        self.assertTrue(all(item.train_accuracy == 1.0 for item in report.candidates))
        self.assertTrue(all(item.validation_accuracy == 0.0 for item in report.candidates))

    def test_validation_labels_do_not_change_candidate_ranking(self):
        inducer = OperatorInducer(2, max_depth=1, max_programs=100)
        train = [Transition((0.0, 0.0), (0.0, 0.0))]
        validation_a = [Transition((1.0, 2.0), (-1.0, 2.0))]
        validation_b = [Transition((1.0, 2.0), (2.0, 1.0))]
        first = inducer.discover(train, validation=validation_a, result_limit=100)
        second = inducer.discover(train, validation=validation_b, result_limit=100)
        self.assertEqual(
            [item.program for item in first.candidates],
            [item.program for item in second.candidates],
        )
        self.assertNotEqual(
            [item.validation_support for item in first.candidates],
            [item.validation_support for item in second.candidates],
        )

    def test_program_composition_order_matters(self):
        state = (2.0, 5.0, 7.0)
        first = OperatorProgram((Primitive("swap", 0, 1), Primitive("neg", 0)))
        second = OperatorProgram((Primitive("neg", 0), Primitive("swap", 0, 1)))
        self.assertNotEqual(first.apply(state), second.apply(state))

    def test_invalid_operator_rejected(self):
        with self.assertRaises(InductionError):
            OperatorProgram((Primitive("unknown", 0),)).apply((1.0, 2.0))


if __name__ == "__main__":
    unittest.main()
