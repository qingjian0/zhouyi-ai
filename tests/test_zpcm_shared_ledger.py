import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import SQLiteEvidenceStore, ProtocolError, MissingReference
from prototype.zpcm_projection import (
    MEMORY_EPISODE, ZPCMClaimProjection, append_claim, retract_claim,
)


def seed_reveal(store):
    store.append_event(
        episode_id="task-1", event_id="obs-1", event_type="observation",
        payload={"observation_id": "obs-1"}, idempotency_key="obs-1",
    )
    store.commit_prediction(
        episode_id="task-1", event_id="pred-1", idempotency_key="pred-1",
        actor_role="learner", payload={
            "prediction_id": "pred-1", "observation_id": "obs-1",
            "model_version": "m1", "learner_track": "srok0",
            "decision_status": "PREDICT",
        },
    )
    store.reveal_evidence(
        episode_id="task-1", event_id="reveal-1", idempotency_key="reveal-1",
        actor_role="evaluator", payload={
            "prediction_id": "pred-1", "learner_track": "srok0",
            "target_or_feedback": ["a", "b", "c"],
        },
    )
    return "task-1::reveal-1"


class ZPCMSharedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "shared.sqlite3"
        self.store = SQLiteEvidenceStore(self.path)
        self.projection = ZPCMClaimProjection(self.store)
        self.evidence_ref = seed_reveal(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_claims_project_from_the_same_event_store(self):
        receipt = append_claim(
            self.store, event_id="claim-event-1", claim_id="claim-1",
            subject="entity:alice", predicate="prefers", object_value="tea",
            valid_from=100, evidence_refs=(self.evidence_ref,),
            epistemic_status="SUPPORTED", scope_conditions=("context:work",),
        )
        report = self.projection.materialize()
        self.assertEqual(report.applied_events, 1)
        claims = self.projection.query_claims(subject="entity:alice")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].object_value, "tea")
        self.assertEqual(claims[0].evidence_refs, (self.evidence_ref,))
        self.assertEqual(claims[0].assertion_event_id, receipt.event_id)
        event_types = [e["event_type"] for e in self.store.replay_episode(MEMORY_EPISODE)]
        self.assertEqual(event_types, ["memory_claim_asserted"])
        event_tables = self.store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchall()
        self.assertEqual(len(event_tables), 1)

    def test_invalid_or_non_reveal_evidence_ref_is_rejected(self):
        with self.assertRaises(MissingReference):
            append_claim(
                self.store, event_id="bad-claim-1", claim_id="bad-1",
                subject="s", predicate="p", object_value="o", valid_from=1,
                evidence_refs=("missing::reveal",),
            )
        with self.assertRaises(MissingReference):
            append_claim(
                self.store, event_id="bad-claim-2", claim_id="bad-2",
                subject="s", predicate="p", object_value="o", valid_from=1,
                evidence_refs=("task-1::obs-1",),
            )

    def test_retraction_is_append_only_and_projection_is_rebuildable(self):
        append_claim(
            self.store, event_id="claim-event-2", claim_id="claim-2",
            subject="entity:bob", predicate="located_in", object_value="Shanghai",
            valid_from=100, evidence_refs=(self.evidence_ref,),
        )
        self.projection.materialize()
        retract_claim(self.store, event_id="retract-2", claim_id="claim-2", reason="newer evidence")
        self.projection.materialize()
        self.assertEqual(self.projection.query_claims(subject="entity:bob"), ())
        history = self.projection.query_claims(subject="entity:bob", include_retracted=True)
        self.assertEqual(history[0].retraction_reason, "newer evidence")
        rebuilt = self.projection.rebuild_projection()
        self.assertEqual(rebuilt.end_sequence, 2)
        self.assertEqual(self.projection.query_claims(subject="entity:bob"), ())

    def test_incremental_materialization_resumes_after_limit(self):
        append_claim(self.store, event_id="c1", claim_id="1", subject="s1",
                     predicate="p", object_value=1, valid_from=1,
                     evidence_refs=(self.evidence_ref,))
        append_claim(self.store, event_id="c2", claim_id="2", subject="s2",
                     predicate="p", object_value=2, valid_from=2,
                     evidence_refs=(self.evidence_ref,))
        first = self.projection.materialize(limit=1)
        second = self.projection.materialize(limit=1)
        self.assertTrue(first.remaining)
        self.assertFalse(second.remaining)
        self.assertEqual(self.projection.projection_sequence, 2)
        self.assertEqual(len(self.projection.query_claims()), 2)

    def test_duplicate_idempotent_assertion_does_not_duplicate_projection(self):
        kwargs = dict(
            event_id="same-event", claim_id="same-claim", subject="s",
            predicate="p", object_value="v", valid_from=1,
            evidence_refs=(self.evidence_ref,),
        )
        first = append_claim(self.store, **kwargs)
        second = append_claim(self.store, **kwargs)
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.projection.materialize()
        self.assertEqual(len(self.projection.query_claims()), 1)

    def test_claim_id_cannot_be_reasserted_or_retracted_twice(self):
        append_claim(self.store, event_id="assert-once", claim_id="once",
                     subject="s", predicate="p", object_value="v", valid_from=1,
                     evidence_refs=(self.evidence_ref,))
        with self.assertRaises(ProtocolError):
            append_claim(self.store, event_id="assert-twice", claim_id="once",
                         subject="s", predicate="p", object_value="v2", valid_from=2,
                         evidence_refs=(self.evidence_ref,))
        retract_claim(self.store, event_id="retract-once", claim_id="once", reason="withdrawn")
        with self.assertRaises(MissingReference):
            retract_claim(self.store, event_id="retract-twice", claim_id="once", reason="again")

    def test_integrity_check_covers_one_canonical_event_ledger(self):
        append_claim(self.store, event_id="integrity-claim", claim_id="integrity",
                     subject="s", predicate="p", object_value="v", valid_from=1,
                     evidence_refs=(self.evidence_ref,))
        self.projection.materialize()
        report = self.store.verify_integrity()
        self.assertEqual(report["bad_event_hashes"], ())
        self.assertEqual(report["event_count"], 4)


if __name__ == "__main__":
    unittest.main()
