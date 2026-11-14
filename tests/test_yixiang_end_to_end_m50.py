import unittest
from prototype.yixiang_end_to_end_m50 import run_benchmark, run_episode

COMMIT = "abcdef1234567890abcdef1234567890abcdef12"

class M50Tests(unittest.TestCase):
    def test_end_to_end_run_completes(self):
        result = run_benchmark(episode_count=3, seed_start=7, code_commit=COMMIT)
        self.assertEqual(result["episode_count"], 3)
        self.assertTrue(result["ledger_valid"])
        self.assertTrue(result["manifest_audit"].complete)
        self.assertTrue(result["manifest_audit"].leakage_free)

    def test_agent_recovers_direct_parents_under_confounding(self):
        episode = run_episode(7, COMMIT, 0)
        score = episode["score_by_id"]["intervention_agent_adapter"]
        self.assertEqual(score.f1, 1.0)
        self.assertEqual(score.structural_hamming_distance, 0)

    def test_observational_baseline_is_scored_without_causal_claim(self):
        episode = run_episode(7, COMMIT, 0)
        corr = episode["score_by_id"]["observational_correlation"]
        self.assertGreaterEqual(corr.structural_hamming_distance, 0)

    def test_random_baseline_is_seeded(self):
        a = run_episode(11, COMMIT, 1)
        b = run_episode(11, COMMIT, 1)
        self.assertEqual(a["score_by_id"]["seeded_random"],
                         b["score_by_id"]["seeded_random"])

    def test_intervention_effect_separates_confounded_non_parent(self):
        effects = run_episode(7, COMMIT, 0)["intervention_effects"]
        self.assertAlmostEqual(effects["c"], 0.0, places=10)
        self.assertGreater(abs(effects["a"]), 1.0)
        self.assertGreater(abs(effects["b"]), 1.0)

    def test_paired_ablation_is_valid(self):
        result = run_benchmark(3, 7, COMMIT)
        self.assertTrue(result["paired_ablation"].valid)
        self.assertEqual(result["paired_ablation"].effects[0].paired_episodes, 3)

    def test_manifest_digest_is_deterministic(self):
        a = run_benchmark(3, 7, COMMIT)
        b = run_benchmark(3, 7, COMMIT)
        self.assertEqual(a["manifest_audit"].manifest_digest,
                         b["manifest_audit"].manifest_digest)

    def test_result_digest_is_deterministic(self):
        self.assertEqual(run_benchmark(3, 7, COMMIT)["result_digest"],
                         run_benchmark(3, 7, COMMIT)["result_digest"])

    def test_ledger_records_action_observation_and_claim(self):
        kinds = {e.event_type for e in run_episode(7, COMMIT, 0)["ledger"].events}
        self.assertTrue({"action", "observation", "policy_decision", "final_claim"} <= kinds)

    def test_ledger_chain_validates(self):
        self.assertTrue(run_episode(7, COMMIT, 0)["ledger_audit"].valid)

    def test_budget_not_violated(self):
        result = run_benchmark(3, 7, COMMIT)
        for summary in result["summaries"].values():
            self.assertEqual(summary["budget_violation_rate"], 0.0)

    def test_oracle_is_separated_from_agent_outputs(self):
        episode = run_episode(7, COMMIT, 0)
        for output in episode["outputs"]:
            self.assertNotIn("truth_parents", output.__dict__)
        self.assertEqual(episode["oracle_diagnostic"]["baseline_id"],
                         "evaluator_oracle_only")

    def test_requires_multiple_episodes(self):
        with self.assertRaisesRegex(ValueError, "episode_count_must_be_at_least_two"):
            run_benchmark(1, 7, COMMIT)

    def test_rejects_negative_seed(self):
        with self.assertRaisesRegex(ValueError, "seed_start_must_be_nonnegative"):
            run_benchmark(3, -1, COMMIT)

    def test_rejects_non_hex_commit(self):
        with self.assertRaisesRegex(ValueError, "code_commit_must_be_hex_sha"):
            run_benchmark(3, 7, "not-a-sha")

    def test_agent_uses_full_intervention_budget(self):
        output = next(x for x in run_episode(7, COMMIT, 0)["outputs"]
                      if x.baseline_id == "intervention_agent_adapter")
        self.assertEqual(output.total_cost, 6.0)

    def test_correlation_baseline_uses_observations_only(self):
        output = next(x for x in run_episode(7, COMMIT, 0)["outputs"]
                      if x.baseline_id == "observational_correlation")
        self.assertEqual(output.total_cost, 0.0)

    def test_population_is_paired_across_interventions(self):
        import json
        action = next(e for e in run_episode(7, COMMIT, 0)["ledger"].events
                      if e.event_type == "action")
        self.assertEqual(len(json.loads(action.payload_json)["paired_unit_ids"]), 64)

    def test_reports_scope_limitations(self):
        result = run_benchmark(3, 7, COMMIT)
        self.assertTrue(any("not_an_llm" in x for x in result["limitations"]))

    def test_all_baselines_have_comparable_episode_counts(self):
        result = run_benchmark(3, 7, COMMIT)
        self.assertEqual({x["episodes"] for x in result["summaries"].values()}, {3})

if __name__ == "__main__":
    unittest.main()
