import unittest

from prototype.e10a_structural_ood import build_structural_ood_task
from prototype.e10a_primitive_expansion import PrimitiveExpansionLearner
from prototype.e10a_mechanism_learner import E10AMechanismLearner
from prototype.e10a_prequential_ledger import PrequentialLedger


def _novel_relation_episode(seed=3301):
    support, _, _ = build_structural_ood_task(seed)
    values = ("rough", "smooth", "matte")
    objects = []
    for role, value in enumerate(values):
        for n in range(2):
            objects.append({
                "object_id": f"novel-{role}-{n}",
                "attributes": [["shape_class", "blob"], ["texture_class", value]],
            })
    objects.append({
        "object_id": "novel-distractor",
        "attributes": [["shape_class", "blob"], ["texture_class", "rough"]],
    })
    def row(oid, participants, phase, permission):
        return {
            "observation_id": oid,
            "relation_symbol": "aligns",
            "participants": participants,
            "context": [["phase", phase], ["permission", permission]],
        }
    query = [
        row("q-positive-1", ["novel-0-0", "novel-1-0", "novel-2-0"], "active", "granted"),
        row("q-negative-context", ["novel-0-0", "novel-1-0", "novel-2-0"], "active", "denied"),
        row("q-positive-2", ["novel-0-1", "novel-1-1", "novel-2-1"], "active", "granted"),
        row("q-negative-role", ["novel-0-1", "novel-1-1", "novel-distractor"], "active", "granted"),
        row("q-negative-phase", ["novel-0-1", "novel-1-1", "novel-2-1"], "inactive", "granted"),
    ]
    labels = [True, False, True, False, False]
    return support, objects, query, labels


class PrimitiveExpansionTests(unittest.TestCase):
    def test_discovers_new_relation_and_feature_only_from_revealed_evidence(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support)
        learner.add_query_objects(objects)

        before = learner.predict(query[0])
        self.assertEqual(before["decision_status"], "ABSTAIN_INCONSISTENT")
        self.assertEqual(learner.candidate_count, 1)  # unrelated Support mechanism only

        first = learner.revise(query[0], labels[0])
        self.assertEqual(first["operation"], "expand")
        self.assertEqual(first["status"], "PROVISIONAL")
        self.assertEqual(learner.predict(query[2])["decision_status"], "ABSTAIN_AMBIGUOUS")

        second = learner.revise(query[1], labels[1])
        self.assertEqual(second["status"], "IDENTIFIED")
        self.assertEqual(learner.candidate_count, 2)  # old relation + newly proposed relation
        decision = learner.predict(query[2])
        self.assertEqual(decision["decision_status"], "PREDICT")
        self.assertTrue(decision["prediction"])

    def test_new_primitive_is_filtered_by_later_role_and_context_counterexamples(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support)
        learner.add_query_objects(objects)
        learner.revise(query[0], labels[0])
        learner.revise(query[1], labels[1])
        learner.revise(query[2], labels[2])
        self.assertFalse(learner.predict(query[3])["prediction"])
        role_revision = learner.revise(query[3], labels[3])
        self.assertEqual(role_revision["status"], "IDENTIFIED")
        self.assertFalse(learner.predict(query[3])["prediction"])
        phase_revision = learner.revise(query[4], labels[4])
        self.assertEqual(phase_revision["status"], "IDENTIFIED")
        self.assertFalse(learner.predict(query[4])["prediction"])

    def test_budget_exhaustion_fails_closed(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support, proposal_budget=1)
        learner.add_query_objects(objects)
        revision = learner.revise(query[0], labels[0])
        self.assertTrue(revision["budget_exceeded"])
        self.assertEqual(revision["operation"], "abstain")
        self.assertEqual(learner.predict(query[0])["decision_status"], "ABSTAIN_BUDGET")


    def test_expansion_revision_is_accepted_by_prequential_ledger(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support)
        learner.add_query_objects(objects)
        ledger = PrequentialLedger(episode_id="primitive-expansion-ledger")
        decision = learner.predict(query[0])
        ledger.commit_prediction(
            prediction_id="prediction-1",
            observation_id=query[0]["observation_id"],
            model_version=decision["model_version"],
            candidate_set_hash=decision["candidate_set_hash"],
            decision_status=decision["decision_status"],
            prediction=decision["prediction"],
        )
        reveal = ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="prediction-1", target=labels[0]
        )
        revision = learner.revise(query[0], reveal["target"])
        event = ledger.append_revision(
            revision_id="revision-1",
            operation=revision["operation"],
            evidence_ids=[reveal["reveal_id"]],
            before_version_ids=[decision["model_version"]],
            after_version_ids=[revision["model_version"]],
            rationale_code=revision["status"],
        )
        self.assertEqual(event["operation"], "expand")


    def test_unknown_relation_does_not_delete_unrelated_base_candidates(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = E10AMechanismLearner(support)
        learner.add_query_objects(objects)
        initial = learner.candidate_count
        self.assertGreater(initial, 0)
        learner.revise(query[0], labels[0])
        self.assertEqual(learner.candidate_count, initial)


    def test_prequential_capability_across_eight_support_seeds(self):
        predicted = 0
        correct = 0
        abstained = 0
        for seed in range(3301, 3309):
            support, objects, query, labels = _novel_relation_episode(seed)
            learner = PrimitiveExpansionLearner(support)
            learner.add_query_objects(objects)
            for row, target in zip(query, labels):
                decision = learner.predict(row)
                if decision["decision_status"] == "PREDICT":
                    predicted += 1
                    correct += int(decision["prediction"] is target)
                else:
                    abstained += 1
                learner.revise(row, target)
        self.assertEqual(predicted, 24)
        self.assertEqual(correct, 24)
        self.assertEqual(abstained, 16)

    def test_duplicate_observation_reveal_is_rejected_without_mutation(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support)
        learner.add_query_objects(objects)
        learner.revise(query[0], labels[0])
        before = learner.candidate_hash
        with self.assertRaisesRegex(ValueError, "already been revised"):
            learner.revise(query[0], labels[0])
        self.assertEqual(learner.candidate_hash, before)

    def test_future_query_labels_are_not_part_of_learner_state(self):
        support, objects, query, labels = _novel_relation_episode()
        learner = PrimitiveExpansionLearner(support)
        learner.add_query_objects(objects)
        self.assertFalse(hasattr(learner, "query_truth"))
        self.assertFalse(hasattr(learner, "evaluator"))
        self.assertEqual(learner.predict(query[0])["decision_status"], "ABSTAIN_INCONSISTENT")


if __name__ == "__main__":
    unittest.main()
