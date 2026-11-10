import copy
import unittest

from prototype.e10a_latent_generator import generate_episode
from prototype.e10a_task_split import build_support_query_task


class E10ATaskSplitTests(unittest.TestCase):
    def _views(self, seed=701):
        episode = generate_episode(seed, instances_per_template=6)
        return episode, episode.learner_view(), episode.audit_view()

    def _task(self, seed=701, split_seed=41):
        episode, learner, evaluator = self._views(seed)
        return episode, build_support_query_task(
            learner, evaluator, seed=split_seed, query_fraction=0.3
        )

    def test_query_view_has_no_labels_or_evaluator_fields(self):
        _, task = self._task()
        forbidden = {"outcome", "valid", "violation", "template_id", "family"}
        for row in task["query"]["observations"]:
            self.assertFalse(forbidden.intersection(row))
        self.assertEqual(
            set(task["evaluator_truth"]),
            {row["observation_id"] for row in task["query"]["observations"]},
        )

    def test_related_participant_groups_never_cross_partitions(self):
        _, task = self._task()

        def key(row):
            return row["relation_symbol"], tuple(sorted(row["participants"]))

        support = {key(row) for row in task["support"]["observations"]}
        query = {key(row) for row in task["query"]["observations"]}
        self.assertFalse(support & query)

    def test_split_is_deterministic_and_manifest_is_auditable(self):
        _, learner, evaluator = self._views(702)
        left = build_support_query_task(learner, evaluator, seed=77)
        right = build_support_query_task(learner, evaluator, seed=77)
        self.assertEqual(left, right)
        manifest = left["manifest"]
        self.assertEqual(manifest["split_seed"], 77)
        self.assertEqual(
            manifest["selection_policy"], "label_blind_uniform_group_shuffle_v1"
        )
        self.assertGreater(manifest["query_group_count"], 0)
        self.assertIn("support_label_counts", manifest)
        self.assertNotIn("query_label_counts_evaluator_only", manifest)

    def test_source_group_split_keeps_all_derived_observations_together(self):
        _, learner, evaluator = self._views(709)
        task = build_support_query_task(
            learner, evaluator, seed=83, grouping_policy="source_group"
        )
        source_by_observation = {
            row["observation_id"]: row["source_group_id"]
            for row in evaluator["instances"]
        }
        support_ids = {
            row["observation_id"] for row in task["support"]["observations"]
        }
        query_ids = {
            row["observation_id"] for row in task["query"]["observations"]
        }
        partitions_by_source = {}
        for observation_id, source_group_id in source_by_observation.items():
            partition = "support" if observation_id in support_ids else "query"
            partitions_by_source.setdefault(source_group_id, set()).add(partition)
        self.assertTrue(all(len(partitions) == 1
                            for partitions in partitions_by_source.values()))
        self.assertEqual(task["manifest"]["grouping_policy"], "source_group")
        self.assertEqual(
            task["manifest"]["grouping"],
            "relation_symbol+evaluator_source_group_id",
        )
        for row in task["support"]["observations"] + task["query"]["observations"]:
            self.assertNotIn("source_group_id", row)
        self.assertEqual(
            sum(task["manifest"]["support_group_size_histogram"].values()),
            task["manifest"]["support_group_count"],
        )
        self.assertEqual(
            sum(task["manifest"]["query_group_size_histogram"].values()),
            task["manifest"]["query_group_count"],
        )

    def test_source_group_assignment_ignores_evaluator_labels_and_metadata(self):
        _, learner, evaluator = self._views(710)
        changed_learner = copy.deepcopy(learner)
        changed_evaluator = copy.deepcopy(evaluator)
        for row in changed_learner["observations"]:
            row["outcome"] = not row["outcome"]
        for row in changed_evaluator["instances"]:
            row["valid"] = not row["valid"]
            row["violation"] = "mutated"
            row["template_id"] = "opaque-mutated-template"
        original = build_support_query_task(
            learner, evaluator, seed=89, grouping_policy="source_group"
        )
        changed = build_support_query_task(
            changed_learner, changed_evaluator, seed=89,
            grouping_policy="source_group"
        )
        original_ids = [r["observation_id"] for r in original["query"]["observations"]]
        changed_ids = [r["observation_id"] for r in changed["query"]["observations"]]
        self.assertEqual(original_ids, changed_ids)

    def test_source_group_policy_rejects_missing_provenance(self):
        _, learner, evaluator = self._views(711)
        del evaluator["instances"][0]["source_group_id"]
        with self.assertRaisesRegex(ValueError, "source_group_id"):
            build_support_query_task(
                learner, evaluator, seed=97, grouping_policy="source_group"
            )

    def test_query_assignment_is_invariant_to_hidden_label_mutation(self):
        _, learner, evaluator = self._views(704)
        changed_learner = copy.deepcopy(learner)
        changed_evaluator = copy.deepcopy(evaluator)
        for row in changed_learner["observations"]:
            row["outcome"] = not row["outcome"]
        for row in changed_evaluator["instances"]:
            row["valid"] = not row["valid"]

        original = build_support_query_task(learner, evaluator, seed=81)
        changed = build_support_query_task(changed_learner, changed_evaluator, seed=81)
        original_ids = [r["observation_id"] for r in original["query"]["observations"]]
        changed_ids = [r["observation_id"] for r in changed["query"]["observations"]]
        self.assertEqual(original_ids, changed_ids)

    def test_every_observation_is_assigned_exactly_once(self):
        episode, task = self._task()
        source = {row.observation_id for row in episode.observations}
        support = {row["observation_id"] for row in task["support"]["observations"]}
        query = {row["observation_id"] for row in task["query"]["observations"]}
        self.assertFalse(support & query)
        self.assertEqual(support | query, source)

    def test_duplicate_evaluator_ids_are_rejected(self):
        _, learner, evaluator = self._views(705)
        evaluator["instances"].append(copy.deepcopy(evaluator["instances"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate evaluator"):
            build_support_query_task(learner, evaluator, seed=1)

    def test_non_boolean_labels_and_inconsistent_labels_are_rejected(self):
        _, learner, evaluator = self._views(706)
        malformed = copy.deepcopy(evaluator)
        malformed["instances"][0]["valid"] = 1
        with self.assertRaisesRegex(ValueError, "exact boolean"):
            build_support_query_task(learner, malformed, seed=1)

        inconsistent = copy.deepcopy(learner)
        inconsistent["observations"][0]["outcome"] = not inconsistent["observations"][0]["outcome"]
        with self.assertRaisesRegex(ValueError, "label mismatch"):
            build_support_query_task(inconsistent, evaluator, seed=1)

    def test_unknown_schema_and_duplicate_participants_fail_closed(self):
        _, learner, evaluator = self._views(707)
        unknown = copy.deepcopy(learner)
        unknown["schema_version"] = "future-or-unknown"
        with self.assertRaisesRegex(ValueError, "unsupported learner schema"):
            build_support_query_task(unknown, evaluator, seed=1)

        malformed = copy.deepcopy(learner)
        malformed["observations"][0]["participants"] = [
            malformed["observations"][0]["participants"][0],
            malformed["observations"][0]["participants"][0],
        ]
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            build_support_query_task(malformed, evaluator, seed=1)

    def test_invalid_fraction_and_seed_fail_closed(self):
        _, learner, evaluator = self._views(708)
        for fraction in (1.0, 0.0, True, "0.2"):
            with self.subTest(fraction=fraction):
                with self.assertRaises(ValueError):
                    build_support_query_task(
                        learner, evaluator, seed=1, query_fraction=fraction
                    )
        with self.assertRaisesRegex(ValueError, "seed must be an integer"):
            build_support_query_task(learner, evaluator, seed=True)


if __name__ == "__main__":
    unittest.main()
