import unittest
from dataclasses import replace
from prototype.yixiang_evidence_event_ledger_m45 import *

def ledger():
 l=EvidenceLedger()
 l.append("e1","action","r1","2026-11-14T00:00:00Z",{"do":"x=1"},("design:1",),"data-v1","abc123")
 return l

class M45Tests(unittest.TestCase):
 def test_empty_ledger_valid(self): self.assertTrue(EvidenceLedger().audit().valid)
 def test_append_creates_sequence_one(self): self.assertEqual(ledger().events[0].sequence,1)
 def test_digest_is_sha256_length(self): self.assertEqual(len(ledger().head_digest),64)
 def test_append_chain_parent(self):
  l=ledger(); parent=l.head_digest
  e=l.append("e2","observation","r1","2026-11-14T00:01:00Z",{"y":2},("sample:1",),"data-v1","abc123")
  self.assertEqual(e.previous_digest,parent)
 def test_valid_two_event_chain(self):
  l=ledger(); l.append("e2","observation","r1","t2",{"y":2},("s1",),"d1","c1")
  self.assertTrue(l.audit().valid)
 def test_duplicate_id_rejected(self):
  l=ledger()
  with self.assertRaisesRegex(ValueError,"duplicate_event_id"):
   l.append("e1","observation","r1","t2",{},("s",),"d","c")
 def test_unknown_event_type_rejected(self):
  with self.assertRaisesRegex(ValueError,"unsupported_event_type"):
   EvidenceLedger().append("e","guess","r","t",{},("s",),"d","c")
 def test_missing_source_ref_rejected(self):
  with self.assertRaisesRegex(ValueError,"source_refs_required"):
   EvidenceLedger().append("e","action","r","t",{},(),"d","c")
 def test_blank_source_ref_rejected(self):
  with self.assertRaisesRegex(ValueError,"source_refs_required"):
   EvidenceLedger().append("e","action","r","t",{},(" ",),"d","c")
 def test_required_text_rejected(self):
  with self.assertRaisesRegex(ValueError,"required_text_field_missing"):
   EvidenceLedger().append(" ","action","r","t",{},("s",),"d","c")
 def test_nan_payload_rejected(self):
  with self.assertRaises(ValueError):
   EvidenceLedger().append("e","action","r","t",{"x":float("nan")},("s",),"d","c")
 def test_payload_key_order_canonical(self):
  a=EvidenceLedger(); b=EvidenceLedger()
  x=a.append("e","action","r","t",{"a":1,"b":2},("s",),"d","c")
  y=b.append("e","action","r","t",{"b":2,"a":1},("s",),"d","c")
  self.assertEqual(x.digest,y.digest)
 def test_tampered_payload_detected(self):
  l=ledger(); l._events[0]=replace(l.events[0],payload_json='{"do":"x=2"}')
  self.assertIn("digest_mismatch:e1",l.audit().issues)
 def test_tampered_parent_detected(self):
  l=ledger(); l.append("e2","observation","r","t",{},("s",),"d","c")
  l._events[1]=replace(l.events[1],previous_digest="bad")
  self.assertIn("broken_parent:e2",l.audit().issues)
 def test_sequence_gap_detected(self):
  l=ledger(); l._events[0]=replace(l.events[0],sequence=3)
  self.assertIn("sequence_gap:e1",l.audit().issues)
 def test_events_property_is_immutable_tuple(self): self.assertIsInstance(ledger().events,tuple)
 def test_export_preserves_provenance(self):
  row=ledger().export_records()[0]
  self.assertEqual(row["source_refs"],("design:1",))
  self.assertEqual(row["dataset_version"],"data-v1")
 def test_all_supported_event_types(self):
  for kind in ALLOWED_EVENT_TYPES:
   self.assertEqual(EvidenceLedger().append("e",kind,"r","t",{},("s",),"d","c").event_type,kind)
 def test_digest_changes_when_source_changes(self):
  a=EvidenceLedger().append("e","action","r","t",{},("s1",),"d","c")
  b=EvidenceLedger().append("e","action","r","t",{},("s2",),"d","c")
  self.assertNotEqual(a.digest,b.digest)
 def test_no_mutating_api_exposed(self): self.assertFalse(hasattr(ledger(),"delete"))
