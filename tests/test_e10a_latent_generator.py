import unittest

from prototype.e10a_latent_generator import (
    GENERATOR_VERSION,
    build_split_manifest,
    generate_episode,
)


class E10ALatentGeneratorTests(unittest.TestCase):
    def test_repeated_latent_templates_generate_positive_and_negative_evidence(self):
        episode = generate_episode(101)
        learner = episode.learner_view()
        audit = episode.audit_view()
        self.assertEqual(len(audit["templates"]), 2)
        self.assertTrue(any(row["outcome"] for row in learner["observations"]))
        self.assertTrue(any(not row["outcome"] for row in learner["observations"]))
        for template in audit["templates"]:
            matching = [row for row in audit["instances"]
                        if row["template_id"] == template["template_id"]]
            self.assertGreaterEqual(sum(row["valid"] for row in matching), 2)
            self.assertTrue(any(not row["valid"] for row in matching))

    def test_learner_view_does_not_expose_latent_role_or_template_truth(self):
        episode = generate_episode(102)
        view = episode.learner_view()
        self.assertNotIn("templates", view)
        self.assertNotIn("instances", view)
        self.assertNotIn("role_objects", repr(view))
        self.assertNotIn("template_id", repr(view))
        self.assertNotIn("feature_key", repr(view))

    def test_participant_presentation_order_is_not_role_order(self):
        episode = generate_episode(103, instances_per_template=5)
        truth = {row.observation_id: row
                 for row in episode.instances}
        observations = {row.observation_id: row
                        for row in episode.observations}
        self.assertTrue(any(
            observations[key].participants != truth[key].role_objects
            for key in truth
        ))

    def test_role_constraints_and_context_are_reusable(self):
        episode = generate_episode(104)
        object_map = {row.object_id: dict(row.attributes)
                      for row in episode.objects}
        templates = {row.template_id: row for row in episode.templates}
        for instance in episode.instances:
            template = templates[instance.template_id]
            if instance.valid:
                self.assertEqual(
                    tuple(object_map[obj][template.feature_key]
                          for obj in instance.role_objects),
                    template.role_values,
                )
                observation = next(row for row in episode.observations
                                   if row.observation_id == instance.observation_id)
                self.assertEqual(dict(observation.context)[template.context_key],
                                 template.required_context)

    def test_generator_identifiability_prerequisites(self):
        episode = generate_episode(105)
        report = episode.identifiability_report()
        self.assertTrue(all(row["identifiable_up_to_role_permutation"]
                            for row in report.values()))

    def test_determinism_and_symbol_renaming(self):
        left = generate_episode(106)
        same = generate_episode(106)
        other = generate_episode(107)
        self.assertEqual(left.learner_view(), same.learner_view())
        left_symbols = {obj.object_id for obj in left.objects}
        other_symbols = {obj.object_id for obj in other.objects}
        self.assertTrue(left_symbols.isdisjoint(other_symbols))
        self.assertNotEqual(left.learner_view(), other.learner_view())

    def test_split_manifest_separates_identity_and_hashes(self):
        train = [generate_episode(201), generate_episode(202)]
        test = [generate_episode(301), generate_episode(302)]
        manifest = build_split_manifest(train, test)
        self.assertEqual(manifest.generator_version, GENERATOR_VERSION)
        self.assertFalse(set(manifest.train_object_ids)
                         & set(manifest.test_object_ids))
        self.assertNotEqual(manifest.train_learner_hash, manifest.test_learner_hash)
        self.assertNotEqual(manifest.train_truth_hash, manifest.test_truth_hash)

    def test_split_rejects_identity_leakage(self):
        shared = generate_episode(401)
        with self.assertRaises(ValueError):
            build_split_manifest([shared], [shared])

    def test_invalid_generator_parameters_fail_closed(self):
        with self.assertRaises(ValueError):
            generate_episode(1, object_count=5)
        with self.assertRaises(ValueError):
            generate_episode(1, template_count=5, attribute_count=4)
        with self.assertRaises(ValueError):
            generate_episode(1, instances_per_template=1)


if __name__ == "__main__":
    unittest.main()
