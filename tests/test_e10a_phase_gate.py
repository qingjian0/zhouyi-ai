import unittest

from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_phase_gate import PhaseGatedEvaluator
from prototype.e10a_prequential_ledger import PrequentialLedger


class E10APhaseGateTests(unittest.TestCase):
    def _setup(self, seed=1001):
        _, query, truth = build_object_disjoint_task(seed, instances_per_template=2)
        ledger = PrequentialLedger(episode_id=f"episode-{seed}")
        gate = PhaseGatedEvaluator(
            query_payload=query, evaluator_truth=truth, ledger=ledger
        )
        return gate, ledger

    def test_reveal_requires_open_query_and_prior_matching_commit(self):
        gate, ledger = self._setup()
        with self.assertRaisesRegex(ValueError, "no open Query"):
            gate.reveal_current(prediction_id="p0", reveal_id="r0")
        row = gate.open_next_query()
        self.assertNotIn("outcome", row["observation"])
        with self.assertRaisesRegex(ValueError, "no committed prediction"):
            gate.reveal_current(prediction_id="p0", reveal_id="r0")
        ledger.commit_prediction(
            prediction_id="p0", observation_id=row["observation"]["observation_id"],
            model_version="m0", candidate_set_hash="c0",
            decision_status="PREDICT", prediction=True,
        )
        reveal = gate.reveal_current(prediction_id="p0", reveal_id="r0")
        self.assertEqual(reveal["event_type"], "EvidenceReveal")
        self.assertIsInstance(reveal["target"], bool)

    def test_cannot_advance_before_current_reveal(self):
        gate, ledger = self._setup(1002)
        first = gate.open_next_query()
        with self.assertRaisesRegex(ValueError, "before advancing"):
            gate.open_next_query()
        ledger.commit_prediction(
            prediction_id="p1", observation_id=first["observation"]["observation_id"],
            model_version="m0", candidate_set_hash="c0",
            decision_status="ABSTAIN_AMBIGUOUS",
        )
        gate.reveal_current(prediction_id="p1", reveal_id="r1")
        second = gate.open_next_query()
        self.assertNotEqual(
            first["observation"]["observation_id"],
            second["observation"]["observation_id"],
        )

    def test_wrong_prediction_id_cannot_unlock_truth(self):
        gate, ledger = self._setup(1003)
        row = gate.open_next_query()
        ledger.commit_prediction(
            prediction_id="correct-pred", observation_id=row["observation"]["observation_id"],
            model_version="m0", candidate_set_hash="c0",
            decision_status="PREDICT", prediction=False,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            gate.reveal_current(prediction_id="wrong-pred", reveal_id="r")
        self.assertFalse(gate.is_complete)

    def test_object_table_is_sent_once_and_query_labels_never_sent(self):
        gate, ledger = self._setup(1004)
        first = gate.open_next_query()
        self.assertTrue(first["objects"])
        self.assertNotIn("outcome", first["observation"])
        ledger.commit_prediction(
            prediction_id="p-first", observation_id=first["observation"]["observation_id"],
            model_version="m0", candidate_set_hash="c0",
            decision_status="ABSTAIN_BUDGET",
        )
        gate.reveal_current(prediction_id="p-first", reveal_id="r-first")
        second = gate.open_next_query()
        self.assertEqual(second["objects"], [])
        self.assertNotIn("outcome", second["observation"])

    def test_complete_only_after_every_query_is_revealed(self):
        gate, ledger = self._setup(1005)
        self.assertFalse(gate.is_complete)
        index = 0
        while True:
            item = gate.open_next_query()
            if item is None:
                break
            prediction_id = f"p-{index}"
            ledger.commit_prediction(
                prediction_id=prediction_id,
                observation_id=item["observation"]["observation_id"],
                model_version="m0", candidate_set_hash="c0",
                decision_status="ABSTAIN_AMBIGUOUS",
            )
            gate.reveal_current(
                prediction_id=prediction_id, reveal_id=f"r-{index}"
            )
            index += 1
        self.assertGreater(index, 0)
        self.assertTrue(gate.is_complete)
        self.assertIsNone(gate.open_next_query())

    def test_query_truth_must_cover_exact_query_ids(self):
        _, query, truth = build_object_disjoint_task(1006, instances_per_template=2)
        broken = dict(truth)
        broken["query_truth"] = truth["query_truth"][:-1]
        with self.assertRaisesRegex(ValueError, "IDs must match"):
            PhaseGatedEvaluator(
                query_payload=query, evaluator_truth=broken,
                ledger=PrequentialLedger(episode_id="broken"),
            )


if __name__ == "__main__":
    unittest.main()
