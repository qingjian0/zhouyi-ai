import tempfile
import unittest
from pathlib import Path
from prototype.e12a6_lifecycle_contract import Action,ActionType,Candidate,CandidateState,Evidence,SplitRole
from prototype.e12a6_zpcm_persistence import LifecyclePersistenceError,PersistentLifecycleLedger
from prototype.zpcm_memory import ZPCMError,ZPCMMemory

def candidate():
    return Candidate(candidate_id="rel:greater-than",version=1,canonical_expression="x > y",
      proposer_family="relational",supporting_families=("relational","residual"),
      input_types=("number","number"),operator="GT")
def evidence():
    return Evidence(evidence_id="train-1",episode_id="ep-1",world_family="finite-rule-world",
      split_role=SplitRole.TRAIN,observation_id="obs-1",outcome="true",model_version="model-0",
      prediction_commit_step=1,label_visibility_step=2)
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
        before=self.store.snapshot(); self.memory.close(); self.memory=ZPCMMemory(self.path)
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
    def test_replay_rejects_tampered_event_digest(self):
        self.store.register_candidate(candidate())
        self.memory.db.execute("UPDATE memory_events SET payload_json=? WHERE event_id=?",
          ('{"tampered":true}',"e12a6:candidate:rel:greater-than@1"))
        with self.assertRaises(LifecyclePersistenceError): PersistentLifecycleLedger(self.memory,scope="project-a")

if __name__=="__main__": unittest.main()
