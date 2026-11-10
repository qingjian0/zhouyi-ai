import unittest

from prototype.e10a_generator import (
    build_split_manifest, generate_episode,
)


class E10AGeneratorTests(unittest.TestCase):
    def test_truth_is_separate_from_learner_view(self):
        episode = generate_episode(7)
        view = episode.learner_view()
        self.assertIn("objects", view)
        self.assertIn("observations", view)
        self.assertNotIn("truth", view)
        self.assertNotIn("role_names", repr(view))
        self.assertTrue(episode.audit_view()["relations"])

    def test_generation_is_deterministic_for_seed(self):
        left = generate_episode(11).learner_view()
        right = generate_episode(11).learner_view()
        self.assertEqual(left, right)

    def test_surface_symbols_change_across_seeds(self):
        left = generate_episode(11).learner_view()
        right = generate_episode(12).learner_view()
        left_ids = {row["object_id"] for row in left["objects"]}
        right_ids = {row["object_id"] for row in right["objects"]}
        self.assertTrue(left_ids.isdisjoint(right_ids))

    def test_role_order_is_preserved_while_record_order_is_not_semantic(self):
        episode = generate_episode(19, relation_count=7)
        learner = episode.learner_view()
        audit = episode.audit_view()["relations"]
        by_symbol = {}
        for row in audit:
            by_symbol.setdefault(row["relation_symbol"], []).append(row)
        self.assertEqual(len(learner["observations"]), 7)
        self.assertTrue(all(len(row["role_objects"]) == len(row["role_names"])
                            for row in audit))

    def test_split_rejects_object_identity_overlap(self):
        train = generate_episode(1)
        test = generate_episode(2)
        # Force an identity collision without changing the rest of the episode.
        from dataclasses import replace
        test = replace(test, objects=(replace(test.objects[0],
                                              object_id=train.objects[0].object_id),
                                      *test.objects[1:]))
        with self.assertRaises(ValueError):
            build_split_manifest([train], [test],
                                 train_ids=["train-0"], test_ids=["test-0"])

    def test_split_accepts_disjoint_episodes(self):
        train = generate_episode(21)
        test = generate_episode(22)
        manifest = build_split_manifest([train], [test],
                                        train_ids=["train-0"], test_ids=["test-0"])
        self.assertFalse(set(manifest.train_object_ids)
                         & set(manifest.test_object_ids))

    def test_invalid_generator_parameters_fail_closed(self):
        with self.assertRaises(ValueError):
            generate_episode(1, object_count=2)
        with self.assertRaises(ValueError):
            generate_episode(1, missing_rate=1.0)


if __name__ == "__main__":
    unittest.main()
