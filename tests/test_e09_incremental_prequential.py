import unittest

from prototype.e09_counterexample_learner import Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialError, PrequentialRunner


class IncrementalPrequentialRunnerTests(unittest.TestCase):
    def make_runner(self):
        learner = IncrementalConjunctionLearner(
            ((0, 1), (0, 1), (0, 1, 2)), min_support=2
        )
        runner = PrequentialRunner(learner, revision_mode="INCREMENTAL_INDEX")
        runner.bootstrap([
            ("seed-1", Example((0, 0, 0), "yes")),
            ("seed-2", Example((0, 1, 0), "yes")),
            ("seed-3", Example((1, 0, 0), "no")),
            ("seed-4", Example((1, 1, 0), "no")),
        ])
        return runner

    def test_reveal_does_not_mutate_model_until_revision(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        self.assertEqual(commit.prediction, "yes")
        before = runner.learner.snapshot()
        runner.reveal(commit.prediction_id, "no")
        self.assertEqual(runner.learner.snapshot(), before)
        event = runner.revise(commit.prediction_id)
        self.assertEqual(event.operation, "INCREMENTAL_INDEX")
        self.assertEqual(event.candidate_evaluations, 8)
        self.assertIsNone(runner.learner.predict((0, 0, 2)))

    def test_conflicting_observation_retracts_previous_contribution(self):
        runner = self.make_runner()
        first = runner.predict_and_commit("obs-5", (0, 0, 2))
        runner.reveal(first.prediction_id, "yes")
        runner.revise(first.prediction_id)
        second = runner.predict_and_commit("obs-6", (0, 0, 2))
        runner.reveal(second.prediction_id, "no")
        event = runner.revise(second.prediction_id)
        self.assertEqual(event.candidate_evaluations, 8)
        self.assertEqual(runner.learner.report["contested_inputs"], 1)
        # The conflicting row is quarantined and its earlier contribution is
        # retracted. The two independent bootstrap positives still support
        # the broad rule, so this query remains classifiable as "yes".
        self.assertEqual(runner.learner.predict((0, 0, 2)), "yes")

    def test_incremental_mode_rejects_batch_learner(self):
        from prototype.e09_counterexample_learner import CounterexampleRuleLearner
        with self.assertRaises(PrequentialError):
            PrequentialRunner(
                CounterexampleRuleLearner(((0, 1),)),
                revision_mode="INCREMENTAL_INDEX",
            )

    def test_bootstrap_preserves_conflicts_for_future_quarantine(self):
        learner = IncrementalConjunctionLearner(((0, 1), (0, 1)), min_support=1)
        runner = PrequentialRunner(learner, revision_mode="INCREMENTAL_INDEX")
        runner.bootstrap([
            ("seed-a", Example((0, 0), "A")),
            ("seed-b", Example((0, 0), "B")),
            ("seed-c", Example((1, 1), "B")),
        ])
        self.assertEqual(runner.learner.report["contested_inputs"], 1)
        commit = runner.predict_and_commit("new-observation", (0, 0))
        runner.reveal(commit.prediction_id, "A")
        runner.revise(commit.prediction_id)
        self.assertEqual(runner.learner.report["contested_inputs"], 1)
        self.assertEqual(runner.learner.predict((0, 0)), "B")


if __name__ == "__main__":
    unittest.main()
