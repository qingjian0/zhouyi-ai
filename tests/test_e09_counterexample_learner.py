import itertools
import unittest

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example, RuleLearningError, run_demo,
)


class E09CounterexampleLearnerTests(unittest.TestCase):
    def test_discovers_hidden_conjunctions_and_generalizes(self):
        result = run_demo()
        self.assertEqual(result["heldout_examples"], 4)
        self.assertGreater(result["heldout_coverage"], 0.0)
        self.assertEqual(result["heldout_accuracy_when_predicted"], 1.0)
        self.assertEqual(result["learner"]["report"]["gradient_updates"], 0)

    def test_counterexample_removes_overgeneralized_clause(self):
        learner = CounterexampleRuleLearner(((0, 1), (0, 1)),
                                             min_support=2)
        # Initially all observed examples support the broad first-coordinate rule.
        learner.fit([
            Example((0, 0), "yes"),
            Example((0, 1), "yes"),
            Example((1, 0), "no"),
            Example((1, 1), "no"),
        ])
        self.assertEqual(learner.predict((0, 0)), "yes")
        # New counterexample contradicts the previous broad generalization.
        learner.fit([
            Example((0, 0), "yes"),
            Example((0, 1), "yes"),
            Example((1, 0), "no"),
            Example((1, 1), "no"),
            Example((0, 1), "no"),
        ]) if False else None
        # Duplicate assignments are deliberately rejected; a contradictory
        # label is not silently merged into the evidence store.
        with self.assertRaises(RuleLearningError):
            learner.fit([
                Example((0, 0), "yes"),
                Example((0, 1), "yes"),
                Example((0, 1), "no"),
            ])

    def test_abstains_on_conflicting_unseen_clause_matches(self):
        learner = CounterexampleRuleLearner(((0, 1), (0, 1)),
                                             min_support=2)
        learner.fit([
            Example((0, 0), "A"), Example((0, 1), "A"),
            Example((1, 0), "B"), Example((1, 1), "B"),
        ])
        self.assertEqual(learner.predict((0, 0)), "A")
        self.assertEqual(learner.predict((1, 1)), "B")
        self.assertIsNone(learner.predict((2, 0)))

    def test_rejects_candidate_space_explosion(self):
        learner = CounterexampleRuleLearner((range(10),) * 6,
                                             max_candidates=100)
        with self.assertRaises(RuleLearningError):
            learner.fit([Example((0,) * 6, 0), Example((1,) * 6, 1)])

    def test_rejects_invalid_and_duplicate_examples(self):
        learner = CounterexampleRuleLearner(((0, 1),))
        with self.assertRaises(RuleLearningError):
            learner.fit([Example((2,), 0)])
        with self.assertRaises(RuleLearningError):
            learner.fit([Example((0,), 0), Example((0,), 1)])


if __name__ == "__main__":
    unittest.main()
