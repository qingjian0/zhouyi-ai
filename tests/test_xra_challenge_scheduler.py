import unittest
from prototype.xra_challenge_scheduler import schedule_challenge

class XRAChallengeSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.priors = {"h-left": 0.5, "h-right": 0.5}
        self.predictions = {
            "h-left": {"cheap": {"same": 1.0}, "informative": {"red": 1.0}, "useless": {"x": 1.0}},
            "h-right": {"cheap": {"same": 1.0}, "informative": {"blue": 1.0}, "useless": {"x": 1.0}},
        }
        self.costs = {"cheap": 0.1, "informative": 1.0, "useless": 0.2}

    def test_selects_best_information_gain_per_cost(self):
        result = schedule_challenge(self.priors, self.predictions, self.costs, remaining_budget=2)
        self.assertEqual(result.action, "informative")
        self.assertAlmostEqual(result.expected_information_gain, 1.0)

    def test_budget_causes_abstention(self):
        result = schedule_challenge(self.priors, self.predictions, self.costs, remaining_budget=0.05)
        self.assertIsNone(result.action)
        self.assertEqual(result.reason, "budget_exhausted")

    def test_threshold_causes_abstention(self):
        result = schedule_challenge(self.priors, self.predictions, self.costs,
                                    remaining_budget=2, min_information_gain_per_cost=2)
        self.assertIsNone(result.action)

    def test_same_predictions_have_zero_information_gain(self):
        predictions = {"h-left": {"probe": {"yes": 0.7, "no": 0.3}},
                       "h-right": {"probe": {"yes": 0.7, "no": 0.3}}}
        result = schedule_challenge(self.priors, predictions, {"probe": 1},
                                    remaining_budget=1, min_information_gain_per_cost=0.01)
        self.assertIsNone(result.action)
        self.assertAlmostEqual(result.scores[0][1], 0.0)

    def test_rejects_incomplete_predictions(self):
        with self.assertRaises(ValueError):
            schedule_challenge(self.priors, {"h-left": {"probe": {"yes": 1}}},
                               {"probe": 1}, remaining_budget=1)

    def test_rejects_bad_probability_mass(self):
        predictions = {"h-left": {"probe": {"yes": 0.8}},
                       "h-right": {"probe": {"no": 1}}}
        with self.assertRaises(ValueError):
            schedule_challenge(self.priors, predictions, {"probe": 1}, remaining_budget=1)

if __name__ == "__main__": unittest.main()
