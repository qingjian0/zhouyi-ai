import tempfile,unittest
from pathlib import Path
from prototype.zpcm_memory import ZPCMError,ZPCMMemory,canonical
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/"m.db";self.m=ZPCMMemory(self.path)
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def test_domain_event_queries_have_composite_index(self):
  index_names={row[1] for row in self.m.db.execute("PRAGMA index_list(memory_events)")}
  self.assertIn("memory_events_type_scope_seq",index_names)
  plans={
   "forward": self.m.db.execute("EXPLAIN QUERY PLAN SELECT seq FROM memory_events WHERE event_type=? AND scope=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?",("m2_cognition","s",0,100,10)).fetchall(),
   "reverse": self.m.db.execute("EXPLAIN QUERY PLAN SELECT seq FROM memory_events WHERE event_type=? AND scope=? AND seq<? AND seq<=? ORDER BY seq DESC LIMIT ?",("m2_cognition","s",100,100,10)).fetchall(),
   "latest": self.m.db.execute("EXPLAIN QUERY PLAN SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",("m2_cognition","s")).fetchall(),
  }
  for query_name, rows in plans.items():
   detail=" ".join(str(row[3]) for row in rows)
   with self.subTest(query=query_name):
    self.assertIn("memory_events_type_scope_seq",detail)

 def test_generic_domain_events_share_the_authoritative_event_log(self):
  first=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:1",
      scope="project",payload={"kind":"observation","record_id":"obs-1"},expected_sequence=0)
  second=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:2",
      scope="project",payload={"kind":"observation","record_id":"obs-2"},expected_sequence=first["sequence"])
  self.assertFalse(first["replayed"]);self.assertFalse(second["replayed"])
  events=self.m.replay_domain_events(event_type="m2_cognition",scope="project")
  self.assertEqual([x["event_id"] for x in events],["m2:obs:1","m2:obs:2"])
  self.assertEqual(self.m.db.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0],2)
 def test_domain_event_retry_is_idempotent_and_content_conflicts_fail(self):
  first=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:1",
      scope="project",payload={"kind":"observation","record_id":"obs-1"},expected_sequence=0)
  replay=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:1",
      scope="project",payload={"kind":"observation","record_id":"obs-1"},expected_sequence=0)
  self.assertTrue(replay["replayed"]);self.assertEqual(first["sequence"],replay["sequence"])
  with self.assertRaises(ZPCMError):
   self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:1",
       scope="project",payload={"kind":"observation","record_id":"changed"},expected_sequence=0)
 def test_domain_sequences_are_isolated_by_type_and_scope(self):
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:1",scope="a",payload={"n":1},expected_sequence=0)
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:2",scope="b",payload={"n":2},expected_sequence=0)
  self.m.append_domain_event(event_type="other_domain",event_id="other:1",scope="a",payload={"n":3},expected_sequence=0)
  self.assertEqual(len(self.m.replay_domain_events(event_type="m2_cognition",scope="a")),1)
  self.assertEqual(len(self.m.replay_domain_events(event_type="m2_cognition",scope="b")),1)
  self.assertEqual(len(self.m.replay_domain_events(event_type="other_domain",scope="a")),1)
 def test_domain_replay_verifies_payload_digest(self):
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:obs:1",
      scope="project",payload={"kind":"observation"},expected_sequence=0)
  self.m.db.execute("UPDATE memory_events SET payload_json=? WHERE event_id=?",
      ('{"kind":"tampered"}',"m2:obs:1"))
  with self.assertRaises(ZPCMError):
   self.m.replay_domain_events(event_type="m2_cognition",scope="project")

 def test_protocol_projection_idempotent_redacts_non_support(self):
  es=[{"event_id":"e1","event_type":"observation","payload_digest":"d1","payload":{"scope":"s","split":"SUPPORT"}},
      {"event_id":"e2","event_type":"evidence_reveal","payload_digest":"d2","payload":{"scope":"s","split":"LOCKED_TEST","target_or_feedback":"SECRET","learner_track":"srok"}},
      {"event_id":"e3","event_type":"evidence_reveal","payload_digest":"d3","payload":{"scope":"s","split":"SUPPORT","target_or_feedback":"yes","learner_track":"srok"}}]
  self.assertEqual(self.m.sync_protocol_events(es,scope="s",learner_track="srok"),3)
  self.assertEqual(self.m.sync_protocol_events(es,scope="s",learner_track="srok"),0)
  data=str(self.m.retrieve(scope="s",max_items=9));self.assertNotIn("SECRET",data);self.assertNotIn('"target_or_feedback": "yes"',data)
  self.assertTrue(self.m.verify_integrity()["ok"])
 def test_support_targets_are_always_redacted_from_memory_projection(self):
  e={"event_id":"e","event_type":"evidence_reveal","payload_digest":"d","payload":{"scope":"s","split":"SUPPORT","target_or_feedback":"answer","learner_track":"srok"}}
  self.m.sync_protocol_events([e],scope="s",learner_track="srok")
  self.assertNotIn("answer",str(self.m.retrieve(scope="s")))
 def test_assertions_conflict_and_retraction(self):
  self.assertEqual(self.m.add_assertion(assertion_id="a1",subject_id="x",predicate="color",object_value="blue",scope="s",source_event_id="a1e"),"ACTIVE")
  self.assertEqual(self.m.add_assertion(assertion_id="a2",subject_id="x",predicate="color",object_value="red",scope="s",source_event_id="a2e"),"CONTESTED")
  self.assertEqual({x["status"] for x in self.m.assertions(scope="s")},{"CONTESTED"})
  self.m.retract_assertion("a2",event_id="r2",scope="s")
  self.assertEqual([x["status"] for x in self.m.assertions(scope="s")],["ACTIVE","RETRACTED"])
 def test_scope_and_working_set_budgets(self):
  for i in range(5):self.m.append_item(item_id=f"i{i}",item_type="semantic",scope="s",content={"text":f"fact {i}"},source_event_id=f"src{i}")
  self.m.append_item(item_id="other",item_type="semantic",scope="other",content={"text":"secret"},source_event_id="other-src")
  p=self.m.retrieve(scope="s",max_items=2,max_bytes=4096);self.assertEqual(p["item_count"],2);self.assertTrue(p["truncated"]);self.assertFalse(p["complete"]);self.assertNotIn("secret",str(p))
 def test_byte_budget_and_reopen(self):
  self.m.append_item(item_id="large",item_type="episode",scope="s",content={"text":"x"*1000},source_event_id="large-src")
  p=self.m.retrieve(scope="s",max_bytes=64);self.assertEqual(p["item_count"],0);self.assertTrue(p["truncated"])
  self.m.close();self.m=ZPCMMemory(self.path);self.assertEqual(self.m.retrieve(scope="s")["item_count"],1)
 def test_sync_episode_projects_authoritative_e09_event_log(self):
  source=SQLiteEvidenceStore(Path(self.tmp.name)/"e09.db")
  try:
   source.append_event(episode_id="ep",event_id="obs-1",event_type="observation",
       idempotency_key="obs-1",actor_role="runner",
       payload={"observation_id":"o1","scope":"s","split":"SUPPORT"})
   self.assertEqual(self.m.sync_episode(source,episode_id="ep",scope="s",learner_track="srok"),1)
   self.assertEqual(self.m.sync_episode(source,episode_id="ep",scope="s",learner_track="srok"),0)
   packet=self.m.retrieve(scope="s")
   self.assertEqual(packet["item_count"],1)
   self.assertEqual(packet["items"][0]["source_event_id"],"obs-1")
  finally:source.close()

 def test_keyset_reader_pages_typed_scope_without_offset(self):
  first=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:1",
      scope="project",payload={"n":1},expected_sequence=0)
  self.m.append_domain_event(event_type="other",event_id="other:1",
      scope="project",payload={"n":99},expected_sequence=0)
  second=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:2",
      scope="project",payload={"n":2},expected_sequence=first["sequence"])
  third=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:3",
      scope="project",payload={"n":3},expected_sequence=second["sequence"])
  events=list(self.m.iter_domain_events(event_type="m2_cognition",scope="project",page_size=2))
  self.assertEqual([event["event_id"] for event in events],["m2:1","m2:2","m2:3"])
  tail=list(self.m.iter_domain_events(event_type="m2_cognition",scope="project",
                                      after_sequence=first["sequence"],page_size=1))
  self.assertEqual([event["event_id"] for event in tail],["m2:2","m2:3"])
  self.assertEqual([event["sequence"] for event in events],sorted(event["sequence"] for event in events))

 def test_keyset_reader_uses_fixed_high_water_mark(self):
  first=self.m.append_domain_event(event_type="m2_cognition",event_id="m2:1",
      scope="project",payload={"n":1},expected_sequence=0)
  iterator=self.m.iter_domain_events(event_type="m2_cognition",scope="project",page_size=1)
  self.assertEqual(next(iterator)["event_id"],"m2:1")
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:2",
      scope="project",payload={"n":2},expected_sequence=first["sequence"])
  self.assertEqual(list(iterator),[])

 def test_keyset_reader_verifies_each_page_digest(self):
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:1",
      scope="project",payload={"n":1},expected_sequence=0)
  self.m.append_domain_event(event_type="m2_cognition",event_id="m2:2",
      scope="project",payload={"n":2},expected_sequence=1)
  self.m.db.execute("UPDATE memory_events SET payload_json=? WHERE event_id=?",
      ('{"n":999}',"m2:2"))
  iterator=self.m.iter_domain_events(event_type="m2_cognition",scope="project",page_size=1)
  self.assertEqual(next(iterator)["event_id"],"m2:1")
  with self.assertRaises(ZPCMError):
   next(iterator)

 def test_keyset_reader_rejects_invalid_page_size(self):
  for size in (0,-1,True,1.5,4097):
   with self.subTest(size=size),self.assertRaises(ZPCMError):
    list(self.m.iter_domain_events(event_type="m2_cognition",scope="project",page_size=size))

 def test_generic_domain_api_cannot_bypass_e12a6_authorization_consumption(self):
  payload={"kind":"authorization_consumed","body":{"receipt_id":"receipt-1","nonce":"nonce-1","scope":"s"}}
  with self.assertRaises(ZPCMError):
   self.m.append_domain_event(event_type="e12a6_lifecycle",event_id="e12a6:authorization-consumed:receipt-1",
       scope="s",payload=payload,expected_sequence=0)
  with self.assertRaises(ZPCMError):
   self.m.append_domain_event(event_type="untrusted_domain",event_id="bypass:1",
       scope="s",payload=payload,expected_sequence=0)
  self.assertEqual(self.m.db.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0],0)

 def test_event_payload_hard_limit_rejects_before_append(self):
  m=ZPCMMemory(Path(self.tmp.name)/"limited.db",max_event_payload_bytes=64,max_page_bytes=128)
  try:
   with self.assertRaises(ZPCMError):
    m.append_domain_event(event_type="x",event_id="too-big",scope="s",
        payload={"text":"x"*100},expected_sequence=0)
   self.assertEqual(m.db.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0],0)
  finally:m.close()
 def test_forward_and_reverse_pages_obey_aggregate_byte_budget(self):
  m=ZPCMMemory(Path(self.tmp.name)/"paged.db",max_event_payload_bytes=256,max_page_bytes=130)
  try:
   for i in range(3):
    m.append_domain_event(event_type="x",event_id=f"e{i}",scope="s",
        payload={"text":"x"*70,"i":i},expected_sequence=i)
   forward=list(m.iter_domain_events(event_type="x",scope="s",page_size=10))
   reverse=list(m.iter_domain_events_reverse(event_type="x",scope="s",page_size=10))
   self.assertEqual([x["event_id"] for x in forward],["e0","e1","e2"])
   self.assertEqual([x["event_id"] for x in reverse],["e2","e1","e0"])
   payload_sizes=[len(canonical({"text":"x"*70,"i":i}).encode("utf-8")) for i in range(3)]
   self.assertTrue(all(size <= 130 for size in payload_sizes))
   self.assertGreater(payload_sizes[0]+payload_sizes[1],130)
   self.assertEqual(m.get_domain_event(event_type="x",scope="s",event_id="e1")["event_id"],"e1")
  finally:m.close()
 def test_persisted_oversized_event_fails_closed_before_decode(self):
  m=ZPCMMemory(Path(self.tmp.name)/"corrupt.db",max_event_payload_bytes=64,max_page_bytes=128)
  try:
   raw='{"text":"'+"x"*100+'"}'
   m.db.execute("INSERT INTO memory_events(event_id,event_type,scope,payload_json,payload_digest,recorded_at) VALUES(?,?,?,?,?,?)",
       ("legacy-large","x","s",raw,"invalid","now"))
   with self.assertRaises(ZPCMError):
    list(m.iter_domain_events(event_type="x",scope="s"))
   with self.assertRaises(ZPCMError):
    m.get_domain_event(event_type="x",scope="s",event_id="legacy-large")
  finally:m.close()
 def test_invalid_byte_budgets_are_rejected(self):
  for event_limit,page_limit in ((0,1),(True,128),(128,64),(128,True)):
   with self.subTest(event_limit=event_limit,page_limit=page_limit),self.assertRaises(ZPCMError):
    ZPCMMemory(Path(self.tmp.name)/"invalid.db",max_event_payload_bytes=event_limit,max_page_bytes=page_limit)

if __name__=="__main__":unittest.main()
