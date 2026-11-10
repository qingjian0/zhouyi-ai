import unittest

from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_prequential import PrequentialError, PrequentialRunner


class E09PrequentialRunnerTests(unittest.TestCase):
    def make_runner(self):
        runner = PrequentialRunner(CounterexampleRuleLearner(
            ((0, 1), (0, 1), (0, 1, 2)), min_support=2
        ))
        runner.bootstrap([
            ("seed-1", Example((0, 0, 0), "yes")),
            ("seed-2", Example((0, 1, 0), "yes")),
            ("seed-3", Example((1, 0, 0), "no")),
            ("seed-4", Example((1, 1, 0), "no")),
        ])
        return runner

    def test_predict_is_committed_before_label_reveal(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        self.assertEqual(commit.prediction, "yes")
        self.assertEqual(commit.model_version, 1)
        self.assertEqual(runner.score()["revealed_observations"], 0)
        reveal = runner.reveal(commit.prediction_id, "no")
        self.assertEqual(reveal.prediction_id, commit.prediction_id)
        self.assertEqual(runner.score()["accuracy_when_predicted"], 0.0)

    def test_reveal_without_commit_is_rejected(self):
        runner = self.make_runner()
        with self.assertRaises(PrequentialError):
            runner.reveal("missing", "yes")

    def test_duplicate_prediction_and_reveal_are_rejected(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        with self.assertRaises(PrequentialError):
            runner.predict_and_commit("obs-5", (0, 0, 2))
        runner.reveal(commit.prediction_id, "no")
        with self.assertRaises(PrequentialError):
            runner.reveal(commit.prediction_id, "yes")

    def test_revision_requires_reveal_and_is_explicitly_batch_refit(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        with self.assertRaises(PrequentialError):
            runner.revise(commit.prediction_id)
        reveal = runner.reveal(commit.prediction_id, "no")
        event = runner.revise(commit.prediction_id)
        self.assertEqual(event.trigger_reveal_id, reveal.reveal_id)
        self.assertEqual(event.operation, "BATCH_REFIT")
        self.assertEqual(event.before_model_version, 1)
        self.assertEqual(event.after_model_version, 2)
        self.assertIsNone(runner.learner.predict((0, 0, 2)))

    def test_one_reveal_cannot_trigger_multiple_revisions(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        runner.reveal(commit.prediction_id, "no")
        runner.revise(commit.prediction_id)
        with self.assertRaises(PrequentialError):
            runner.revise(commit.prediction_id)

    def test_revision_cost_is_recorded(self):
        runner = self.make_runner()
        commit = runner.predict_and_commit("obs-5", (0, 0, 2))
        runner.reveal(commit.prediction_id, "no")
        event = runner.revise(commit.prediction_id)
        self.assertGreater(event.training_example_count, 0)
        self.assertGreater(event.candidate_evaluations, 0)


if __name__ == "__main__":
    unittest.main()
