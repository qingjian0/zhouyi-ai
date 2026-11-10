import unittest

from prototype.e10_structural_concepts import (
    ConceptFormationError, Observation, StructuralConceptLearner,
    synthetic_observations,
)


class E10StructuralConceptTests(unittest.TestCase):
    def test_recovers_recurring_bundles_without_target_labels(self):
        learner = StructuralConceptLearner(min_support=4).fit(
            synthetic_observations(17)
        )
        bundles = {
            tuple(item["features"])
            for item in learner.snapshot()["candidates"]
            if item["kind"] == "attribute_bundle"
        }
        self.assertIn(("amber", "resonant", "spiral"), bundles)
        self.assertIn(("cobalt", "conductive", "lattice"), bundles)
        self.assertFalse(learner.report["target_labels_received"])
        self.assertEqual(learner.report["gradient_updates"], 0)

    def test_hard_near_misses_do_not_form_full_motif(self):
        learner = StructuralConceptLearner(min_support=4).fit(
            synthetic_observations(17)
        )
        candidates = {
            tuple(item["features"])
            for item in learner.snapshot()["candidates"]
            if item["kind"] == "attribute_bundle"
        }
        self.assertNotIn(("amber", "decoy-0", "spiral"), candidates)

    def test_object_id_renaming_and_row_order_do_not_change_discovered_patterns(self):
        baseline = StructuralConceptLearner(min_support=4).fit(
            synthetic_observations(29)
        )
        transformed = StructuralConceptLearner(min_support=4).fit(
            synthetic_observations(29, rename=True, shuffle=True)
        )
        key = lambda learner: [
            (item["kind"], tuple(item["features"]), item["support"])
            for item in learner.snapshot()["candidates"]
        ]
        self.assertEqual(key(baseline), key(transformed))

    def test_duplicate_object_ids_rejected(self):
        rows = (
            Observation("same", frozenset({"a"})),
            Observation("same", frozenset({"b"})),
        )
        with self.assertRaises(ConceptFormationError):
            StructuralConceptLearner().fit(rows)

    def test_candidate_budget_is_enforced(self):
        rows = synthetic_observations(17)
        with self.assertRaises(ConceptFormationError):
            StructuralConceptLearner(max_candidates=2).fit(rows)

    def test_support_counts_distinct_objects_not_repeated_features(self):
        rows = (
            Observation("one", frozenset({"a", "b"})),
            Observation("two", frozenset({"a", "b"})),
            Observation("three", frozenset({"a", "b"})),
        )
        learner = StructuralConceptLearner(min_support=3).fit(rows)
        candidate = next(
            item for item in learner.snapshot()["candidates"]
            if item["features"] == ["a", "b"]
        )
        self.assertEqual(candidate["support"], 3)


if __name__ == "__main__":
    unittest.main()
