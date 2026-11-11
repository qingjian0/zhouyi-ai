"""Tests for the persistent N3-D counterfactual branch ledger."""
import tempfile
import unittest
from pathlib import Path

from prototype.znca_n3c_event_store import SQLiteEventStore, EventStoreError
from prototype.znca_n3d_counterfactual_branches import (
    BranchError, CounterfactualBranchLedger, StaleBranch,
)


class CounterfactualBranchLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "events.sqlite"
        self.store = SQLiteEventStore(self.path)
        self.ledger = CounterfactualBranchLedger(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def seed(self):
        self.store.commit_hypothesis(
            expected_version=0, transaction_id="seed-1", hypothesis_id="h0",
            base_version=0, status="SUPPORTED", evidence_refs=("ev:seed",),
            state_delta={"weather": "rain", "temperature": "cold"},
        )

    def test_branch_stores_only_sparse_delta_and_promotes(self):
        self.seed()
        branch = self.ledger.create_branch(
            branch_id="b1", hypothesis_id="h1", evidence_refs=("ev:1",),
            transaction_id="branch-create",
        )
        self.assertEqual(branch.base_revision, 1)
        self.assertEqual(branch.delta, ())
        self.ledger.record_delta(
            branch_id="b1", key="weather", value="snow",
            transaction_id="branch-delta",
        )
        promoted = self.ledger.promote(branch_id="b1", transaction_id="branch-promote")
        self.assertEqual(promoted.status, "PROMOTED")
        self.assertEqual(self.ledger.projection().as_dict(),
                         {"temperature": "cold", "weather": "snow"})
        self.assertEqual(self.store.recover().as_dict(),
                         {"temperature": "cold", "weather": "snow"})

    def test_stale_branch_cannot_promote(self):
        self.seed()
        self.ledger.create_branch(
            branch_id="stale", hypothesis_id="h-stale", evidence_refs=("ev:s",),
            transaction_id="stale-create",
        )
        self.ledger.record_delta(
            branch_id="stale", key="weather", value="sun",
            transaction_id="stale-delta",
        )
        self.store.commit_hypothesis(
            expected_version=self.store.version, transaction_id="canonical-next",
            hypothesis_id="h2", base_version=self.store.version,
            status="SUPPORTED", evidence_refs=("ev:2",),
            state_delta={"temperature": "warm"},
        )
        with self.assertRaises(StaleBranch):
            self.ledger.promote(branch_id="stale", transaction_id="stale-promote")

    def test_compensation_restores_prior_value_without_deleting_history(self):
        first = self.store.commit_hypothesis(
            expected_version=0, transaction_id="first", hypothesis_id="h1",
            base_version=0, status="SUPPORTED", evidence_refs=("ev:1",),
            state_delta={"weather": "rain", "wind": "strong"},
        )
        self.store.commit_hypothesis(
            expected_version=1, transaction_id="second", hypothesis_id="h2",
            base_version=1, status="SUPPORTED", evidence_refs=("ev:2",),
            state_delta={"weather": "snow"},
        )
        # The target's key was subsequently changed, so compensation must fail closed.
        with self.assertRaises(BranchError):
            self.ledger.compensate(
                target_sequence=first.sequence, reason="bad observation",
                evidence_refs=("ev:correction",), transaction_id="comp-fail",
            )
        self.assertEqual(len(self.store.verify()), 2)

    def test_compensation_restores_and_keeps_original_event(self):
        first = self.store.commit_hypothesis(
            expected_version=0, transaction_id="first", hypothesis_id="h1",
            base_version=0, status="SUPPORTED", evidence_refs=("ev:1",),
            state_delta={"weather": "rain"},
        )
        self.ledger.compensate(
            target_sequence=first.sequence, reason="sensor corrected",
            evidence_refs=("ev:correction",), transaction_id="compensate",
        )
        self.assertEqual(self.ledger.projection().as_dict(), {})
        self.assertEqual(len(self.store.verify()), 2)
        self.assertEqual(self.store.verify()[0].event_type, "HypothesisCommitted")
        self.assertEqual(self.store.recover().as_dict(), {})

    def test_rejected_branch_is_retained_but_never_promoted(self):
        branch = self.ledger.create_branch(
            branch_id="reject-me", hypothesis_id="h-r", evidence_refs=("ev:r",),
            transaction_id="reject-create",
        )
        rejected = self.ledger.reject(
            branch_id=branch.branch_id, reason="counterexample",
            transaction_id="reject-event",
        )
        self.assertEqual(rejected.status, "REJECTED")
        with self.assertRaises(BranchError):
            self.ledger.promote(branch_id="reject-me", transaction_id="reject-promote")
        self.assertEqual(self.ledger.get_branch("reject-me").status, "REJECTED")

    def test_reopen_reconstructs_branches_and_canonical_projection(self):
        self.seed()
        self.ledger.create_branch(
            branch_id="persist", hypothesis_id="h-p", evidence_refs=("ev:p",),
            transaction_id="persist-create",
        )
        self.ledger.record_delta(
            branch_id="persist", key="weather", value="fog",
            transaction_id="persist-delta",
        )
        self.store.close()
        self.store = SQLiteEventStore(self.path)
        self.ledger = CounterfactualBranchLedger(self.store)
        self.assertEqual(self.ledger.get_branch("persist").delta, (("weather", "fog"),))
        self.assertEqual(self.store.recover().as_dict(),
                         {"temperature": "cold", "weather": "rain"})

    def test_compensation_requires_evidence_and_reason(self):
        event = self.store.commit_hypothesis(
            expected_version=0, transaction_id="commit", hypothesis_id="h",
            base_version=0, status="SUPPORTED", evidence_refs=("ev",),
            state_delta={"x": "1"},
        )
        with self.assertRaises(BranchError):
            self.ledger.compensate(
                target_sequence=event.sequence, reason="fix", evidence_refs=(),
                transaction_id="no-evidence",
            )

    def test_branch_delta_does_not_mutate_canonical_state(self):
        self.seed()
        self.ledger.create_branch(
            branch_id="isolated", hypothesis_id="h-i", evidence_refs=("ev:i",),
            transaction_id="isolated-create",
        )
        self.ledger.record_delta(
            branch_id="isolated", key="weather", value="hail",
            transaction_id="isolated-delta",
        )
        self.assertEqual(self.ledger.projection().as_dict(),
                         {"temperature": "cold", "weather": "rain"})


if __name__ == "__main__":
    unittest.main()
