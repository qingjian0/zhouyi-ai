import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from prototype.e12a6_lifecycle_contract import Action,ActionType,Candidate,CandidateState,Evidence,SplitRole
from prototype.e12a6_zpcm_persistence import (EVENT_SCHEMA, LifecyclePersistenceError, PersistentLifecycleLedger, _candidate_to_dict, _evidence_to_dict, _safe_evidence)
from prototype.e09_verification_receipt import VerifiedE09VerificationReceipt
from prototype.zpcm_memory import ZPCMError,ZPCMMemory

def candidate():
    return Candidate(candidate_id="rel:greater-than",version=1,canonical_expression="x > y",
      proposer_family="relational",supporting_families=("relational","residual"),
      input_types=("number","number"),operator="GT")
def evidence():
    return Evidence(evidence_id="train-1",episode_id="ep-1",world_family="finite-rule-world",
      split_role=SplitRole.TRAIN,observation_id="obs-1",outcome="true",model_version="model-0",
      prediction_commit_step=1,label_visibility_step=2)

def authorized_candidate():
    definition = {
        "schema": "csg-gcr-typed-candidate-v1",
        "parent_state_ref": "parent-1",
        "branch_ids": ["left", "right"],
        "branch_merge": {
            "authorization_ref": "grant-1",
            "authorization_evidence_refs": ["train-1"],
        },
    }
    return replace(
        candidate(),
        canonical_expression=json.dumps(definition, sort_keys=True, separators=(",", ":")),
        parent_refs=("parent-1",),
        evidence_ids=("train-1",),
    )


def verified_receipt(evidence_item=None, *, receipt_id="receipt-1", nonce="nonce-1"):
    item = evidence_item or evidence()
    item = replace(item, outcome=f"opaque-e09-evidence-ref:{item.evidence_id}",
                   provenance="opaque-e09-event-digest:" + "b" * 64)
    now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
    return VerifiedE09VerificationReceipt(
        receipt_id=receipt_id,
        nonce=nonce,
        episode_id="ep-1",
        authorization_ref="grant-1",
        scope="project-a",
        parent_state_ref="parent-1",
        branch_ids=("left", "right"),
        authorization_evidence_refs=("train-1",),
        evidence_refs=("train-1",),
        issuer_id="issuer-A",
        authorization_event_digest="a" * 64,
        verifier_id="verifier-A",
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=1),
        evidence=(item,),
    )


def writer_identity():
    return {
        "workload_id": "spiffe://zhouyi/test-writer",
        "identity_provider": "test-spiffe",
        "authentication_method": "mTLS",
        "credential_fingerprint": "c" * 64,
    }


def propose():
    return Action(action_id="propose-1",action_type=ActionType.PROPOSE,candidate_id="rel:greater-than",
      candidate_version=1,from_state=CandidateState.OBSERVED,to_state=CandidateState.PROPOSED)

class PersistentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/"zpcm.db"
        self.memory=ZPCMMemory(self.path); self.store=PersistentLifecycleLedger(self.memory,scope="project-a")
    def tearDown(self):
        self.memory.close(); self.tmp.cleanup()
    def test_registration_and_action_survive_reopen(self):
        self.store.register_candidate(candidate()); self.store.register_evidence(evidence()); self.store.apply(propose())
        before=self.store.snapshot()
        self.assertNotIn("true", str(self.memory.replay_lifecycle_events(scope="project-a")))
        self.assertIn("opaque-evidence-ref:train-1", str(before))
        self.memory.close(); self.memory=ZPCMMemory(self.path)
        self.store=PersistentLifecycleLedger(self.memory,scope="project-a")
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(self.store.ledger.candidates[("rel:greater-than",1)].state,CandidateState.PROPOSED)
    def test_same_action_is_idempotent_but_content_reuse_is_rejected(self):
        self.store.register_candidate(candidate()); first=self.store.apply(propose()); second=self.store.apply(propose())
        self.assertTrue(second.replayed); self.assertEqual(first.sequence,second.sequence)
        changed=Action(action_id="propose-1",action_type=ActionType.PROPOSE,candidate_id="rel:greater-than",
          candidate_version=1,from_state=CandidateState.OBSERVED,to_state=CandidateState.PROPOSED,note="different")
        with self.assertRaises(LifecyclePersistenceError): self.store.apply(changed)
    def test_invalid_transition_does_not_append_or_mutate(self):
        self.store.register_candidate(candidate()); before=self.store.snapshot()
        bad=Action(action_id="bad",action_type=ActionType.GATE_VALIDATE,candidate_id="rel:greater-than",
          candidate_version=1,from_state=CandidateState.OBSERVED,to_state=CandidateState.GATE_VALIDATED)
        with self.assertRaises(ValueError): self.store.apply(bad)
        self.assertEqual(self.store.snapshot(),before)
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope="project-a")),1)
    def test_append_failure_does_not_mutate_in_memory_ledger(self):
        self.store.register_candidate(candidate()); before=self.store.snapshot(); original=self.memory.append_lifecycle_event
        self.memory.append_lifecycle_event=lambda **kwargs: (_ for _ in ()).throw(ZPCMError("disk failure"))
        with self.assertRaises(ZPCMError): self.store.apply(propose())
        self.memory.append_lifecycle_event=original; self.assertEqual(self.store.snapshot(),before)
    def test_crash_after_durable_append_recovers_by_replay(self):
        self.store.register_candidate(candidate()); original=self.memory.append_lifecycle_event
        def commit_then_crash(**kwargs):
            original(**kwargs); raise RuntimeError("simulated crash after commit")
        self.memory.append_lifecycle_event=commit_then_crash
        with self.assertRaises(RuntimeError): self.store.apply(propose())
        self.memory.append_lifecycle_event=original; self.memory.close(); self.memory=ZPCMMemory(self.path)
        restored=PersistentLifecycleLedger(self.memory,scope="project-a")
        self.assertEqual(restored.ledger.candidates[("rel:greater-than",1)].state,CandidateState.PROPOSED)
    def test_stale_stream_cursor_rejects_concurrent_writer(self):
        self.store.register_candidate(candidate())
        self.memory.append_lifecycle_event(event_id="external",scope="project-a",
          payload={"schema_version":"external-v1","kind":"external","body":{}},expected_sequence=1)
        with self.assertRaises(ZPCMError): self.store.apply(propose())
    def test_scope_isolation(self):
        self.store.register_candidate(candidate()); other=PersistentLifecycleLedger(self.memory,scope="project-b")
        self.assertEqual(other.snapshot()["candidates"],[]); self.assertEqual(len(self.store.snapshot()["candidates"]),1)
    def test_revision_event_is_idempotent(self):
        self.store.register_candidate(candidate())
        revised=Action(action_id="propose",action_type=ActionType.PROPOSE,candidate_id="rel:greater-than",
          candidate_version=1,from_state=CandidateState.OBSERVED,to_state=CandidateState.PROPOSED)
        self.store.apply(revised)
        # Exercise the revision contract using a small valid lifecycle sequence.
        challenged=Action(action_id="discriminate",action_type=ActionType.REQUEST_DISCRIMINATION,
          candidate_id="rel:greater-than",candidate_version=1,
          from_state=CandidateState.PROPOSED,to_state=CandidateState.DISCRIMINATION_PENDING)
        self.store.apply(challenged)
        self.store.register_evidence(Evidence(evidence_id="train2",episode_id="ep-1",
          world_family="finite-rule-world",split_role=SplitRole.TRAIN,observation_id="obs-2",
          outcome="private-label",model_version="model-0"))
        self.store.apply(Action(action_id="train",action_type=ActionType.TRAIN_SUPPORT,
          candidate_id="rel:greater-than",candidate_version=1,evidence_ids=("train2",),
          from_state=CandidateState.DISCRIMINATION_PENDING,to_state=CandidateState.TRAIN_SUPPORTED))
        self.store.register_evidence(Evidence(evidence_id="gate",episode_id="ep-1",
          world_family="finite-rule-world",split_role=SplitRole.GATE_FINAL,observation_id="obs-g",
          outcome="gate-label",model_version="model-0"))
        self.store.apply(Action(action_id="gate",action_type=ActionType.GATE_VALIDATE,
          candidate_id="rel:greater-than",candidate_version=1,evidence_ids=("gate",),
          from_state=CandidateState.TRAIN_SUPPORTED,to_state=CandidateState.GATE_VALIDATED))
        self.store.register_evidence(Evidence(evidence_id="counter",episode_id="ep-1",
          world_family="finite-rule-world",split_role=SplitRole.LOCKED_TEST,observation_id="obs-c",
          outcome="locked-secret",model_version="model-0"))
        self.store.apply(Action(action_id="challenge",action_type=ActionType.CHALLENGE,
          candidate_id="rel:greater-than",candidate_version=1,evidence_ids=("counter",),
          from_state=CandidateState.GATE_VALIDATED,to_state=CandidateState.CHALLENGED))
        self.store.apply(Action(action_id="revise",action_type=ActionType.REVISE,
          candidate_id="rel:greater-than",candidate_version=1,evidence_ids=("counter",),
          from_state=CandidateState.CHALLENGED,to_state=CandidateState.REVISED))
        args=dict(canonical_expression="x - y > 0",operator="THRESHOLD_DIFF",conditions=("threshold>=0",),
          proposer_family="revision",supporting_families=("revision",),input_types=("number","number"),
          complexity=3,proposal_cost=0.2,evidence_ids=("counter",))
        one,receipt1=self.store.create_revision("rel:greater-than",1,**args)
        two,receipt2=self.store.create_revision("rel:greater-than",1,**args)
        self.assertEqual(one,two); self.assertTrue(receipt2.replayed)
        self.assertEqual(receipt1.sequence,receipt2.sequence)
        self.assertNotIn("locked-secret",str(self.memory.replay_lifecycle_events(scope="project-a")))
    def test_authorization_receipt_consumed_atomically_and_survives_reopen(self):
        candidate_item = authorized_candidate()
        evidence_item = evidence()
        receipt = verified_receipt(evidence_item)
        now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        bundle = self.store.register_candidate_bundle(
            candidate_item, (evidence_item,), authorization_receipt=receipt, consumed_at=now, writer_identity=writer_identity(),
        )
        self.assertIsNotNone(bundle.authorization)
        self.assertFalse(bundle.authorization.replayed)
        self.assertEqual(
            [event["payload"]["kind"] for event in self.memory.replay_lifecycle_events(scope="project-a")],
            ["evidence_registered", "candidate_registered", "authorization_consumed"],
        )
        before = self.store.snapshot()
        self.memory.close()
        self.memory = ZPCMMemory(self.path)
        self.store = PersistentLifecycleLedger(self.memory, scope="project-a")
        self.assertEqual(self.store.snapshot(), before)
        replay = self.store.register_candidate_bundle(
            candidate_item, (evidence_item,), authorization_receipt=receipt,
            consumed_at=now + timedelta(seconds=10), writer_identity=writer_identity(),
        )
        self.assertTrue(replay.replayed)
        self.assertTrue(replay.authorization.replayed)

    def test_receipt_consumption_requires_and_audits_authenticated_writer_identity(self):
        item = evidence()
        receipt = verified_receipt(item)
        now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        candidate_item = authorized_candidate()
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(
                candidate_item, (item,), authorization_receipt=receipt, consumed_at=now,
            )
        self.assertEqual(self.memory.replay_lifecycle_events(scope="project-a"), [])
        identity = writer_identity()
        identity["credential_fingerprint"] = "not-a-sha256-fingerprint"
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(
                candidate_item, (item,), authorization_receipt=receipt,
                consumed_at=now, writer_identity=identity,
            )
        self.assertEqual(self.memory.replay_lifecycle_events(scope="project-a"), [])
        identity = writer_identity()
        self.store.register_candidate_bundle(
            candidate_item, (item,), authorization_receipt=receipt,
            consumed_at=now, writer_identity=identity,
        )
        events = self.memory.replay_lifecycle_events(scope="project-a")
        consumption = events[-1]["payload"]["body"]
        self.assertEqual(consumption["submitter_workload_id"], identity["workload_id"])
        self.assertEqual(consumption["submitter_identity_provider"], identity["identity_provider"])
        self.assertEqual(consumption["submitter_authentication_method"], identity["authentication_method"])
        self.assertEqual(consumption["submitter_credential_fingerprint"], identity["credential_fingerprint"])

    def test_receipt_backed_candidate_requires_same_receipt_on_replay(self):
        evidence_item = evidence()
        receipt = verified_receipt(evidence_item)
        now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        candidate_item = authorized_candidate()
        self.store.register_candidate_bundle(
            candidate_item, (evidence_item,), authorization_receipt=receipt, consumed_at=now,
            writer_identity=writer_identity(),
        )
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(candidate_item, (evidence_item,))

    def test_same_receipt_or_nonce_cannot_authorize_another_candidate(self):
        evidence_item = evidence()
        receipt = verified_receipt(evidence_item)
        now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        self.store.register_candidate_bundle(
            authorized_candidate(), (evidence_item,), authorization_receipt=receipt, consumed_at=now,
            writer_identity=writer_identity(),
        )
        altered_definition = {
            "schema": "csg-gcr-typed-candidate-v1",
            "parent_state_ref": "parent-1",
            "branch_ids": ["left", "right"],
            "branch_merge": {
                "authorization_ref": "grant-1",
                "authorization_evidence_refs": ["train-1"],
            },
        }
        other = replace(
            authorized_candidate(),
            candidate_id="rel:other",
            canonical_expression=json.dumps(altered_definition, sort_keys=True, separators=(",", ":")),
        )
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(
                other, (evidence_item,), authorization_receipt=receipt, consumed_at=now,
                writer_identity=writer_identity(),
            )
        reused_nonce = verified_receipt(evidence_item, receipt_id="receipt-2", nonce="nonce-1")
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(
                other, (evidence_item,), authorization_receipt=reused_nonce, consumed_at=now, writer_identity=writer_identity(),
            )

    def test_sqlite_unique_nonce_constraint_blocks_stale_second_writer(self):
        first_evidence = evidence()
        first_receipt = verified_receipt(first_evidence)
        now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        self.store.register_candidate_bundle(
            authorized_candidate(), (first_evidence,),
            authorization_receipt=first_receipt, consumed_at=now, writer_identity=writer_identity(),
        )

        second_evidence = replace(evidence(), evidence_id="train-2", observation_id="obs-2")
        second_definition = {
            "schema": "csg-gcr-typed-candidate-v1",
            "parent_state_ref": "parent-1",
            "branch_ids": ["left", "right"],
            "branch_merge": {
                "authorization_ref": "grant-2",
                "authorization_evidence_refs": ["train-2"],
            },
        }
        second_candidate = replace(
            authorized_candidate(), candidate_id="rel:other",
            canonical_expression=json.dumps(second_definition, sort_keys=True, separators=(",", ":")),
            evidence_ids=("train-2",),
        )
        safe_second_evidence = _safe_evidence(second_evidence)
        receipt_body = {
            "receipt_id": "receipt-2", "nonce": "nonce-1",
            "authorization_ref": "grant-2", "episode_id": "ep-1",
            "scope": "project-a", "parent_state_ref": "parent-1",
            "branch_ids": ["left", "right"], "authorization_evidence_refs": ["train-2"],
            "evidence_refs": ["train-2"], "issuer_id": "issuer-A",
            "verifier_id": "verifier-A", "authorization_event_digest": "c" * 64,
            "receipt_issued_at": "2026-11-12T00:29:00+00:00",
            "receipt_expires_at": "2026-11-12T00:31:00+00:00",
            "candidate_id": "rel:other", "candidate_version": 1,
            "consumed_at": "2026-11-12T00:30:00+00:00",
            "submitter_workload_id": "spiffe://zhouyi/test-writer",
            "submitter_identity_provider": "test-spiffe",
            "submitter_authentication_method": "mTLS",
            "submitter_credential_fingerprint": "c" * 64,
        }
        events = [
            {"event_id": "e12a6:evidence:train-2", "payload": {
                "schema_version": EVENT_SCHEMA, "kind": "evidence_registered",
                "body": {"evidence": _evidence_to_dict(safe_second_evidence)},
            }},
            {"event_id": "e12a6:candidate:rel:other@1", "payload": {
                "schema_version": EVENT_SCHEMA, "kind": "candidate_registered",
                "body": {"candidate": _candidate_to_dict(second_candidate)},
            }},
            {"event_id": "e12a6:authorization-consumed:receipt-2", "payload": {
                "schema_version": EVENT_SCHEMA, "kind": "authorization_consumed",
                "body": receipt_body,
            }},
        ]
        second_connection = ZPCMMemory(self.path)
        try:
            with self.assertRaises(ZPCMError):
                second_connection.append_lifecycle_events(
                    events=events, scope="project-a", expected_sequence=3,
                )
        finally:
            second_connection.close()
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope="project-a")), 3)

    def test_expired_receipt_is_not_consumed(self):
        evidence_item = evidence()
        receipt = verified_receipt(evidence_item)
        with self.assertRaises(LifecyclePersistenceError):
            self.store.register_candidate_bundle(
                authorized_candidate(), (evidence_item,), authorization_receipt=receipt,
                consumed_at=datetime(2026, 11, 12, 0, 32, tzinfo=timezone.utc),
                writer_identity=writer_identity(),
            )
        self.assertEqual(self.store.snapshot()["candidates"], [])
        self.assertEqual(self.memory.replay_lifecycle_events(scope="project-a"), [])

    def test_receipt_consumption_append_failure_is_atomic(self):
        before = self.store.snapshot()
        original = self.memory.append_lifecycle_events
        self.memory.append_lifecycle_events = lambda **kwargs: (_ for _ in ()).throw(ZPCMError("disk failure"))
        with self.assertRaises(ZPCMError):
            self.store.register_candidate_bundle(
                authorized_candidate(), (evidence(),),
                authorization_receipt=verified_receipt(),
                consumed_at=datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc),
                writer_identity=writer_identity(),
            )
        self.memory.append_lifecycle_events = original
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.memory.replay_lifecycle_events(scope="project-a"), [])

    def test_replay_rejects_tampered_event_digest(self):
        self.store.register_candidate(candidate())
        self.memory.db.execute("UPDATE memory_events SET payload_json=? WHERE event_id=?",
          ('{"tampered":true}',"e12a6:candidate:rel:greater-than@1"))
        with self.assertRaises(LifecyclePersistenceError): PersistentLifecycleLedger(self.memory,scope="project-a")

if __name__=="__main__": unittest.main()
