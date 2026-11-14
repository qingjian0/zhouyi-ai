import unittest

from prototype.yixiang_m60_causal_transfer import (
    backdoor_adjusted_effect, generate_dataset, observational_difference,
    _d_separated, infer_backdoor_set, predict, rename_case, run_baselines,
)


class M60CausalTransferTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.truth = generate_dataset()
        self.by_id = {case["case_id"]: case for case in self.cases}

    def test_observed_confounder_requires_backdoor_adjustment(self):
        case = self.by_id["observed_confounder"]
        naive = observational_difference(case)
        adjusted = backdoor_adjusted_effect(case, ["U"])
        self.assertGreater(abs(naive - self.truth["observed_confounder"]["ate"]), 0.1)
        self.assertAlmostEqual(adjusted, self.truth["observed_confounder"]["ate"], places=10)

    def test_total_effect_must_not_adjust_away_mediator(self):
        case = self.by_id["mediated_total_effect"]
        total = backdoor_adjusted_effect(case, [])
        direct_only = backdoor_adjusted_effect(case, ["M"])
        self.assertAlmostEqual(total, self.truth["mediated_total_effect"]["ate"], places=10)
        self.assertGreater(abs(total - direct_only), 0.2)

    def test_collider_is_not_a_valid_adjustment_variable(self):
        case = self.by_id["collider_selection"]
        self.assertAlmostEqual(observational_difference(case), 0.0, places=10)
        collider_adjusted = backdoor_adjusted_effect(case, ["C"])
        self.assertGreater(abs(collider_adjusted), 0.1)

    def test_latent_confounding_requires_abstention(self):
        case = self.by_id["latent_confounder"]
        prediction = predict(case, "graph_backdoor")
        self.assertEqual(prediction["status"], "not_identifiable")
        self.assertIsNone(prediction["estimate"])

    def test_graph_backdoor_baseline_recovers_identifiable_effects(self):
        results = run_baselines(self.cases, self.truth)
        graph = results["graph_backdoor"]["metrics"]
        self.assertEqual(graph["identification_accuracy"], 1.0)
        self.assertEqual(graph["identified_case_mae"], 0.0)
        self.assertEqual(graph["identified_cases_scored"], 3)

    def test_all_observed_adjustment_is_not_generally_valid(self):
        results = run_baselines(self.cases, self.truth)
        graph = results["graph_backdoor"]["metrics"]
        naive = results["naive_observational"]["metrics"]
        all_adjust = results["all_observed_adjustment"]["metrics"]
        self.assertEqual(graph["identified_case_mae"], 0.0)
        self.assertGreater(all_adjust["identified_case_mae"], 0.0)
        self.assertGreater(naive["identified_case_mae"], 0.0)

    def test_minimum_backdoor_set_is_found_from_graph_not_hardcoded_parents(self):
        result = infer_backdoor_set(self.by_id["observed_confounder"])
        self.assertTrue(result["identified"])
        self.assertEqual(result["adjustment_set"], ["U"])

    def test_mediator_is_excluded_from_total_effect_adjustment(self):
        result = infer_backdoor_set(self.by_id["mediated_total_effect"])
        self.assertEqual(result["adjustment_set"], [])

    def test_hidden_common_cause_has_no_observed_backdoor_set(self):
        result = infer_backdoor_set(self.by_id["latent_confounder"])
        self.assertFalse(result["identified"])
        self.assertEqual(result["reason"], "no_observed_backdoor_adjustment_set")

    def test_d_separation_distinguishes_chain_fork_and_collider(self):
        nodes = ["A", "B", "C"]
        self.assertFalse(_d_separated(nodes, [("A", "B"), ("B", "C")], "A", "C", []))
        self.assertTrue(_d_separated(nodes, [("A", "B"), ("B", "C")], "A", "C", ["B"]))
        self.assertFalse(_d_separated(nodes, [("A", "B"), ("C", "B")], "A", "C", ["B"]))
        self.assertTrue(_d_separated(nodes, [("A", "B"), ("C", "B")], "A", "C", []))

    def test_causal_mapping_transfers_under_domain_renaming(self):
        source = self.by_id["observed_confounder"]
        target = rename_case(
            source, {"U": "context", "X": "decision", "Y": "result"},
            case_id="renamed_domain",
        )
        source_prediction = predict(source, "graph_backdoor")
        target_prediction = predict(target, "graph_backdoor")
        self.assertAlmostEqual(source_prediction["estimate"], target_prediction["estimate"], places=12)
        self.assertEqual(target_prediction["adjustment_set"], ["context"])


if __name__ == "__main__":
    unittest.main()
