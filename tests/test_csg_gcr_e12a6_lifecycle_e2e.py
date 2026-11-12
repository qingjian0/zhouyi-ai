import tempfile
import hashlib
import unittest
from pathlib import Path

from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.csg_gcr_e12a6_ingestion import ingest_typed_candidate
from prototype.e12a6_lifecycle_contract import Action, ActionType, CandidateState, SplitRole
from prototype.e09_authority_services import E09AuthenticatedWorkload, E09AuthorityService
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal
from prototype.typed_hypergraph_unifier import HyperedgeProposal, RoleBinding, VariableRef, VariableSpec
from prototype.zpcm_memory import ZPCMMemory


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
        workload_id=f"spiffe://e2e/{name}", issuer_id=f"issuer:{name}",
        roles=frozenset({role}), scopes=frozenset({scope}),
        identity_provider="test-spiffe", authentication_method="mTLS",
        credential_fingerprint=hashlib.sha256(name.encode()).hexdigest(),
    )


def add_reveal(authority, split, prediction_id, *, episode, scope, track, label):
    observation_id=f"obs-{prediction_id}"
    observation_event=f"{episode}:observation:{observation_id}"
    authority.append_observation(
      "observer",episode_id=episode,event_id=observation_event,idempotency_key=observation_event,
      payload={"observation_id":observation_id,"query_id":observation_id,"scope":scope,"split":split})
    commit_event=f"{episode}:prediction:{prediction_id}"
    commit_digest=hashlib.sha256(prediction_id.encode()).hexdigest()
    commit=authority.append_prediction_commit(
      "learner",episode_id=episode,event_id=commit_event,idempotency_key=commit_event,
      causation_refs=[observation_event],
      payload={"prediction_id":prediction_id,"observation_id":observation_id,
        "query_id":observation_id,"scope":scope,"split":split,"model_version":"model-1",
        "learner_track":track,"decision_status":"PREDICT","interop_commit_digest":commit_digest})
    reveal_event=f"{episode}:reveal:{prediction_id}"
    authority.append_evidence_reveal(
      "evaluator",episode_id=episode,event_id=reveal_event,idempotency_key=reveal_event,
      causation_refs=[commit_event],
      payload={"prediction_id":prediction_id,"query_id":observation_id,"scope":scope,
        "split":split,"commit_digest":commit_digest,"event_digest":commit.payload_digest,
        "learner_track":track,"target_or_feedback":label})
    return reveal_event


def make_typed_candidate(evidence_refs):
    ref=VariableRef("world","entity")
    edge=HyperedgeProposal("edge-e2e","parent-e2e","branch-e2e","supports",
      (RoleBinding("subject",ref,"entity-e2e","Entity"),),tuple(evidence_refs))
    proposal=CandidateProposal("edge-e2e","parent-e2e","branch-e2e",(),tuple(evidence_refs),
      score=2.5,candidate_kind="supports")
    typed=TypedCandidateProposal(proposal,edge,(VariableSpec(ref,"Entity"),))
    report=TypedCandidateCoordinator().coordinate((typed,))
    return report.candidates[0]


