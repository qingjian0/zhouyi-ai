import unittest

from prototype.e02i2c_hidden_event_benchmark import EventType, build_episode
from prototype.e02i2c_metadata_attack import (
    CategoricalNaiveBayes,
    ShallowCategoricalTree,
    extract_features,
    run_metadata_attack,
)


class E02I2CMetadataAttackTests(unittest.TestCase):
    def test_m0_contains_only_identifier_surface_features(self):
        episode = build_episode(EventType.MODIFY, 1010, split="train")
        features = extract_features(episode.observation, "M0")
        self.assertTrue(features)
        self.assertTrue(all(key.startswith("id.") for key in features))
        self.assertFalse(any("split" in key for key in features))
        self.assertFalse(any("polarity" in key for key in features))
        self.assertNotIn("a^b", repr(features))

    def test_m1_excludes_evaluator_split_and_semantic_fields(self):
        episode = build_episode(EventType.MODIFY, 1010, split="train")
        features = extract_features(episode.observation, "M1")
        self.assertTrue(any(key.startswith("op.") for key in features))
        self.assertFalse(any("ctx." in key for key in features))
        self.assertFalse(any("split" in key for key in features))
        self.assertFalse(any("polarity" in key for key in features))
        self.assertNotIn("a^b", repr(features))

    def test_m2_adds_only_context_shape_not_literal_signature(self):
        episode = build_episode(EventType.MODIFY, 1010, split="train")
        features = extract_features(episode.observation, "M2")
        self.assertEqual(features["ctx.identity_present"], "True")
        self.assertEqual(features["ctx.identity_status"], "ACTIVE")
        self.assertIn("ctx.candidate_shape", features)
        self.assertNotIn("a^b", repr(features))
        self.assertFalse(any("identity_id" in key or "version_id" in key for key in features))

    def test_unknown_tier_is_rejected(self):
        episode = build_episode(EventType.KEEP, 1010, split="train")
        with self.assertRaises(ValueError):
            extract_features(episode.observation, "M3")

    def test_naive_bayes_and_tree_are_deterministic(self):
        rows = [
            {"window_count": "1", "identity": "active"},
            {"window_count": "2", "identity": "active"},
            {"window_count": "2", "identity": "suspended"},
            {"window_count": "1", "identity": "active"},
        ]
        labels = ["KEEP", "MODIFY", "RETIRE", "KEEP"]
        nb = CategoricalNaiveBayes().fit(rows, labels)
        tree = ShallowCategoricalTree(max_depth=3).fit(rows, labels)
        self.assertEqual(nb.predict(rows), nb.predict(rows))
        self.assertEqual(tree.predict(rows), tree.predict(rows))

    def test_preregistered_run_rejects_fewer_than_thirty_seed_blocks(self):
        with self.assertRaises(ValueError):
            run_metadata_attack(seeds=29, bootstrap_samples=100)


if __name__ == "__main__":
    unittest.main()
