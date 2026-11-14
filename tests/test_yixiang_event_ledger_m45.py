import unittest
from prototype.yixiang_event_ledger_m45 import *

def ev(i,seq,prev="",**kw):
 d=dict(event_id=i,sequence=seq,run_id="r1",kind=EventKind.OBSERVATION_RECORDED,stage="M47",
 artifact_ref="artifact",evidence_refs=("evidence",),context_id="ctx",timestamp="2026-11-14T00:00:00Z",
 actor="reviewer",payload_ref="payload",previous_event_id=prev); d.update(kw); return ExperimentEvent(**d)

class M45Tests(unittest.TestCase):
 def test_empty_ledger_valid(self): self.assertTrue(audit_ledger(()).valid)
 def test_single_event_valid(self): self.assertTrue(audit_ledger((ev("e1",0),)).valid)
 def test_append_event(self): self.assertEqual(len(append_event((),ev("e1",0))),1)
 def test_sequence_must_be_contiguous(self): self.assertIn("non_contiguous_sequence:e1",audit_ledger((ev("e1",1),)).issues)
 def test_chain_link_checked(self): self.assertIn("broken_event_link:e2",audit_ledger((ev("e1",0),ev("e2",1,"wrong"))).issues)
 def test_duplicate_id_rejected(self): self.assertIn("duplicate_or_empty_event_id",audit_ledger((ev("e1",0),ev("e1",1,"e1"))).issues)
 def test_context_constant_per_run(self): self.assertIn("run_context_changed:r1",audit_ledger((ev("e1",0),ev("e2",1,"e1",context_id="ctx2"))).issues)
 def test_missing_evidence(self): self.assertIn("missing_evidence_refs:e1",audit_ledger((ev("e1",0,evidence_refs=()),)).issues)
 def test_missing_artifact(self): self.assertIn("missing_required_provenance:e1",audit_ledger((ev("e1",0,artifact_ref=""),)).issues)
 def test_append_rejects_wrong_sequence(self):
  with self.assertRaises(ValueError): append_event((),ev("e1",1))
 def test_append_rejects_wrong_link(self):
  with self.assertRaises(ValueError): append_event((ev("e1",0),),ev("e2",1,"bad"))
 def test_append_preserves_prior(self):
  old=(ev("e1",0),); new=append_event(old,ev("e2",1,"e1")); self.assertEqual(len(old),1); self.assertEqual(len(new),2)
