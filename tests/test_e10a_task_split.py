import unittest

from prototype.e10a_latent_generator import generate_episode
from prototype.e10a_task_split import build_support_query_task


class E10ATaskSplitTests(unittest.TestCase):
    def _task(self, seed=701, split_seed=41):
        episode = generate_episode(seed, instances_per_template=6)
        return episode, build_support_query_task(
            episode.learner_view(), episode.audit_view(),
            seed=split_seed, query_fraction=0.3,
        )

    def test_query_view_has_no_labels_or_evaluator_fields(self):
        _, task = self._task()
        for row in task["query"]["observations"]:
            self.assertNotIn("outcome", row)
            self.assertNotIn("valid", row)
            self.assertNotIn("violation", row)
            self.assertNotIn("template_id", row)
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

    def test_support_retains_both_labels_for_each_relation(self):
        _, task = self._task()
        for relation in {row["relation_symbol"]
                         for row in task["support"]["observations"]}:
            labels = {row["outcome"] for row in task["support"]["observations"]
                      if row["relation_symbol"] == relation}
            self.assertEqual(labels, {False, True})

    def test_split_is_deterministic_and_manifest_is_auditable(self):
        episode = generate_episode(702, instances_per_template=6)
        learner, evaluator = episode.learner_view(), episode.audit_view()
        left = build_support_query_task(learner, evaluator, seed=77)
        right = build_support_query_task(learner, evaluator, seed=77)
        self.assertEqual(left, right)
        self.assertEqual(left["manifest"]["split_seed"], 77)
        self.assertGreater(left["manifest"]["query_group_count"], 0)

    def test_every_observation_is_assigned_exactly_once(self):
        episode, task = self._task()
        source = {row["observation_id"] for row in episode.observations}
        support = {row["observation_id"] for row in task["support"]["observations"]}
        query = {row["observation_id"] for row in task["query"]["observations"]}
        self.assertFalse(support & query)
        self.assertEqual(support | query, source)

    def test_invalid_fraction_and_mismatched_views_fail_closed(self):
        episode = generate_episode(703, instances_per_template=6)
        learner, evaluator = episode.learner_view(), episode.audit_view()
        with self.assertRaises(ValueError):
            build_support_query_task(learner, evaluator, seed=1,
                                     query_fraction=1.0)
        evaluator["episode_id"] = "wrong-episode"
        with self.assertRaises(ValueError):
            build_support_query_task(learner, evaluator, seed=1)


if __name__ == "__main__":
    unittest.main()
