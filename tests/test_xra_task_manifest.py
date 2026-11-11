import unittest
from prototype.xra_task_manifest import EvidenceProvenance, TaskManifest, validate_learner_payload

def raw_manifest():
    return {
        "task_id": "task-opaque-01", "episode_id": "episode-opaque-01",
        "actions": ["probe", "wait"], "observation_schema_version": "obs-v1",
        "representation_version": "repr-v1", "split": "train",
        "action_costs": {"probe": 2.0, "wait": 0.5}, "horizon": 5,
        "challenge_protocol": "paired_deterministic_v1",
        "missingness_semantics": "missing_is_unobserved_not_match",
    }

class XRATaskManifestTests(unittest.TestCase):
    def test_public_payload(self):
        manifest = TaskManifest.from_mapping(raw_manifest())
        payload = manifest.learner_payload()
        validate_learner_payload(payload)
        self.assertEqual(payload["actions"], ["probe", "wait"])

    def test_rejects_schema_and_duplicate_actions(self):
        raw = raw_manifest(); del raw["split"]
        with self.assertRaises(ValueError): TaskManifest.from_mapping(raw)
        raw = raw_manifest(); raw["true_partition"] = []
        with self.assertRaises(ValueError): TaskManifest.from_mapping(raw)
        raw = raw_manifest(); raw["actions"] = ["probe", "probe"]
        with self.assertRaises(ValueError): TaskManifest.from_mapping(raw)

    def test_rejects_bad_cost_and_horizon(self):
        raw = raw_manifest(); raw["action_costs"]["wait"] = 0
        with self.assertRaises(ValueError): TaskManifest.from_mapping(raw)
        raw = raw_manifest(); raw["horizon"] = True
        with self.assertRaises(ValueError): TaskManifest.from_mapping(raw)

    def test_recursive_leakage_guard(self):
        with self.assertRaises(ValueError):
            validate_learner_payload({"debug": [{"generator_seed": 4}]})

    def test_provenance_version_must_match(self):
        manifest = TaskManifest.from_mapping(raw_manifest())
        record = EvidenceProvenance(manifest.task_id, manifest.episode_id, "t1", "probe",
            "old-repr", manifest.observation_schema_version, manifest.split, "observed", 1.0)
        with self.assertRaises(ValueError): record.validate_against(manifest)

    def test_missing_is_not_a_matching_observation(self):
        manifest = TaskManifest.from_mapping(raw_manifest())
        record = EvidenceProvenance(manifest.task_id, manifest.episode_id, "t2", "probe",
            manifest.representation_version, manifest.observation_schema_version,
            manifest.split, "missing", 0.0)
        record.validate_against(manifest)

if __name__ == "__main__": unittest.main()
