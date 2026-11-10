import unittest

from prototype.e10b_concept_reviser import ConceptReviser


class ConceptReviserTests(unittest.TestCase):
    def _observe(self, learner, prefix, color, target, noise=None):
        return learner.observe(
            observation_id=f"{prefix}-obs",
            entity_id=f"{prefix}-entity",
            features={"color": color, "noise": noise or prefix},
            target=target,
        )

    def test_splits_broad_concept_when_feature_predictively_separates_evidence(self):
        learner = ConceptReviser(min_members_per_child=2, min_split_gain=0.2)
        self._observe(learner, "r1", "red", True)
        self._observe(learner, "r2", "red", True)
        self._observe(learner, "b1", "blue", False)
        snapshot = self._observe(learner, "b2", "blue", False)
        split_events = [event for event in snapshot["events"] if event["operation"] == "split"]
        self.assertEqual(len(split_events), 1)
        self.assertEqual(split_events[0]["feature_key"], "color")
        self.assertEqual(len(snapshot["active_concepts"]), 2)
        self.assertEqual(learner.predict_concept({"color": "red"})["decision_status"], "ASSIGN")
        self.assertEqual(
            learner.predict_concept({"color": "green"})["decision_status"],
            "ABSTAIN_UNSEEN_CONCEPT_BRANCH",
        )

    def test_unique_noise_feature_cannot_force_a_split(self):
        learner = ConceptReviser(min_members_per_child=2, min_split_gain=0.0)
        for index in range(8):
            self._observe(learner, f"noise-{index}", "same", index % 2 == 0)
        self.assertFalse(any(event["operation"] == "split" for event in learner.snapshot()["events"]))
        self.assertEqual(len(learner.snapshot()["active_concepts"]), 1)

    def test_sibling_concepts_merge_when_evidence_makes_them_equivalent(self):
        learner = ConceptReviser(
            min_members_per_child=2,
            min_split_gain=0.2,
            merge_rate_tolerance=0.35,
        )
        self._observe(learner, "r1", "red", True)
        self._observe(learner, "r2", "red", True)
        self._observe(learner, "b1", "blue", False)
        split_snapshot = self._observe(learner, "b2", "blue", False)
        self.assertEqual(len(split_snapshot["active_concepts"]), 2)

        self._observe(learner, "r3", "red", False)
        merged = self._observe(learner, "b3", "blue", True)
        merge_events = [event for event in merged["events"] if event["operation"] == "merge"]
        self.assertEqual(len(merge_events), 1)
        self.assertEqual(len(merged["active_concepts"]), 1)
        self.assertEqual(merged["active_concepts"][0]["concept_id"], "concept-root")

    def test_duplicate_observation_or_entity_is_rejected_without_mutation(self):
        learner = ConceptReviser()
        self._observe(learner, "one", "red", True)
        before = learner.snapshot()
        with self.assertRaisesRegex(ValueError, "observation_id"):
            learner.observe(
                observation_id="one-obs",
                entity_id="another",
                features={"color": "blue"},
                target=False,
            )
        with self.assertRaisesRegex(ValueError, "entity_id"):
            learner.observe(
                observation_id="two-obs",
                entity_id="one-entity",
                features={"color": "blue"},
                target=False,
            )
        self.assertEqual(learner.snapshot(), before)

    def test_missing_split_feature_abstains_instead_of_guessing(self):
        learner = ConceptReviser(min_members_per_child=2, min_split_gain=0.2)
        for prefix, color, target in (
            ("r1", "red", True), ("r2", "red", True),
            ("b1", "blue", False), ("b2", "blue", False),
        ):
            self._observe(learner, prefix, color, target)
        result = learner.predict_concept({"noise": "x"})
        self.assertEqual(result["decision_status"], "ABSTAIN_UNSEEN_CONCEPT_BRANCH")


if __name__ == "__main__":
    unittest.main()
