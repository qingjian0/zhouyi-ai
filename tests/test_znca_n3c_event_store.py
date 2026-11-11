import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from prototype.znca_n3c_event_store import (
    EventStoreError, IdempotencyConflict, IntegrityError,
    SQLiteEventStore, VersionConflict,
)


class DurableEventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "events.sqlite3"
        self.store = SQLiteEventStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def commit(self, transaction_id="tx-1", expected_version=0, key="relation.a"):
        return self.store.commit_hypothesis(
            expected_version=expected_version, transaction_id=transaction_id,
            hypothesis_id="hyp-1", base_version=expected_version,
            status="SUPPORTED", evidence_refs=("evidence-1",),
            state_delta={key: "active"},
        )

    def test_append_advances_version_and_hash_chain(self):
        event = self.commit()
        self.assertEqual(event.sequence, 1)
        self.assertEqual(self.store.version, 1)
        self.assertEqual(len(self.store.verify()), 1)

    def test_replay_rebuilds_state(self):
        self.commit()
        self.store.commit_hypothesis(
            expected_version=1, transaction_id="tx-2", hypothesis_id="hyp-2",
            base_version=1, status="SUPPORTED", evidence_refs=("evidence-2",),
            state_delta={"relation.b": "stable"},
        )
        recovered = self.store.recover({"seed": "known"})
        self.assertEqual(recovered.version, 2)
        self.assertEqual(recovered.as_dict(), {
            "seed": "known", "relation.a": "active", "relation.b": "stable",
        })

    def test_reopen_recovers_durable_state(self):
        self.commit()
        self.store.close()
        self.store = SQLiteEventStore(self.path)
        self.assertEqual(self.store.recover().as_dict(), {"relation.a": "active"})

    def test_expected_version_is_compare_and_swap(self):
        self.commit()
        with self.assertRaises(VersionConflict):
            self.commit("tx-stale", 0, "relation.b")
        self.assertEqual(self.store.version, 1)
        self.assertEqual(len(self.store.events()), 1)

    def test_idempotent_retry_returns_original_event(self):
        first = self.commit()
        self.assertEqual(self.commit(), first)
        self.assertEqual(self.store.version, 1)

    def test_transaction_id_cannot_be_reused_for_different_payload(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.commit_hypothesis(
                expected_version=0, transaction_id="tx-1", hypothesis_id="other",
                base_version=0, status="SUPPORTED", evidence_refs=("evidence-1",),
                state_delta={"relation.a": "other"},
            )

    def test_non_supported_hypothesis_is_rejected(self):
        with self.assertRaises(EventStoreError):
            self.store.commit_hypothesis(
                expected_version=0, transaction_id="tx-1", hypothesis_id="hyp-1",
                base_version=0, status="CONTESTED", evidence_refs=("e1",),
                state_delta={"a": "b"},
            )

    def test_missing_evidence_and_empty_delta_are_rejected(self):
        with self.assertRaises(EventStoreError):
            self.store.commit_hypothesis(
                expected_version=0, transaction_id="tx-1", hypothesis_id="hyp-1",
                base_version=0, status="SUPPORTED", evidence_refs=(),
                state_delta={"a": "b"},
            )
        with self.assertRaises(EventStoreError):
            self.store.commit_hypothesis(
                expected_version=0, transaction_id="tx-1", hypothesis_id="hyp-1",
                base_version=0, status="SUPPORTED", evidence_refs=("e1",),
                state_delta={},
            )

    def test_base_version_must_match_expected_version(self):
        with self.assertRaises(VersionConflict):
            self.store.commit_hypothesis(
                expected_version=0, transaction_id="tx-1", hypothesis_id="hyp-1",
                base_version=1, status="SUPPORTED", evidence_refs=("e1",),
                state_delta={"a": "b"},
            )

    def test_hash_chain_detects_payload_tampering(self):
        self.commit()
        connection = sqlite3.connect(self.path)
        connection.execute(
            "UPDATE znca_events SET payload_json = ? WHERE sequence = 1",
            ('{"state_delta":{"relation.a":"tampered"}}',),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(IntegrityError):
            self.store.verify()

    def test_two_writers_same_version_only_one_wins(self):
        self.store.close()
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def writer(index):
            local = SQLiteEventStore(self.path)
            barrier.wait()
            try:
                event = local.commit_hypothesis(
                    expected_version=0, transaction_id=f"race-{index}",
                    hypothesis_id=f"hyp-{index}", base_version=0,
                    status="SUPPORTED", evidence_refs=(f"evidence-{index}",),
                    state_delta={f"relation.{index}": "active"},
                )
                outcome = ("committed", event.sequence)
            except VersionConflict:
                outcome = ("conflict", None)
            finally:
                local.close()
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.store = SQLiteEventStore(self.path)
        self.assertEqual(sum(x[0] == "committed" for x in outcomes), 1)
        self.assertEqual(sum(x[0] == "conflict" for x in outcomes), 1)
        self.assertEqual(self.store.version, 1)
        self.assertEqual(len(self.store.verify()), 1)

    def test_event_paging_is_ordered(self):
        self.commit()
        self.store.commit_hypothesis(
            expected_version=1, transaction_id="tx-2", hypothesis_id="hyp-2",
            base_version=1, status="SUPPORTED", evidence_refs=("e2",),
            state_delta={"b": "2"},
        )
        self.assertEqual([e.sequence for e in self.store.events(1)], [2])


if __name__ == "__main__":
    unittest.main()
