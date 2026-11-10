import copy
import json
import unittest

from prototype.e10a_object_disjoint import build_object_disjoint_task


class E10AObjectDisjointTests(unittest.TestCase):
    def test_object_pools_are_disjoint_and_observations_stay_in_pool(self):
        support, query, truth = build_object_disjoint_task(901)
        support_ids = {row["object_id"] for row in support["objects"]}
        query_ids = {row["object_id"] for row in query["objects"]}
        self.assertTrue(support_ids)
        self.assertTrue(query_ids)
        self.assertFalse(support_ids & query_ids)
        self.assertEqual(truth["audit"]["object_id_intersection"], [])
        for row in support["observations"]:
            self.assertTrue(set(row["participants"]) <= support_ids)
        for row in query["observations"]:
            self.assertTrue(set(row["participants"]) <= query_ids)

    def test_same_mechanism_but_distinct_object_identities(self):
        support, query, truth = build_object_disjoint_task(902)
        self.assertEqual(support["mechanism_hash"], query["mechanism_hash"])
        self.assertEqual(support["mechanism_hash"], truth["mechanism_hash"])
        self.assertNotEqual(
            {x["object_id"] for x in support["objects"]},
            {x["object_id"] for x in query["objects"]},
        )

    def test_query_labels_and_truth_annotations_are_hidden(self):
        support, query, truth = build_object_disjoint_task(903)
        forbidden = {"outcome", "valid", "violation", "template_id",
                     "role_objects", "source_group_id"}
        for row in query["observations"]:
            self.assertFalse(forbidden.intersection(row))
        self.assertTrue(all("outcome" in row for row in support["observations"]))
        self.assertTrue(truth["query_truth"])

    def test_query_objects_are_absent_from_support_payload(self):
        support, query, _ = build_object_disjoint_task(904)
        serialized = json.dumps(support, sort_keys=True)
        for row in query["objects"]:
            self.assertNotIn(row["object_id"], serialized)
            self.assertNotIn(json.dumps(row, sort_keys=True), serialized)

    def test_source_instance_variants_stay_together_within_each_pool(self):
        _, _, truth = build_object_disjoint_task(905)
        for key in ("support_truth", "query_truth"):
            partitions = {}
            for row in truth[key]:
                partitions.setdefault(row["source_group_id"], set()).add(row["valid"])
            # Each source group has exactly one positive and >= one negative.
            for labels in partitions.values():
                self.assertIn(True, labels)
                self.assertIn(False, labels)

    def test_deterministic_and_independent_rng_streams(self):
        left = build_object_disjoint_task(906)
        right = build_object_disjoint_task(906)
        self.assertEqual(left, right)
        # Changing the number of examples changes rows but keeps the mechanism.
        changed = build_object_disjoint_task(906, instances_per_template=7)
        self.assertEqual(left[0]["mechanism_hash"], changed[0]["mechanism_hash"])

    def test_invalid_arguments_fail_closed(self):
        for seed in (True, "1", 1.2):
            with self.assertRaises(ValueError):
                build_object_disjoint_task(seed)
        for count in (True, 1, 1.5, "3"):
            with self.assertRaises(ValueError):
                build_object_disjoint_task(1, instances_per_template=count)

    def test_query_truth_mutation_does_not_change_learner_payloads(self):
        support, query, truth = build_object_disjoint_task(907)
        support_before = json.dumps(support, sort_keys=True)
        query_before = json.dumps(query, sort_keys=True)
        changed = copy.deepcopy(truth)
        for row in changed["query_truth"]:
            row["valid"] = not row["valid"]
            row["violation"] = "mutated"
        self.assertEqual(support_before, json.dumps(support, sort_keys=True))
        self.assertEqual(query_before, json.dumps(query, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