class CSGGCRE12A6EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.episode="ep-e2e"
        self.scope="world/e2e"
        self.track="srok-e2e"
        self.e09=SQLiteEvidenceStore(Path(self.tmp.name)/"e09.db")
        self.memory=ZPCMMemory(Path(self.tmp.name)/"zpcm.db")
        self.ledger=PersistentLifecycleLedger(self.memory,scope="e2e/project")
        self.registry=StaticE09DomainRegistry({
          self.scope:E09DomainBinding("domain:e2e","finite-rule-world","registry:e2e","v1")
        })
        self.authority=E09AuthorityService(
          self.e09,authenticator=_Authenticator({
            "observer":_identity("observer","observer",self.scope),
            "learner":_identity("learner","learner",self.scope),
            "evaluator":_identity("evaluator","evaluator",self.scope),
          }),signer=_Signer(),domain_registry=self.registry)
    def tearDown(self):
        self.e09.close()
        self.memory.close()
        self.tmp.cleanup()
    def ingest(self, refs):
        candidate=make_typed_candidate(refs)
        return ingest_typed_candidate(candidate,ledger=self.ledger,e09_store=self.e09,
          episode_id=self.episode,scope=self.scope,learner_track=self.track,
          grammar_version="csg-e2e-v1",domain_registry=self.registry)
    def test_candidate_lifecycle_runs_from_csg_gcr_through_e09_e12_zpcm_and_restarts(self):
        support=add_reveal(self.authority,"SUPPORT","pred-support",episode=self.episode,
          scope=self.scope,track=self.track,label="PRIVATE_SUPPORT")
        gate=add_reveal(self.authority,"GATE_FINAL","pred-gate",episode=self.episode,
          scope=self.scope,track=self.track,label="PRIVATE_GATE")
        locked=add_reveal(self.authority,"LOCKED_TEST","pred-locked",episode=self.episode,
          scope=self.scope,track=self.track,label="PRIVATE_LOCKED")
        result=self.ingest((support,gate,locked))
        candidate=result.projection.native_candidate
        cid=candidate.candidate_id
        self.ledger.apply(Action("propose-e2e",ActionType.PROPOSE,cid,1,
          from_state=CandidateState.OBSERVED,to_state=CandidateState.PROPOSED))
        self.ledger.apply(Action("discriminate-e2e",ActionType.REQUEST_DISCRIMINATION,cid,1,
          from_state=CandidateState.PROPOSED,to_state=CandidateState.DISCRIMINATION_PENDING))
        self.ledger.apply(Action("train-e2e",ActionType.TRAIN_SUPPORT,cid,1,evidence_ids=(support,),
          from_state=CandidateState.DISCRIMINATION_PENDING,to_state=CandidateState.TRAIN_SUPPORTED))
        self.ledger.apply(Action("gate-e2e",ActionType.GATE_VALIDATE,cid,1,evidence_ids=(gate,),
          from_state=CandidateState.TRAIN_SUPPORTED,to_state=CandidateState.GATE_VALIDATED))
        self.ledger.apply(Action("challenge-e2e",ActionType.CHALLENGE,cid,1,evidence_ids=(locked,),
          from_state=CandidateState.GATE_VALIDATED,to_state=CandidateState.CHALLENGED))
        self.assertEqual(self.ledger.ledger.candidates[(cid,1)].state,CandidateState.CHALLENGED)
        before=self.ledger.snapshot()
        events=self.memory.replay_lifecycle_events(scope="e2e/project")
        self.assertEqual(len(events),9)  # 3 evidence + candidate + 5 lifecycle actions
        self.assertNotIn("PRIVATE_SUPPORT",str(events))
        self.assertNotIn("PRIVATE_GATE",str(events))
        self.assertNotIn("PRIVATE_LOCKED",str(events))
        self.memory.close()
        self.memory=ZPCMMemory(Path(self.tmp.name)/"zpcm.db")
        self.ledger=PersistentLifecycleLedger(self.memory,scope="e2e/project")
        self.assertEqual(self.ledger.snapshot(),before)
        restored=self.ledger.ledger
        self.assertEqual(restored.candidates[(cid,1)].state,CandidateState.CHALLENGED)
        self.assertEqual(len(restored.actions),5)
        self.assertEqual({x.split_role for x in restored.evidence.values()},
          {SplitRole.TRAIN,SplitRole.GATE_FINAL,SplitRole.LOCKED_TEST})
    def test_gate_dev_cannot_be_used_as_gate_final(self):
        support=add_reveal(self.authority,"SUPPORT","pred-support",episode=self.episode,
          scope=self.scope,track=self.track,label="PRIVATE_SUPPORT")
        dev=add_reveal(self.authority,"GATE_DEV","pred-dev",episode=self.episode,
          scope=self.scope,track=self.track,label="PRIVATE_DEV")
        result=self.ingest((support,dev))
        cid=result.projection.native_candidate.candidate_id
        self.ledger.apply(Action("propose-dev",ActionType.PROPOSE,cid,1,
          from_state=CandidateState.OBSERVED,to_state=CandidateState.PROPOSED))
        self.ledger.apply(Action("discriminate-dev",ActionType.REQUEST_DISCRIMINATION,cid,1,
          from_state=CandidateState.PROPOSED,to_state=CandidateState.DISCRIMINATION_PENDING))
        self.ledger.apply(Action("train-dev",ActionType.TRAIN_SUPPORT,cid,1,evidence_ids=(support,),
          from_state=CandidateState.DISCRIMINATION_PENDING,to_state=CandidateState.TRAIN_SUPPORTED))
        before=self.ledger.snapshot()
        count=len(self.memory.replay_lifecycle_events(scope="e2e/project"))
        with self.assertRaisesRegex(ValueError,"GATE_FINAL"):
            self.ledger.apply(Action("invalid-gate",ActionType.GATE_VALIDATE,cid,1,evidence_ids=(dev,),
              from_state=CandidateState.TRAIN_SUPPORTED,to_state=CandidateState.GATE_VALIDATED))
        self.assertEqual(self.ledger.snapshot(),before)
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope="e2e/project")),count)


if __name__=="__main__": unittest.main()
