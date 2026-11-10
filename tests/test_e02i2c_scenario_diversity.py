import unittest

from prototype.e02i2c_hidden_event_benchmark import EventType, SUPPORTED_EVENTS
from prototype.e02i2c_scenario_diversity import (
    FAMILIES, generate_episode, run_scenario_diversity, _decision, _build_family_episodes,
)


class E02I2CScenarioDiversityTests(unittest.TestCase):
    def test_family_split_is_strict_and_locked_family_is_unavailable(self):
        for family in ("A", "B"):
            generate_episode(EventType.KEEP, 123, family=family, split="train")
            with self.assertRaises(ValueError):
                generate_episode(EventType.KEEP, 123, family=family, split="gate")
        generate_episode(EventType.KEEP, 123, family="C", split="gate")
        with self.assertRaises(ValueError):
            generate_episode(EventType.KEEP, 123, family="D", split="test")

    def test_all_events_preserve_adjudication_across_families(self):
        for family, split in (("A", "train"), ("B", "train"), ("C", "gate")):
            for index, event in enumerate(SUPPORTED_EVENTS):
                for seed in range(10):
                    episode = generate_episode(
                        event, 10000 + seed * 100 + index,
                        family=family, split=split,
                    )
                    self.assertEqual(_decision(episode.observation), event,
                                     (family, event, seed))
                    self.assertEqual(len(episode.observation.opportunities), 4)
                    self.assertGreaterEqual(len(episode.observation.evidence), 3)
                    self.assertLessEqual(len(episode.observation.evidence), 8)

    def test_family_c_varies_environment_and_evidence_count(self):
        rows = [
            generate_episode(EventType.KEEP, 50000 + seed,
                             family="C", split="gate")
            for seed in range(30)
        ]
        environments = {
            item.environment for ep in rows
            for item in ep.observation.opportunities
        }
        counts = {len(ep.observation.evidence) for ep in rows}
        self.assertGreaterEqual(len(environments), 2)
        self.assertGreaterEqual(len(counts), 2)

    def test_truth_and_family_are_not_observation_fields(self):
        episode = generate_episode(EventType.MODIFY, 50123, family="C", split="gate")
        observation = episode.observation
        self.assertFalse(hasattr(observation, "truth"))
        self.assertFalse(hasattr(observation, "family"))
        self.assertFalse(hasattr(observation, "seed"))
        self.assertFalse(hasattr(observation, "split"))

    def test_runner_enforces_train_gate_namespace_and_semantics(self):
        result = run_scenario_diversity(seeds=30, bootstrap_samples=100)
        self.assertTrue(result["namespace"]["sample_disjoint"])
        self.assertTrue(result["namespace"]["evidence_disjoint"])
        self.assertTrue(result["semantic_invariance"]["passed"])
        self.assertEqual(result["train_episodes"], 480)
        self.assertEqual(result["gate_episodes"], 240)
        self.assertFalse(result["limitations"] == [])
        for tier in ("M0", "M1", "M2"):
            for model in ("categorical_naive_bayes", "decision_tree_depth_3"):
                metrics = result["metadata_attackers"][tier][model]
                self.assertEqual(metrics["seed_block_bootstrap"]["replicates"], 100)
                self.assertTrue(metrics["seed_block_bootstrap"]["macro_f1_95_ci"])
                self.assertEqual(
                    sum(row["episodes"] for row in metrics["per_environment"].values()),
                    240,
                )
        self.assertEqual(
            sum(row["episodes"] for row in result["evidence_aware_reference"]["per_environment"].values()),
            240,
        )


if __name__ == "__main__":
    unittest.main()
