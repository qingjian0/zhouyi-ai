import unittest

from prototype.e13_causal import (
    InterventionQuery, MechanismContractError, MechanismMap, MechanismModel,
    MechanismRule, MechanismResponse, forecast_target_response,
    observe_target_response, select_mechanism_query, validate_mechanism_query,
)


class DynamicMechanismTests(unittest.TestCase):
    def setUp(self):
        self.source = MechanismModel(
            "heat-domain", ("heater", "receiver"),
            (
                MechanismRule("heater", "increase", "receiver", "warmer", 1, (("phase", "active"),)),
                MechanismRule("heater", "decrease", "receiver", "cooler", 2, (("phase", "active"),)),
            ),
        )
        self.target = MechanismModel(
            "bio-domain", ("supplier", "consumer"),
            (
                MechanismRule("supplier", "more", "consumer", "energized", 1, (("stage", "active"),)),
                MechanismRule("supplier", "less", "consumer", "depleted", 2, (("stage", "active"),)),
            ),
        )
        self.query_more = InterventionQuery("q-more", "heater", "increase", (("phase", "active"),))
        self.query_less = InterventionQuery("q-less", "heater", "decrease", (("phase", "active"),))

    def mapping(self, candidate_id="m1", outcome_value_map=(("warmer", "energized"), ("cooler", "depleted"))):
        return MechanismMap(
            candidate_id,
            intervention_variables=(("heater", "supplier"),),
            outcome_variables=(("receiver", "consumer"),),
            intervention_values=(("increase", "more"), ("decrease", "less")),
            outcome_values=outcome_value_map,
            context_keys=(("phase", "stage"),),
            provenance="explicit test mapping",
            rationale="test a directed intervention-response correspondence",
        )

    def test_cross_domain_mechanism_prediction_matches_independent_target(self):
        mapping = self.mapping()
        predicted = forecast_target_response(self.source, mapping, self.query_more)
        observed = observe_target_response(self.target, mapping, self.query_more)
        self.assertEqual(predicted, MechanismResponse("consumer", "energized", 1))
        self.assertEqual(predicted, observed)

    def test_static_role_correspondence_does_not_hide_response_direction_reversal(self):
        reversed_target = MechanismModel(
            "reversed-bio-domain", ("supplier", "consumer"),
            (MechanismRule("supplier", "more", "consumer", "depleted", 1, (("stage", "active"),)),),
        )
        mapping = self.mapping()
        predicted = forecast_target_response(self.source, mapping, self.query_more)
        observed = observe_target_response(reversed_target, mapping, self.query_more)
        self.assertNotEqual(predicted, observed)

    def test_delay_is_part_of_mechanism_not_ignored(self):
        delayed_target = MechanismModel(
            "delayed-bio-domain", ("supplier", "consumer"),
            (MechanismRule("supplier", "more", "consumer", "energized", 3, (("stage", "active"),)),),
        )
        mapping = self.mapping()
        self.assertNotEqual(
            forecast_target_response(self.source, mapping, self.query_more),
            observe_target_response(delayed_target, mapping, self.query_more),
        )

    def test_context_mapping_is_explicit_and_values_are_invariant(self):
        mapping = self.mapping()
        wrong_context = InterventionQuery("q-wrong", "heater", "increase", (("phase", "dormant"),))
        self.assertIsNone(forecast_target_response(self.source, mapping, wrong_context))
        self.assertIsNone(observe_target_response(self.target, mapping, wrong_context))

    def test_missing_outcome_mapping_fails_closed(self):
        mapping = self.mapping(outcome_value_map=(("warmer", "energized"),))
        self.assertIsNone(forecast_target_response(self.source, mapping, self.query_less))

    def test_ambiguous_duplicate_response_rule_is_rejected(self):
        with self.assertRaises(MechanismContractError):
            MechanismModel("ambiguous", ("a", "b"), (
                MechanismRule("a", "x", "b", "y", 1),
                MechanismRule("a", "x", "b", "z", 1),
            ))

    def test_mapping_collision_is_rejected(self):
        with self.assertRaises(MechanismContractError):
            self.mapping(outcome_value_map=(("warmer", "same"), ("cooler", "same")))

    def test_active_query_chooses_intervention_that_separates_mechanism_maps(self):
        correct = self.mapping("correct")
        flipped = self.mapping(
            "flipped",
            outcome_value_map=(("warmer", "depleted"), ("cooler", "energized")),
        )
        selection = select_mechanism_query(
            self.source, (correct, flipped), (self.query_more, self.query_less),
        )
        self.assertEqual(selection.status, "SELECTED")
        self.assertIn(selection.selected.query_id, ("q-more", "q-less"))
        self.assertEqual(selection.selected.disagreement, 1.0)

    def test_selected_candidate_is_checked_against_target_only_after_selection(self):
        mapping = self.mapping()
        result = validate_mechanism_query(
            self.source, self.target, mapping, self.query_more
        )
        self.assertEqual(result.status, "VALID_FOR_QUERY")
        reversed_target = MechanismModel(
            "reversed", ("supplier", "consumer"),
            (MechanismRule("supplier", "more", "consumer", "depleted", 1, (("stage", "active"),)),),
        )
        rejected = validate_mechanism_query(
            self.source, reversed_target, mapping, self.query_more
        )
        self.assertEqual(rejected.status, "REJECTED")
        self.assertEqual(rejected.reason, "INTERVENTION_RESPONSE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
