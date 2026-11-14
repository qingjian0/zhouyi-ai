import math
import unittest

from orchestrator.research.raw_analyzer import (
    _student_t_critical_two_sided, analyze_raw_observations, task_manifest_from_specs,
)


class RawAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = []
        self.observations = []
        for seed in range(12):
            for condition, value in (("baseline", 0.70), ("treatment", 0.75 + seed * 0.001)):
                task_id = f"{condition}-{seed}"
                self.manifest.append({"task_id": task_id, "track": "B2",
                                      "condition": condition, "seed": seed})
                self.observations.append({
                    "observation_id": f"obs-{condition}-{seed}-ood-shuffled",
                    "task_id": task_id, "split": "ood", "control": "shuffled",
                    "metric": "accuracy", "metric_value": value, "status": "succeeded",
                    "preregistered": True, "parameter_count": 1000,
                    "compute_budget": 50000, "split_source": "heldout_ood_v1",
                    "control_family": "shuffled",
                })

    def analyze(self, observations=None, manifest=None, **kwargs):
        return analyze_raw_observations(
            observations if observations is not None else self.observations,
            task_manifest=manifest if manifest is not None else self.manifest,
            task_set_digest="a" * 64, treatment_condition="treatment",
            baseline_condition="baseline", metric="accuracy",
            metric_direction="higher", **kwargs,
        )

    def test_manifest_helper_reads_matrix_task_payload(self):
        class Task:
            task_id = "t0"
            payload = {"track": "B2", "condition": "treatment", "seed": 7}
        self.assertEqual(task_manifest_from_specs([Task()]), [
            {"task_id": "t0", "track": "B2", "condition": "treatment", "seed": 7}
        ])

    def test_student_t_critical_known_values(self):
        self.assertAlmostEqual(_student_t_critical_two_sided(0.95, 9), 2.262157, places=5)
        self.assertAlmostEqual(_student_t_critical_two_sided(0.95, 1), 12.706205, places=4)

    def test_builds_paired_evidence_and_ci(self):
        result = self.analyze()
        self.assertEqual(len(result["evidence_rows"]), 1)
        row = result["evidence_rows"][0]
        self.assertEqual(row["seeds"], 12)
        self.assertTrue(row["valid"])
        self.assertGreater(row["effect_mean"], 0)
        self.assertLess(row["ci_lower"], row["effect_mean"])
        self.assertGreater(row["ci_upper"], row["effect_mean"])
        self.assertEqual(len(row["task_ids"]), 24)
        self.assertEqual(row["effect_direction"], "positive")

    def test_missing_observation_is_not_imputed(self):
        result = self.analyze(self.observations[:-1])
        self.assertEqual(len(result["missing_task_ids"]), 1)
        self.assertEqual(result["evidence_rows"][0]["seeds"], 11)

    def test_unmatched_seed_is_excluded(self):
        obs = self.observations[:-1]
        result = self.analyze(obs)
        self.assertEqual(result["evidence_rows"][0]["seeds"], 11)
        self.assertTrue(any(item["reason"] == "unmatched_pair" for item in result["excluded"]))

    def test_budget_mismatch_does_not_pair(self):
        obs = [dict(x) for x in self.observations]
        obs[-1]["compute_budget"] = 50001
        result = self.analyze(obs)
        self.assertEqual(result["evidence_rows"][0]["seeds"], 11)

    def test_same_task_can_emit_multiple_distinct_evaluation_observations(self):
        extra = dict(self.observations[0], observation_id="obs-extra",
                     split="iid", control="none", split_source="iid_validation_v1",
                     control_family="none")
        result = self.analyze(self.observations + [extra])
        self.assertEqual(result["observation_count"], len(self.observations) + 1)
        self.assertEqual(result["observed_task_count"], len(self.manifest))

    def test_duplicate_observation_id_rejected(self):
        duplicate = dict(self.observations[0])
        duplicate["task_id"] = self.observations[1]["task_id"]
        with self.assertRaisesRegex(ValueError, "duplicate observation_id"):
            self.analyze(self.observations + [duplicate])

    def test_duplicate_manifest_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate task ID"):
            self.analyze(manifest=self.manifest + [self.manifest[0]])

    def test_lower_is_better_preserves_raw_metric_sign(self):
        obs = [dict(x, metric="latency", metric_value=100 if x["task_id"].startswith("baseline") else 80)
               for x in self.observations]
        result = analyze_raw_observations(
            obs, task_manifest=self.manifest, task_set_digest="a" * 64,
            treatment_condition="treatment", baseline_condition="baseline",
            metric="latency", metric_direction="lower",
        )
        self.assertLess(result["evidence_rows"][0]["effect_mean"], 0)

    def test_failed_tasks_are_not_used(self):
        obs = [dict(x) for x in self.observations]
        obs[0]["status"] = "failed"
        result = self.analyze(obs)
        self.assertEqual(result["evidence_rows"][0]["seeds"], 11)
        self.assertTrue(any(item["reason"] == "task_not_succeeded" for item in result["excluded"]))

    def test_nonfinite_metric_rejected(self):
        obs = [dict(x) for x in self.observations]
        obs[0]["metric_value"] = math.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            self.analyze(obs)


if __name__ == "__main__":
    unittest.main()
