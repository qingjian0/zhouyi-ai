import unittest

from prototype.e09_counterexample_learner import Example
from prototype.e09_incremental_learner import (
    IncrementalConjunctionLearner, IncrementalLearningError,
)


class IncrementalConjunctionLearnerTests(unittest.TestCase):
    def make_learner(self):
        learner = IncrementalConjunctionLearner(
            ((0, 1), (0, 1), (0, 1, 2)), min_support=2
        )
        for row in (
            Example((0, 0, 0), "yes"),
            Example((0, 1, 0), "yes"),
            Example((1, 0, 0), "no"),
            Example((1, 1, 0), "no"),
        ):
            learner.observe(row.inputs, row.label)
        return learner

    def test_incremental_update_invalidates_only_matching_generalizations(self):
        learner = self.make_learner()
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        before = learner.report["incremental_pattern_updates"]
        self.assertEqual(learner.observe((0, 0, 2), "no"), "ADDED")
        self.assertIsNone(learner.predict((0, 0, 2)))
        self.assertEqual(
            learner.report["incremental_pattern_updates"] - before, 8
        )

    def test_duplicate_evidence_is_idempotent(self):
        learner = self.make_learner()
        before = learner.report["incremental_pattern_updates"]
        self.assertEqual(learner.observe((0, 0, 0), "yes"), "DUPLICATE")
        self.assertEqual(learner.report["incremental_pattern_updates"], before)

    def test_conflict_retracts_prior_contribution_and_quarantines_input(self):
        learner = self.make_learner()
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        self.assertEqual(learner.observe((0, 0, 0), "no"), "CONTESTED")
        self.assertEqual(learner.report["retracted_contributions"], 1)
        self.assertEqual(learner.report["contested_inputs"], 1)
        self.assertIsNone(learner.predict((0, 0, 2)))

    def test_conflict_does_not_reintroduce_either_label(self):
        learner = self.make_learner()
        learner.observe((0, 0, 0), "no")
        self.assertEqual(learner.observe((0, 0, 0), "yes"), "DUPLICATE")
        self.assertEqual(learner.observe((0, 0, 0), "maybe"), "CONTESTED")
        self.assertEqual(learner.report["retracted_contributions"], 1)
        self.assertIsNone(learner.predict((0, 0, 0)))

    def test_rejects_invalid_domain_and_arity(self):
        learner = self.make_learner()
        with self.assertRaises(IncrementalLearningError):
            learner.observe((9, 0, 0), "no")
        with self.assertRaises(IncrementalLearningError):
            learner.predict((0, 0))

    def test_snapshot_is_deterministic(self):
        a = self.make_learner().snapshot()
        b = self.make_learner().snapshot()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
