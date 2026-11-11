import unittest

from prototype.e13_b3_active import (
    CandidateForecast, select_discriminating_query, update_version_space
)


class ActiveBridgeQueryTests(unittest.TestCase):
    def setUp(self):
        self.candidates = ("c1", "c2", "c3")
        self.forecasts = (
            CandidateForecast("c1", "q1", "A"),
            CandidateForecast("c2", "q1", "A"),
            CandidateForecast("c3", "q1", "B"),
            CandidateForecast("c1", "q2", "A"),
            CandidateForecast("c2", "q2", "B"),
            CandidateForecast("c3", "q2", "C"),
            CandidateForecast("c1", "q3", "A"),
            CandidateForecast("c2", "q3", "A"),
            CandidateForecast("c3", "q3", "A"),
        )

    def test_selects_maximum_disagreement_query(self):
        result = select_discriminating_query(self.candidates, self.forecasts)
        self.assertEqual(result.status, "SELECTED")
        self.assertEqual(result.selected.query_id, "q2")
        self.assertEqual(result.selected.disagreement, 1.0)

    def test_tie_break_is_deterministic(self):
        forecasts = (
            CandidateForecast("c1", "z", "x"), CandidateForecast("c2", "z", "y"),
            CandidateForecast("c1", "a", "x"), CandidateForecast("c2", "a", "y"),
        )
        result = select_discriminating_query(("c1", "c2"), forecasts)
        self.assertEqual(result.selected.query_id, "a")

    def test_incomplete_forecast_query_is_not_selected(self):
        result = select_discriminating_query(
            ("c1", "c2"), (CandidateForecast("c1", "q", "yes"),)
        )
        self.assertEqual(result.status, "NO_DISCRIMINATING_QUERY")

    def test_evidence_filters_version_space(self):
        result = update_version_space(
            self.candidates, self.forecasts, query_id="q2", observed_outcome="B"
        )
        self.assertEqual(result.status, "UPDATED")
        self.assertEqual(result.retained_candidate_ids, ("c2",))
        self.assertEqual(result.rejected_candidate_ids, ("c1", "c3"))

    def test_observation_can_reject_every_candidate_without_inventing_one(self):
        result = update_version_space(
            self.candidates, self.forecasts, query_id="q2", observed_outcome="D"
        )
        self.assertEqual(result.status, "CONTRADICTION")
        self.assertEqual(result.retained_candidate_ids, ())

    def test_duplicate_or_incomplete_predictions_fail_closed(self):
        result = update_version_space(
            ("c1", "c2"),
            (CandidateForecast("c1", "q", "A"),),
            query_id="q", observed_outcome="A"
        )
        self.assertEqual(result.status, "REJECTED_INCOMPLETE_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
