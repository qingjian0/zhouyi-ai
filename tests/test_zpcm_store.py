import tempfile
import unittest
from pathlib import Path

from prototype.zpcm_store import (
    EventConflictError, MaterializationError, ZPCMError, ZPCMStore,
)


def event(event_id, event_type, payload, *, observed_at=10, recorded_at=11,
          source_refs=None):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": 1,
        "observed_at": observed_at,
        "recorded_at": recorded_at,
        "source_refs": source_refs or [],
        "payload": payload,
    }


def asserted(claim_id="c1", subject="alice", predicate="lives_in",
             object_value="Shanghai", valid_from=1, valid_until=None):
    return event("assert-" + claim_id, "CLAIM_ASSERTED", {
        "claim_id": claim_id,
        "subject": subject,
        "predicate": predicate,
        "object": object_value,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "epistemic_status": "OBSERVED",
        "evidence_refs": ["evidence://conversation/1"],
        "derivation_refs": [],
        "scope_conditions": [],
    }, source_refs=["conversation://1"])


class ZPCMStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "memory.sqlite3"
        self.store = ZPCMStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_append_is_idempotent_for_same_event(self):
        item = asserted()
        first = self.store.append_event(item)
        second = self.store.append_event(item)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(first.seq, second.seq)
        self.assertEqual(self.store.last_event_seq, 1)

    def test_reused_event_id_with_changed_payload_is_rejected(self):
        self.store.append_event(asserted())
        changed = asserted()
        changed["payload"]["object"] = "Beijing"
        with self.assertRaises(EventConflictError):
            self.store.append_event(changed)

    def test_append_and_materialize_are_separate(self):
        self.store.append_event(asserted())
        self.assertEqual(self.store.projection_seq, 0)
        self.assertEqual(self.store.query_claims(), ())
        report = self.store.materialize()
        self.assertEqual(report.applied, 1)
        self.assertEqual(self.store.projection_seq, 1)
        self.assertEqual(self.store.query_claims()[0].object_value, "Shanghai")

    def test_retraction_preserves_claim_history(self):
        self.store.append_event(asserted())
        self.store.append_event(event("retract-c1", "CLAIM_RETRACTED", {
            "claim_id": "c1", "reason": "user correction"
        }, observed_at=20, recorded_at=21))
        self.store.materialize()
        self.assertEqual(self.store.query_claims(), ())
        history = self.store.query_claims(include_retracted=True)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].retracted_seq, 2)

    def test_valid_time_is_distinct_from_recorded_time(self):
        self.store.append_event(asserted(valid_from=100, valid_until=200))
        self.store.materialize()
        self.assertEqual(self.store.query_claims(at_time=99), ())
        self.assertEqual(len(self.store.query_claims(at_time=150)), 1)
        self.assertEqual(self.store.query_claims(at_time=201), ())

    def test_batch_materialization_is_atomic_on_poison_event(self):
        self.store.append_event(asserted())
        self.store.append_event(event("bad-retract", "CLAIM_RETRACTED", {
            "claim_id": "missing", "reason": "invalid"
        }))
        with self.assertRaises(MaterializationError):
            self.store.materialize()
        self.assertEqual(self.store.projection_seq, 0)
        self.assertEqual(self.store.query_claims(), ())

    def test_materialization_resumes_after_restart(self):
        self.store.append_event(asserted())
        self.store.close()
        self.store = ZPCMStore(self.db_path)
        report = self.store.materialize()
        self.assertEqual(report.applied, 1)
        self.assertEqual(len(self.store.query_claims()), 1)

    def test_bounded_materialization_advances_cursor(self):
        for i in range(3):
            self.store.append_event(event(f"note-{i}", "NOTE", {"i": i}))
        first = self.store.materialize(limit=2)
        self.assertEqual(first.applied, 2)
        self.assertTrue(first.remaining)
        second = self.store.materialize(limit=2)
        self.assertEqual(second.applied, 1)
        self.assertFalse(second.remaining)

    def test_rebuild_is_deterministic(self):
        self.store.append_event(asserted())
        self.store.append_event(event("retract-c1", "CLAIM_RETRACTED", {
            "claim_id": "c1", "reason": "correction"
        }))
        self.store.materialize()
        before = self.store.query_claims(include_retracted=True)
        self.store.rebuild_projection()
        after = self.store.query_claims(include_retracted=True)
        self.assertEqual(before, after)

    def test_integrity_reports_ledger_and_projection_watermarks(self):
        self.store.append_event(asserted())
        result = self.store.verify_integrity()
        self.assertEqual(result["sqlite_integrity"], "ok")
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["projection_lag"], 1)
        self.store.materialize()
        result = self.store.verify_integrity()
        self.assertEqual(result["projection_lag"], 0)

    def test_invalid_event_fields_are_rejected(self):
        with self.assertRaises(ZPCMError):
            self.store.append_event({"event_id": "x"})
        with self.assertRaises(ZPCMError):
            self.store.append_event(event("x", "NOTE", {}, observed_at=-1))


if __name__ == "__main__":
    unittest.main()
