import copy
import unittest

from prototype.e10a_prequential_ledger import PrequentialLedger, canonical_hash


class E10APrequentialLedgerTests(unittest.TestCase):
    def _ledger(self):
        return PrequentialLedger(episode_id="ep-test")

    def _commit(self, ledger, **overrides):
        values = {
            "prediction_id": "pred-1",
            "observation_id": "query-1",
            "model_version": "model-v1",
            "candidate_set_hash": "candidates-hash",
            "decision_status": "PREDICT",
            "prediction": True,
            "confidence": 0.8,
            "compute_cost": {"steps": 12},
        }
        values.update(overrides)
        return ledger.commit_prediction(**values)

    def test_prediction_commit_precedes_reveal(self):
        ledger = self._ledger()
        commit = self._commit(ledger)
        reveal = ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="pred-1", target=True
        )
        self.assertLess(commit["step"], reveal["step"])
        self.assertEqual(reveal["prediction_event_id"], commit["event_id"])

    def test_reveal_without_commit_is_rejected(self):
        ledger = self._ledger()
        with self.assertRaisesRegex(ValueError, "prior committed prediction"):
            ledger.reveal_evidence(
                reveal_id="reveal-1", prediction_id="missing", target=False
            )

    def test_prediction_commit_is_immutable_and_unique(self):
        ledger = self._ledger()
        first = self._commit(ledger)
        with self.assertRaisesRegex(ValueError, "already committed"):
            self._commit(ledger, prediction=True)
        self.assertEqual(ledger.snapshot()["events"][0], first)

    def test_reveal_is_once_per_prediction_and_observation(self):
        ledger = self._ledger()
        self._commit(ledger)
        ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="pred-1", target=True
        )
        with self.assertRaises(ValueError):
            ledger.reveal_evidence(
                reveal_id="reveal-2", prediction_id="pred-1", target=False
            )
        with self.assertRaises(ValueError):
            ledger.commit_prediction(
                prediction_id="pred-2", observation_id="query-1",
                model_version="model-v1", candidate_set_hash="h",
                decision_status="PREDICT", prediction=False,
            )

    def test_revision_cannot_cite_unrevealed_or_unknown_evidence(self):
        ledger = self._ledger()
        self._commit(ledger)
        with self.assertRaisesRegex(ValueError, "not been revealed"):
            ledger.append_revision(
                revision_id="rev-1", operation="modify",
                evidence_ids=["reveal-1"], before_version_ids=["v1"],
                after_version_ids=["v2"], rationale_code="counterexample",
            )
        ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="pred-1", target=False
        )
        revision = ledger.append_revision(
            revision_id="rev-1", operation="modify",
            evidence_ids=["reveal-1"], before_version_ids=["v1"],
            after_version_ids=["v2"], rationale_code="counterexample",
            actual_compute={"nodes_expanded": 4},
        )
        self.assertEqual(revision["trigger_evidence_ids"], ["reveal-1"])

    def test_abstention_is_a_valid_committed_prediction(self):
        ledger = self._ledger()
        event = self._commit(
            ledger, decision_status="ABSTAIN_AMBIGUOUS", prediction=None,
            confidence=None,
        )
        self.assertEqual(event["decision_status"], "ABSTAIN_AMBIGUOUS")
        ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="pred-1", target="unknown"
        )

    def test_snapshots_are_detached_and_append_only(self):
        ledger = self._ledger()
        self._commit(ledger)
        before = ledger.snapshot()
        mutated = copy.deepcopy(before)
        mutated["events"][0]["prediction"] = "tampered"
        self.assertNotEqual(canonical_hash(mutated["events"]), before["ledger_hash"])
        self.assertEqual(ledger.snapshot()["ledger_hash"], before["ledger_hash"])
        ledger.reveal_evidence(
            reveal_id="reveal-1", prediction_id="pred-1", target=True
        )
        after = ledger.snapshot()
        self.assertEqual(after["events"][0], before["events"][0])
        self.assertEqual(after["event_count"], 2)

    def test_invalid_prediction_and_cost_fail_closed(self):
        ledger = self._ledger()
        for confidence in (True, -0.1, 1.1, "0.5"):
            with self.assertRaises(ValueError):
                self._commit(
                    ledger, prediction_id=f"p-{confidence}",
                    observation_id=f"o-{confidence}", confidence=confidence,
                )
        with self.assertRaisesRegex(ValueError, "requires a prediction"):
            self._commit(
                ledger, prediction_id="p-none", observation_id="o-none",
                prediction=None,
            )
        with self.assertRaisesRegex(ValueError, "must be a dictionary"):
            self._commit(
                ledger, prediction_id="p-cost", observation_id="o-cost",
                compute_cost=["not", "dict"],
            )



    def test_ood_decision_statuses_are_valid_ledger_commits(self):
        for index, status in enumerate((
            "ABSTAIN_OOD_SCHEMA",
            "ABSTAIN_OOD_VALUE",
            "ABSTAIN_OOD_RELATION",
        )):
            ledger = PrequentialLedger(episode_id=f"ood-ledger-{index}")
            event = ledger.commit_prediction(
                prediction_id="p1",
                observation_id="o1",
                model_version="v1",
                candidate_set_hash="candidates",
                decision_status=status,
                prediction=None,
            )
            self.assertEqual(event["decision_status"], status)

if __name__ == "__main__":
    unittest.main()
