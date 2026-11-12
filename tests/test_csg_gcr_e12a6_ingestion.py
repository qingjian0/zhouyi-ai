import tempfile
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.csg_gcr_e12a6_adapter import adapt_typed_candidate
from prototype.csg_gcr_e12a6_ingestion import CSGGCRIngestionError, ingest_typed_candidate
from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash
from prototype.e12a6_zpcm_persistence import LifecyclePersistenceError, PersistentLifecycleLedger
from prototype.e09_authority_services import E09AuthenticatedWorkload, E09AuthorityService
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal
from prototype.typed_hypergraph_unifier import HyperedgeProposal, RoleBinding, VariableRef, VariableSpec
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


class _Authenticator:
    def __init__(self, identities):
        self.identities = identities
    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown credential")
        return self.identities[credential]


class _Signer:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


def _identity(name, role, scope):
    return E09AuthenticatedWorkload(
        workload_id=f"spiffe://test/{name}", issuer_id=f"issuer:{name}",
        roles=frozenset({role}), scopes=frozenset({scope}),
        identity_provider="test-spiffe", authentication_method="mTLS",
        credential_fingerprint=hashlib.sha256(name.encode()).hexdigest(),
    )


def make_e09_episode(authority, *, episode="ep-1", scope="world/test", track="srok", label="SECRET_TARGET"):
    observation_id="obs-1"
    observation_event=f"{episode}:observation:{observation_id}"
    authority.append_observation(
      "observer", episode_id=episode, event_id=observation_event,
      idempotency_key="obs-1",
      payload={"observation_id":observation_id,"query_id":observation_id,
               "scope":scope,"split":"SUPPORT"})
    commit_event=f"{episode}:prediction:pred-1"
    commit_digest=hashlib.sha256(b"pred-1").hexdigest()
    commit=authority.append_prediction_commit(
      "learner", episode_id=episode, event_id=commit_event,
      idempotency_key="pred-1", causation_refs=[observation_event],
      payload={"prediction_id":"pred-1","observation_id":observation_id,
        "query_id":observation_id,"scope":scope,"split":"SUPPORT",
        "model_version":"model-1","learner_track":track,
        "decision_status":"PREDICT","interop_commit_digest":commit_digest})
    evidence_ref=f"{episode}:reveal:pred-1"
    authority.append_evidence_reveal(
      "evaluator", episode_id=episode, event_id=evidence_ref,
      idempotency_key=evidence_ref, causation_refs=[commit_event],
      payload={"prediction_id":"pred-1","query_id":observation_id,
        "scope":scope,"split":"SUPPORT","commit_digest":commit_digest,
        "event_digest":commit.payload_digest,"learner_track":track,
        "target_or_feedback":label})
    return evidence_ref


def make_candidate(evidence_ref):
    ref=VariableRef("world","entity")
    edge=HyperedgeProposal("edge-1","parent-1","branch-1","supports",
      (RoleBinding("subject",ref,"entity-1","Entity"),),(evidence_ref,))
    proposal=CandidateProposal("edge-1","parent-1","branch-1",(),(evidence_ref,),
      score=3.0,candidate_kind="supports")
    typed=TypedCandidateProposal(proposal,edge,(VariableSpec(ref,"Entity"),))
    report=TypedCandidateCoordinator().coordinate((typed,))
    return report.candidates[0]


class CSGGCRAtomicIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.e09=SQLiteEvidenceStore(Path(self.tmp.name)/"e09.db")
        self.memory=ZPCMMemory(Path(self.tmp.name)/"zpcm.db")
        self.ledger=PersistentLifecycleLedger(self.memory,scope="csg-gcr/project")
        self.scope="world/test"
        self.track="srok"
        self.registry=StaticE09DomainRegistry({
          self.scope:E09DomainBinding("domain:test","finite-rule-world","registry:test","v1")
        })
        self.authority=E09AuthorityService(
          self.e09,authenticator=_Authenticator({
            "observer":_identity("observer","observer",self.scope),
            "learner":_identity("learner","learner",self.scope),
            "evaluator":_identity("evaluator","evaluator",self.scope),
          }),signer=_Signer(),domain_registry=self.registry)
        self.ref=make_e09_episode(self.authority)
        self.result=make_candidate(self.ref)
    def tearDown(self):
        self.e09.close(); self.memory.close(); self.tmp.cleanup()
    def ingest(self):
        return ingest_typed_candidate(self.result,ledger=self.ledger,e09_store=self.e09,
          episode_id="ep-1",scope=self.scope,learner_track=self.track,grammar_version="csg-v1",
          domain_registry=self.registry)
    def test_candidate_and_e09_evidence_are_registered_as_one_bundle(self):
        result=self.ingest()
        snapshot=self.ledger.snapshot()
        self.assertEqual(len(snapshot["candidates"]),1)
        self.assertEqual(len(snapshot["evidence"]),1)
        self.assertEqual(snapshot["evidence"][0]["split_role"],"train")
        events=self.memory.replay_lifecycle_events(scope="csg-gcr/project")
        self.assertEqual(len(events),2)
        self.assertNotIn("SECRET_TARGET",str(events))
        self.assertEqual(result.verified_evidence_refs,(self.ref,))
        self.assertFalse(result.receipt.replayed)
    def test_bundle_retry_is_idempotent(self):
        first=self.ingest(); count=len(self.memory.replay_lifecycle_events(scope="csg-gcr/project"))
        second=self.ingest()
        self.assertTrue(second.receipt.replayed)
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope="csg-gcr/project")),count)
        self.assertEqual(first.receipt.candidate.sequence,second.receipt.candidate.sequence)
    def test_missing_trusted_registry_fails_before_any_write(self):
        with self.assertRaisesRegex(CSGGCRIngestionError,"trusted domain registry is required"):
            ingest_typed_candidate(self.result,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope=self.scope,learner_track=self.track,grammar_version="v1")
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_caller_world_family_override_is_rejected(self):
        with self.assertRaisesRegex(CSGGCRIngestionError,"caller-supplied"):
            ingest_typed_candidate(self.result,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope=self.scope,learner_track=self.track,grammar_version="v1",
              domain_registry=self.registry,world_family_by_evidence={self.ref:"attacker-family"})
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_invalid_e09_reference_fails_before_any_write(self):
        bad=make_candidate("ep-1:reveal:missing")
        with self.assertRaises(ValueError):
            ingest_typed_candidate(bad,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="v1",
              domain_registry=self.registry)
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_cross_branch_candidate_fails_closed(self):
        coordinated=replace(self.result.coordinated,branch_ids=("branch-1","branch-2"))
        unification=replace(self.result.unification,branch_ids=("branch-1","branch-2"))
        bad=replace(self.result,coordinated=coordinated,unification=unification)
        with self.assertRaisesRegex(CSGGCRIngestionError,"cross-branch"):
            ingest_typed_candidate(bad,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="v1",
              domain_registry=self.registry)
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_append_failure_leaves_bundle_and_ledger_unchanged(self):
        before=self.ledger.snapshot()
        original=self.memory.append_lifecycle_events
        self.memory.append_lifecycle_events=lambda **kwargs: (_ for _ in ()).throw(ZPCMError("disk failure"))
        with self.assertRaises(ZPCMError): self.ingest()
        self.memory.append_lifecycle_events=original
        self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_crash_after_batch_commit_recovers_whole_bundle(self):
        original=self.memory.append_lifecycle_events
        def commit_then_crash(**kwargs):
            original(**kwargs)
            raise RuntimeError("simulated crash after bundle commit")
        self.memory.append_lifecycle_events=commit_then_crash
        with self.assertRaises(RuntimeError): self.ingest()
        self.memory.append_lifecycle_events=original
        self.memory.close()
        self.memory=ZPCMMemory(Path(self.tmp.name)/"zpcm.db")
        restored=PersistentLifecycleLedger(self.memory,scope="csg-gcr/project")
        self.assertEqual(len(restored.snapshot()["candidates"]),1)
        self.assertEqual(len(restored.snapshot()["evidence"]),1)
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope="csg-gcr/project")),2)
        self.assertNotIn("SECRET_TARGET",str(self.memory.replay_lifecycle_events(scope="csg-gcr/project")))
    def test_zpcm_batch_rolls_back_if_second_event_insert_fails(self):
        original=self.memory._append
        calls={"count":0}
        def fail_second(event_id,event_type,scope,payload):
            calls["count"]+=1
            if calls["count"]==2:
                raise ZPCMError("simulated second insert failure")
            return original(event_id,event_type,scope,payload)
        self.memory._append=fail_second
        with self.assertRaises(ZPCMError):
            self.memory.append_lifecycle_events(
                events=[{"event_id":"batch-e1","payload":{"kind":"one"}},
                        {"event_id":"batch-e2","payload":{"kind":"two"}}],
                scope="atomic-test",expected_sequence=0,
            )
        self.memory._append=original
        self.assertEqual(self.memory.replay_lifecycle_events(scope="atomic-test"),[])
    def test_partial_bundle_replay_is_rejected(self):
        from prototype.e12a6_zpcm_persistence import _safe_evidence, _evidence_to_dict, EVENT_SCHEMA
        safe=_safe_evidence(resolve_for_test(self.e09,self.ref,self.registry))
        self.memory.append_lifecycle_event(event_id=f"e12a6:evidence:{safe.evidence_id}",
          scope="csg-gcr/project",payload={"schema_version":EVENT_SCHEMA,"kind":"evidence_registered",
          "body":{"evidence":_evidence_to_dict(safe)}},expected_sequence=0)
        self.ledger=PersistentLifecycleLedger(self.memory,scope="csg-gcr/project")
        with self.assertRaises(LifecyclePersistenceError):
            self.ledger.register_candidate_bundle(
              adapt_typed_candidate(self.result,scope="world/test",grammar_version="v1").native_candidate,
              (safe,),
            )


def resolve_for_test(store, ref, registry):
    from prototype.e09_e12a6_evidence_bridge import resolve_e09_reveal
    return resolve_e09_reveal(store,episode_id="ep-1",evidence_ref=ref,scope="world/test",
      learner_track="srok",domain_registry=registry)


if __name__=="__main__": unittest.main()
