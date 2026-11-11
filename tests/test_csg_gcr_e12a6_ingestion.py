import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.csg_gcr_e12a6_adapter import adapt_typed_candidate
from prototype.csg_gcr_e12a6_ingestion import CSGGCRIngestionError, ingest_typed_candidate
from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash
from prototype.e12a6_zpcm_persistence import LifecyclePersistenceError, PersistentLifecycleLedger
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal
from prototype.typed_hypergraph_unifier import HyperedgeProposal, RoleBinding, VariableRef, VariableSpec
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


def make_e09_episode(store, *, episode="ep-1", scope="world/test", track="srok", label="SECRET_TARGET"):
    evidence_ref=f"{episode}:reveal:pred-1"
    observation_id="obs-1"
    observation_event=f"{episode}:observation:{observation_id}"
    store.append_event(episode_id=episode,event_id=observation_event,event_type="observation",
      idempotency_key="obs-1",actor_role="runner",
      payload={"observation_id":observation_id,"query_id":observation_id,"scope":scope,"split":"SUPPORT"},
      protocol_version=STRICT_PROTOCOL_VERSION)
    commit_event=f"{episode}:prediction:pred-1"
    commit_digest="a"*64
    commit=store.append_event(episode_id=episode,event_id=commit_event,event_type="prediction_commit",
      idempotency_key="pred-1",actor_role="learner",causation_refs=[observation_event],
      payload={"prediction_id":"pred-1","observation_id":observation_id,"query_id":observation_id,
        "scope":scope,"split":"SUPPORT","model_version":"model-1","learner_track":track,
        "decision_status":"PREDICT","interop_commit_digest":commit_digest},
      protocol_version=STRICT_PROTOCOL_VERSION)
    store.append_event(episode_id=episode,event_id=evidence_ref,event_type="evidence_reveal",
      idempotency_key=evidence_ref,actor_role="evaluator",causation_refs=[commit_event],
      payload={"prediction_id":"pred-1","query_id":observation_id,"scope":scope,"split":"SUPPORT",
        "commit_digest":commit_digest,"event_digest":commit.payload_digest,
        "learner_track":track,"target_or_feedback":label,"reveal_source":"test"},
      protocol_version=STRICT_PROTOCOL_VERSION)
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
        self.ref=make_e09_episode(self.e09)
        self.result=make_candidate(self.ref)
    def tearDown(self):
        self.e09.close(); self.memory.close(); self.tmp.cleanup()
    def ingest(self):
        return ingest_typed_candidate(self.result,ledger=self.ledger,e09_store=self.e09,
          episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="csg-v1",
          world_family_by_evidence={self.ref:"finite-rule-world"})
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
    def test_missing_world_family_fails_before_any_write(self):
        with self.assertRaises(CSGGCRIngestionError):
            ingest_typed_candidate(self.result,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="v1",
              world_family_by_evidence={})
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_invalid_e09_reference_fails_before_any_write(self):
        bad=make_candidate("ep-1:reveal:missing")
        with self.assertRaises(ValueError):
            ingest_typed_candidate(bad,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="v1",
              world_family_by_evidence={"ep-1:reveal:missing":"finite-rule-world"})
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_cross_branch_candidate_fails_closed(self):
        coordinated=replace(self.result.coordinated,branch_ids=("branch-1","branch-2"))
        unification=replace(self.result.unification,branch_ids=("branch-1","branch-2"))
        bad=replace(self.result,coordinated=coordinated,unification=unification)
        with self.assertRaisesRegex(CSGGCRIngestionError,"cross-branch"):
            ingest_typed_candidate(bad,ledger=self.ledger,e09_store=self.e09,
              episode_id="ep-1",scope="world/test",learner_track="srok",grammar_version="v1",
              world_family_by_evidence={self.ref:"finite-rule-world"})
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_append_failure_leaves_bundle_and_ledger_unchanged(self):
        before=self.ledger.snapshot()
        original=self.memory.append_lifecycle_events
        self.memory.append_lifecycle_events=lambda **kwargs: (_ for _ in ()).throw(ZPCMError("disk failure"))
        with self.assertRaises(ZPCMError): self.ingest()
        self.memory.append_lifecycle_events=original
        self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(self.memory.replay_lifecycle_events(scope="csg-gcr/project"),[])
    def test_partial_bundle_replay_is_rejected(self):
        from prototype.e12a6_zpcm_persistence import _safe_evidence, _evidence_to_dict, EVENT_SCHEMA
        safe=_safe_evidence(resolve_for_test(self.e09,self.ref))
        self.memory.append_lifecycle_event(event_id=f"e12a6:evidence:{safe.evidence_id}",
          scope="csg-gcr/project",payload={"schema_version":EVENT_SCHEMA,"kind":"evidence_registered",
          "body":{"evidence":_evidence_to_dict(safe)}},expected_sequence=0)
        self.ledger=PersistentLifecycleLedger(self.memory,scope="csg-gcr/project")
        with self.assertRaises(LifecyclePersistenceError):
            self.ledger.register_candidate_bundle(
              adapt_typed_candidate(self.result,scope="world/test",grammar_version="v1").native_candidate,
              (safe,),
            )


def resolve_for_test(store, ref):
    from prototype.e09_e12a6_evidence_bridge import resolve_e09_reveal
    return resolve_e09_reveal(store,episode_id="ep-1",evidence_ref=ref,scope="world/test",
      learner_track="srok",world_family="finite-rule-world")


if __name__=="__main__": unittest.main()
