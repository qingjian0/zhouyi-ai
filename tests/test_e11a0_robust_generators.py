import unittest

from prototype.e11a0_robust_generators import (
    PRIVATE_SCHEMAS, SHARED_SCHEMAS, make_robust_episode,
)


def nuisance_rate(objects, truth, *, member):
    selected = [
        obj for obj in objects
        if ("concept-a" in truth[obj.object_id]) == member
    ]
    if not selected:
        raise AssertionError("test fixture produced an empty membership group")
    return sum("nuisance-77" in obj.attributes for obj in selected) / len(selected)


class E11A0RobustGeneratorTests(unittest.TestCase):
    def test_reproducible_and_object_disjoint(self):
        a = make_robust_episode(11, mode="missing-noisy", objects_per_split=90)
        b = make_robust_episode(11, mode="missing-noisy", objects_per_split=90)
        self.assertEqual(a, b)
        learner_ids = {obj.object_id for obj in a.learner_objects}
        query_ids = {obj.object_id for obj in a.query_objects}
        self.assertTrue(learner_ids.isdisjoint(query_ids))

    def test_missing_noisy_arm_has_incomplete_and_spurious_attributes(self):
        episode = make_robust_episode(
            21, mode="missing-noisy", objects_per_split=180,
            missing_rate=0.25, false_positive_rate=0.12,
        )
        member_objects = [
            obj for obj in episode.learner_objects
            if "concept-a" in episode.truth[obj.object_id]
        ]
        self.assertTrue(member_objects)
        self.assertTrue(any(
            not PRIVATE_SCHEMAS["concept-a"].issubset(obj.attributes)
            for obj in member_objects
        ))
        self.assertTrue(any(
            any(attr.startswith("a-")
                for attr in obj.attributes)
            and "concept-a" not in episode.truth[obj.object_id]
            for obj in episode.learner_objects
        ))

    def test_shared_attribute_is_not_unique_concept_identifier(self):
        episode = make_robust_episode(
            5, mode="shared-attribute", objects_per_split=60
        )
        self.assertEqual(
            SHARED_SCHEMAS["concept-a"] & SHARED_SCHEMAS["concept-b"],
            frozenset({"shared-00"}),
        )
        self.assertTrue(all(
            ("shared-00" in obj.attributes)
            == bool(episode.truth[obj.object_id])
            for obj in episode.learner_objects + episode.query_objects
        ))

    def test_nuisance_correlation_reverses_across_environments(self):
        episode = make_robust_episode(
            29, mode="nuisance-confounded", objects_per_split=500
        )
        train_member = nuisance_rate(
            episode.learner_objects, episode.truth, member=True
        )
        train_nonmember = nuisance_rate(
            episode.learner_objects, episode.truth, member=False
        )
        query_member = nuisance_rate(
            episode.query_objects, episode.truth, member=True
        )
        query_nonmember = nuisance_rate(
            episode.query_objects, episode.truth, member=False
        )
        self.assertGreater(train_member, train_nonmember + 0.35)
        self.assertGreater(query_nonmember, query_member + 0.35)
        self.assertEqual({o.environment for o in episode.learner_objects}, {"env-0"})
        self.assertEqual({o.environment for o in episode.query_objects}, {"env-1"})

    def test_variable_concept_count_is_hidden_from_learner_view(self):
        small = make_robust_episode(
            12, mode="variable-concept-count", objects_per_split=60
        )
        large = make_robust_episode(
            15, mode="variable-concept-count", objects_per_split=60
        )
        self.assertEqual(len(small.hidden_schemas), 2)
        self.assertEqual(len(large.hidden_schemas), 5)
        self.assertTrue(all(
            2 <= len(schema) <= 4
            for schema in large.hidden_schemas.values()
        ))
        self.assertTrue(all(
            not hasattr(obj, "concepts") and not hasattr(obj, "membership")
            for obj in small.learner_objects + small.query_objects
        ))
        self.assertTrue({
            obj.object_id for obj in small.learner_objects
        }.isdisjoint({
            obj.object_id for obj in small.query_objects
        }))

    def test_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            make_robust_episode(mode="unknown")
        with self.assertRaises(ValueError):
            make_robust_episode(objects_per_split=10)
        with self.assertRaises(ValueError):
            make_robust_episode(missing_rate=1.0)


if __name__ == "__main__":
    unittest.main()
