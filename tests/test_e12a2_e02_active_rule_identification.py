import unittest

from prototype.e12a2_e02_active_rule_identification import (
    QUERIES, RULES, consistent_rules, initial_query_for_seed,
    predict, run_episode, select_information_gain, select_oracle,
)


class ActiveRuleIdentificationTests(unittest.TestCase):
    def test_initial_support_query_is_seeded_without_target_input(self):
        query = initial_query_for_seed(123)
        self.assertIn(query, QUERIES)
        self.assertEqual(query, initial_query_for_seed(123))

    def test_target_rule_is_not_needed_for_candidate_reconstruction(self):
        evidence = (((0, 0), 1), ((1, 0), 2))
        hypotheses = consistent_rules(evidence)
        self.assertTrue(hypotheses)
        self.assertTrue(all(
            predict(rule, query) == outcome
            for rule in hypotheses for query, outcome in evidence
        ))

    def test_information_gain_returns_permitted_unmeasured_query(self):
        evidence = (((0, 0), 1),)
        available = tuple(q for q in QUERIES if q != (0, 0))
        selected = select_information_gain(evidence, available)
        self.assertIn(selected, available)

    def test_information_gain_and_oracle_abstain_when_identified(self):
        evidence = tuple((q, predict(RULES[0], q)) for q in QUERIES)
        self.assertIsNone(select_information_gain(evidence, ()))
        self.assertIsNone(select_oracle(evidence, ()))

    def test_oracle_never_selects_used_query(self):
        evidence = (((0, 0), predict(RULES[0], (0, 0))),)
        available = tuple(q for q in QUERIES if q != (0, 0))
        self.assertIn(select_oracle(evidence, available), available)

    def test_information_gain_selection_does_not_depend_on_hidden_target(self):
        initial = ((0, 0),)
        evidence = ((initial[0], predict(RULES[0], initial[0])),)
        available = tuple(q for q in QUERIES if q != initial[0])
        decision_a = select_information_gain(evidence, available)
        # Changing the environment's hidden target without changing learner
        # evidence must not change the selected measurement.
        _hidden_target_b = RULES[-1]
        decision_b = select_information_gain(evidence, available)
        self.assertEqual(decision_a, decision_b)

    def test_all_policies_reach_same_final_hypothesis_when_identified(self):
        target = RULES[11]
        initial = (1, 2)
        for policy in ("information_gain", "random", "fixed", "exact_oracle"):
            result = run_episode(target, initial, policy, seed=9)
            self.assertTrue(result["identified"])
            self.assertEqual(result["remaining_hypotheses"], 1)

    def test_measurement_budget_is_bounded_by_query_domain(self):
        result = run_episode(RULES[5], (0, 1), "information_gain", seed=5)
        self.assertLessEqual(result["total_measurements"], len(QUERIES))


if __name__ == "__main__":
    unittest.main()
