import unittest
from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_mechanism_learner import E10AMechanismLearner
from prototype.e10a_prequential_ledger import PrequentialLedger
from prototype.e10a_phase_gate import PhaseGatedEvaluator

class MechanismLearnerTests(unittest.TestCase):
    def test_support_only_candidate_induction(self):
        support, query, truth = build_object_disjoint_task(1101)
        learner = E10AMechanismLearner(support)
        self.assertGreater(learner.candidate_count, 0)
        self.assertNotIn("query_truth", learner.__dict__)
        self.assertNotIn("mechanisms", learner.__dict__)
        learner.add_query_objects(query["objects"])
        truth_by_id = {x["observation_id"]: x["valid"] for x in truth["query_truth"]}
        decided = [(learner.predict(row), truth_by_id[row["observation_id"]]) for row in query["observations"]]
        covered = [(p, y) for p, y in decided if p["decision_status"] == "PREDICT"]
        self.assertGreater(len(covered), 0)
        self.assertTrue(all(p["prediction"] == y for p, y in covered))

    def test_phase_gate_ledger_and_incremental_revision(self):
        support, query, truth = build_object_disjoint_task(1102)
        learner = E10AMechanismLearner(support)
        ledger = PrequentialLedger(episode_id="learner-test")
        gate = PhaseGatedEvaluator(query_payload=query, evaluator_truth=truth, ledger=ledger)
        while True:
            packet = gate.open_next_query()
            if packet is None: break
            if packet["objects"]: learner.add_query_objects(packet["objects"])
            row = packet["observation"]
            decision = learner.predict(row)
            pid = "p-" + row["observation_id"]
            ledger.commit_prediction(prediction_id=pid, observation_id=row["observation_id"], model_version=decision["model_version"], candidate_set_hash=decision["candidate_set_hash"], decision_status=decision["decision_status"], prediction=decision["prediction"], compute_cost={"candidate_count": decision["candidate_count"]})
            reveal = gate.reveal_current(prediction_id=pid, reveal_id="r-" + row["observation_id"])
            revision = learner.revise(row, reveal["target"])
            ledger.append_revision(revision_id="v-" + row["observation_id"], operation=revision["operation"], evidence_ids=[reveal["reveal_id"]], before_version_ids=[decision["model_version"]], after_version_ids=[revision["model_version"]], rationale_code=revision["status"])
        self.assertTrue(gate.is_complete)
        self.assertGreater(ledger.snapshot()["event_count"], 0)

    def test_unknown_relation_abstains(self):
        support, _, _ = build_object_disjoint_task(1103)
        learner = E10AMechanismLearner(support)
        row = dict(support["observations"][0], relation_symbol="unknown-relation")
        self.assertEqual(learner.predict(row)["decision_status"], "ABSTAIN_INCONSISTENT")

    def test_evaluator_fields_rejected(self):
        support, _, _ = build_object_disjoint_task(1104)
        support["observations"][0]["valid"] = True
        with self.assertRaises(ValueError): E10AMechanismLearner(support)

if __name__ == "__main__": unittest.main()