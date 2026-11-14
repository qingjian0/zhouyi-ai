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

    def test_new_counterexample_invalidates_broad_rule(self):
        domains = ((0, 1), (0, 1), (0, 1, 2))
        learner = CounterexampleRuleLearner(domains, min_support=2)
        initial = [
            Example((0, 0, 0), "yes"), Example((0, 1, 0), "yes"),
            Example((1, 0, 0), "no"), Example((1, 1, 0), "no"),
        ]
        learner.fit(initial)
        self.assertEqual(learner.predict((0, 0, 2)), "yes")
        # The newly observed counterexample rules out the broad a=0 clause.
        learner.fit(initial + [Example((0, 0, 2), "no")])
        self.assertIsNone(learner.predict((0, 0, 2)))

    def test_abstains_outside_declared_domain(self):
        learner = CounterexampleRuleLearner(((0, 1), (0, 1)), min_support=2)
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

    def test_candidate_budget_counts_each_label_evaluation(self):
        learner = CounterexampleRuleLearner(((0, 1),), max_candidates=5)
        with self.assertRaises(RuleLearningError):
            learner.fit([
                Example((0,), "A"), Example((1,), "B"),
            ])

    def test_rejects_invalid_and_duplicate_examples(self):
        learner = CounterexampleRuleLearner(((0, 1),))
        with self.assertRaises(RuleLearningError):
            learner.fit([Example((2,), 0)])
        with self.assertRaises(RuleLearningError):
            learner.fit([Example((0,), 0), Example((0,), 1)])


if __name__ == "__main__":
    unittest.main()
