import unittest
from prototype.yinfu_active_observation import (
    Hypothesis, Likelihood, ObservationAction, Prediction, select_observation,
)

def action(action_id, channel, cost, timing, values):
    return ObservationAction(
        action_id, channel, cost, timing,
        tuple(Prediction(hid, (Likelihood("0", 1.0-value), Likelihood("1", value)))
              for hid, value in values.items()),
    )

class YinfuActiveObservationTests(unittest.TestCase):
    def setUp(self):
        self.hypotheses = (Hypothesis("h1", 0.5), Hypothesis("h2", 0.5))

    def test_timing_fit_selects_in_window_measurement(self):
        actions = (
            action("early", "visual", 1.0, 0.2, {"h1": 1, "h2": 0}),
            action("in_window", "visual", 1.0, 1.0, {"h1": 0, "h2": 1}),
        )
        result = select_observation(self.hypotheses, actions, remaining_budget=1.0)
        self.assertEqual(result.action_id, "in_window")

    def test_channel_novelty_breaks_equal_utility_tie(self):
        actions = (
            action("repeat_visual", "visual", 1.0, 1.0, {"h1": 1, "h2": 0}),
            action("switch_audio", "audio", 1.0, 1.0, {"h1": 0, "h2": 1}),
        )
        result = select_observation(
            self.hypotheses, actions, available_channels=("visual", "visual"),
            remaining_budget=1.0,
        )
        self.assertEqual(result.action_id, "switch_audio")
        self.assertGreater(result.channel_novelty, 0.9)

    def test_zero_information_abstains(self):
        result = select_observation(
            self.hypotheses, (action("same", "audio", 1.0, 1.0, {"h1": 1, "h2": 1}),),
            remaining_budget=1.0,
        )
        self.assertEqual(result.status, "NO_INFORMATION")
        self.assertIsNone(result.action_id)

    def test_budget_and_timing_are_hard_constraints(self):
        result = select_observation(
            self.hypotheses, (action("too_early", "audio", 2.0, 0.1, {"h1": 1, "h2": 0}),),
            remaining_budget=1.0, min_temporal_fit=0.5,
        )
        self.assertEqual(result.status, "NO_ELIGIBLE_ACTION")

    def test_invalid_likelihoods_are_rejected(self):
        malformed = ObservationAction(
            "bad", "audio", 1.0, 1.0,
            (Prediction("h1", (Likelihood("x", 0.4),)),
             Prediction("h2", (Likelihood("y", 1.0),))),
        )
        result = select_observation(self.hypotheses, (malformed,), remaining_budget=1.0)
        self.assertEqual(result.status, "INVALID")

if __name__ == "__main__":
    unittest.main()
