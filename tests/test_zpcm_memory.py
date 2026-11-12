import ast,tempfile,unittest
from pathlib import Path
from prototype.zpcm_memory import ZPCMError,ZPCMMemory,canonical
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
class Tests(unittest.TestCase):
 def test_zpcm_method_names_are_unique(self):
  source=Path(__file__).parents[1]/"prototype"/"zpcm_memory.py"
  tree=ast.parse(source.read_text(encoding="utf-8"))
  cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=="ZPCMMemory")
  names=[node.name for node in cls.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
  self.assertEqual(len(names),len(set(names)), "duplicate ZPCMMemory method definitions shadow earlier implementations")

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

 def test_e12a6_lifecycle_projection_indexes_candidate_evidence_and_actions(self):
  events=[
   {"event_id":"candidate:rule@1","payload":{"kind":"candidate_registered","body":{"candidate":{"candidate_id":"rule","version":1}}}},
   {"event_id":"evidence:train","payload":{"kind":"evidence_registered","body":{"evidence":{"evidence_id":"train"}}}},
   {"event_id":"action:propose","payload":{"kind":"action_applied","body":{"action":{"action_id":"propose","candidate_id":"rule","candidate_version":1}}}},
  ]
  self.m.append_lifecycle_events(events=events,scope="scope-a",expected_sequence=0)
  candidate=self.m.get_lifecycle_projection_event(
      scope="scope-a",kind="candidate_registered",entity_id="rule",entity_version=1)
  evidence=self.m.get_lifecycle_projection_event(
      scope="scope-a",kind="evidence_registered",entity_id="train")
  action=self.m.get_lifecycle_projection_event(
      scope="scope-a",kind="action_applied",entity_id="propose")
  self.assertEqual(candidate["event_id"],"candidate:rule@1")
  self.assertEqual(evidence["event_id"],"evidence:train")
  self.assertEqual(action["event_id"],"action:propose")
  metadata=list(self.m.iter_lifecycle_projection(scope="scope-a",page_size=2))
  self.assertEqual(len(metadata),3)
  self.assertEqual(metadata[-1]["kind"],"action_applied")
  plan=self.m.db.execute(
      "EXPLAIN QUERY PLAN SELECT event_id FROM e12a6_lifecycle_event_projection "
      "WHERE scope=? AND kind=? AND entity_id=? AND entity_version=? ORDER BY seq DESC LIMIT 1",
      ("scope-a","candidate_registered","rule",1),
  ).fetchall()
  self.assertIn("e12a6_lifecycle_entity_lookup"," ".join(row["detail"] for row in plan))

 def test_lifecycle_projection_backfills_existing_authoritative_events(self):
  self.m._append("candidate:legacy@1","e12a6_lifecycle","scope-a",{
      "kind":"candidate_registered","body":{"candidate":{"candidate_id":"legacy","version":1}}})
  self.m.db.execute("DELETE FROM e12a6_lifecycle_event_projection")
  self.m.close()
  self.m=ZPCMMemory(self.path)
  found=self.m.get_lifecycle_projection_event(
      scope="scope-a",kind="candidate_registered",entity_id="legacy",entity_version=1)
  self.assertEqual(found["event_id"],"candidate:legacy@1")

 def test_typed_projection_backfill_runs_only_when_schema_is_extended(self):
  self.m._append("candidate:legacy@1","e12a6_lifecycle","scope-a",{
   "kind":"candidate_registered","body":{"candidate":{"candidate_id":"legacy","version":1}}})
  self.m.close()
  self.m=ZPCMMemory(self.path)
  found=self.m.db.execute(
   "SELECT candidate_id,candidate_version FROM e12a6_lifecycle_event_projection WHERE event_id=?",
   ("candidate:legacy@1",)).fetchone()
  self.assertEqual(tuple(found),("legacy",1))
  self.m.db.execute("""
   CREATE TRIGGER reject_unnecessary_projection_rewrite
   BEFORE UPDATE ON e12a6_lifecycle_event_projection
   BEGIN SELECT RAISE(ABORT,'unexpected full projection backfill'); END
  """)
  self.m.close()
  self.m=ZPCMMemory(self.path)
  found=self.m.db.execute(
   "SELECT candidate_id,candidate_version FROM e12a6_lifecycle_event_projection WHERE event_id=?",
   ("candidate:legacy@1",)).fetchone()
  self.assertEqual(tuple(found),("legacy",1))

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
 def test_lifecycle_iterator_is_incremental_and_verifies_digest(self):
  for i in range(5):
   self.m.append_lifecycle_event(event_id=f"life:{i}",scope="s",
       payload={"kind":"state_transition","value":i},expected_sequence=i)
  events=self.m.iter_lifecycle_events(scope="s",page_size=2)
  first=next(events)
  self.assertEqual(first["event_id"],"life:0")
  self.assertEqual(next(events)["event_id"],"life:1")
  self.assertEqual([x["event_id"] for x in events],["life:2","life:3","life:4"])

 def test_lifecycle_iterator_enforces_aggregate_page_byte_budget(self):
  m=ZPCMMemory(Path(self.tmp.name)/"lifecycle-budget.db",
      max_event_payload_bytes=128,max_page_bytes=130)
  try:
   for i in range(4):
    m.append_lifecycle_event(event_id=f"life:{i}",scope="s",
        payload={"kind":"state_transition","value":"x"*20},expected_sequence=i)
   events=list(m.iter_lifecycle_events(scope="s",page_size=10))
   self.assertEqual([x["event_id"] for x in events],
       ["life:0","life:1","life:2","life:3"])
  finally:
   m.close()

 def test_lifecycle_iterator_rejects_corrupt_payload_digest(self):
  self.m.append_lifecycle_event(event_id="life:tamper",scope="s",
      payload={"kind":"state_transition"},expected_sequence=0)
  self.m.db.execute("UPDATE memory_events SET payload_json=? WHERE event_id=?",
      ('{"kind":"tampered"}',"life:tamper"))
  with self.assertRaises(ZPCMError):
   list(self.m.iter_lifecycle_events(scope="s"))

 def test_lifecycle_list_api_remains_compatible(self):
  self.m.append_lifecycle_event(event_id="life:compat",scope="s",
      payload={"kind":"state_transition"},expected_sequence=0)
  events=self.m.replay_lifecycle_events(scope="s")
  self.assertIsInstance(events,list)
  self.assertEqual(events[0]["event_id"],"life:compat")

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
  m=ZPCMMemory(Path(self.tmp.name)/"paged.db",max_event_payload_bytes=128,max_page_bytes=130)
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

 def test_authorization_projection_checkpoint_advances_with_lifecycle_append(self):
  first=self.m.append_lifecycle_event(event_id="lifecycle:1",scope="s",
      payload={"kind":"state_transition","value":1},expected_sequence=0)
  checkpoint=self.m.db.execute(
      "SELECT high_water_seq,schema_version FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(checkpoint["high_water_seq"],first["sequence"])
  self.assertEqual(checkpoint["schema_version"],self.m.AUTHORIZATION_PROJECTION_VERSION)
 def test_authorization_projection_incrementally_catches_legacy_append(self):
  self.m.append_lifecycle_event(event_id="lifecycle:1",scope="s",
      payload={"kind":"state_transition","value":1},expected_sequence=0)
  legacy_seq,_=self.m._append("legacy:lifecycle:2","e12a6_lifecycle","s",
      {"kind":"state_transition","value":2})
  self.m.close()
  self.m=ZPCMMemory(self.path)
  checkpoint=self.m.db.execute(
      "SELECT high_water_seq FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(checkpoint["high_water_seq"],legacy_seq)
 def test_checkpoint_does_not_jump_over_unseen_legacy_lifecycle_events(self):
  self.m.append_lifecycle_event(event_id="lifecycle:1",scope="s",
      payload={"kind":"state_transition","value":1},expected_sequence=0)
  legacy_seq,_=self.m._append("legacy:lifecycle:2","e12a6_lifecycle","s",
      {"kind":"state_transition","value":2})
  self.m.append_lifecycle_event(event_id="lifecycle:3",scope="s",
      payload={"kind":"state_transition","value":3},expected_sequence=legacy_seq)
  checkpoint=self.m.db.execute(
      "SELECT high_water_seq FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(checkpoint["high_water_seq"],1)
  self.m.close()
  self.m=ZPCMMemory(self.path)
  checkpoint=self.m.db.execute(
      "SELECT high_water_seq FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(checkpoint["high_water_seq"],3)
 def test_lifecycle_batch_advances_checkpoint_atomically(self):
  receipts=self.m.append_lifecycle_events(scope="s",expected_sequence=0,events=[
      {"event_id":"lifecycle:batch:1","payload":{"kind":"state_transition","value":1}},
      {"event_id":"lifecycle:batch:2","payload":{"kind":"state_transition","value":2}},
  ])
  checkpoint=self.m.db.execute(
      "SELECT high_water_seq FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(checkpoint["high_water_seq"],max(x["sequence"] for x in receipts))
 def test_corrupt_authorization_checkpoint_triggers_streaming_rebuild(self):
  body={"receipt_id":"receipt-rebuild","nonce":"nonce-rebuild","scope":"s"}
  payload={"kind":"authorization_consumed","body":body}
  event_id="e12a6:authorization-consumed:receipt-rebuild"
  self.m._append(event_id,"e12a6_lifecycle","s",payload)
  self.m.close()
  self.m=ZPCMMemory(self.path)
  row=self.m.db.execute(
      "SELECT receipt_id,nonce,event_id,scope FROM e12a6_authorization_consumptions"
  ).fetchone()
  self.assertEqual(tuple(row),(body["receipt_id"],body["nonce"],event_id,"s"))
  self.m.db.execute(
      "UPDATE e12a6_authorization_projection_checkpoint SET checkpoint_digest='corrupt' WHERE singleton=1"
  )
  self.m.close()
  self.m=ZPCMMemory(self.path)
  count=self.m.db.execute("SELECT COUNT(*) FROM e12a6_authorization_consumptions").fetchone()[0]
  self.assertEqual(count,1)
 def test_projection_row_mutation_invalidates_checkpoint_and_rebuilds(self):
  body={"receipt_id":"receipt-projection","nonce":"nonce-projection","scope":"s"}
  payload={"kind":"authorization_consumed","body":body}
  event_id="e12a6:authorization-consumed:receipt-projection"
  self.m._append(event_id,"e12a6_lifecycle","s",payload)
  self.m.close()
  self.m=ZPCMMemory(self.path)
  self.assertEqual(self.m.db.execute(
      "SELECT COUNT(*) FROM e12a6_authorization_consumptions"
  ).fetchone()[0],1)
  self.m.db.execute(
      "DELETE FROM e12a6_authorization_consumptions WHERE receipt_id=?",
      (body["receipt_id"],),
  )
  self.m.close()
  self.m=ZPCMMemory(self.path)
  row=self.m.db.execute(
      "SELECT receipt_id,nonce,event_id,scope FROM e12a6_authorization_consumptions"
  ).fetchone()
  self.assertEqual(tuple(row),(body["receipt_id"],body["nonce"],event_id,"s"))

 def test_explicit_authorization_projection_rebuild_revalidates_full_history(self):
  self.m.append_lifecycle_event(event_id="lifecycle:tamper",scope="s",
      payload={"kind":"state_transition","value":1},expected_sequence=0)
  self.m.db.execute(
      "UPDATE memory_events SET payload_json=? WHERE event_id=?",
      ('{"kind":"tampered"}',"lifecycle:tamper")
  )
  with self.assertRaises(ZPCMError):
   self.m.rebuild_authorization_consumption_index()
 def test_lifecycle_append_and_checkpoint_update_are_atomic(self):
  before=self.m.db.execute(
      "SELECT high_water_seq,checkpoint_digest FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  def fail_checkpoint(_sequence, *, expected_previous_high_water=None):
   raise RuntimeError("injected checkpoint failure")
  self.m._advance_authorization_projection_checkpoint=fail_checkpoint
  with self.assertRaises(RuntimeError):
   self.m.append_lifecycle_event(event_id="lifecycle:atomic",scope="s",
       payload={"kind":"state_transition"},expected_sequence=0)
  self.assertIsNone(self.m.db.execute(
      "SELECT 1 FROM memory_events WHERE event_id='lifecycle:atomic'"
  ).fetchone())
  after=self.m.db.execute(
      "SELECT high_water_seq,checkpoint_digest FROM e12a6_authorization_projection_checkpoint WHERE singleton=1"
  ).fetchone()
  self.assertEqual(tuple(after),tuple(before))

 def test_candidate_history_projection_indexes_action_ownership_and_streams_verified_events(self):
  self.m.append_lifecycle_events(scope="scope-a",expected_sequence=0,events=[
   {"event_id":"candidate:rule@1","payload":{"kind":"candidate_registered","body":{"candidate":{"candidate_id":"rule","version":1}}}},
   {"event_id":"action:propose","payload":{"kind":"action_applied","body":{"action":{"action_id":"propose","candidate_id":"rule","candidate_version":1}}}},
   {"event_id":"action:confirm","payload":{"kind":"action_applied","body":{"action":{"action_id":"confirm","candidate_id":"rule","candidate_version":1}}}},
   {"event_id":"candidate:rule@2","payload":{"kind":"revision_created","body":{"arguments":{"candidate_id":"rule","version":1},"candidate":{"candidate_id":"rule","version":2}}}},
  ])
  rows=self.m.db.execute(
   "SELECT kind,entity_id,candidate_id,candidate_version,action_id FROM e12a6_lifecycle_event_projection WHERE scope=? ORDER BY seq",
   ("scope-a",),
  ).fetchall()
  self.assertEqual([(r["kind"],r["candidate_id"],r["candidate_version"]) for r in rows],[
   ("candidate_registered","rule",1),("action_applied","rule",1),
   ("action_applied","rule",1),("revision_created","rule",2)])
  self.assertEqual([r["action_id"] for r in rows[1:3]],["propose","confirm"])
  history=list(self.m.iter_lifecycle_candidate_history(
   scope="scope-a",candidate_id="rule",candidate_version=1,page_size=1))
  self.assertEqual([e["event_id"] for e in history],[
   "candidate:rule@1","action:propose","action:confirm"])
  revision=list(self.m.iter_lifecycle_candidate_history(
   scope="scope-a",candidate_id="rule",candidate_version=2))
  self.assertEqual([e["event_id"] for e in revision],["candidate:rule@2"])
  plan=self.m.db.execute(
   "EXPLAIN QUERY PLAN SELECT event_id FROM e12a6_lifecycle_event_projection "
   "WHERE scope=? AND candidate_id=? AND candidate_version=? AND seq>? ORDER BY seq LIMIT ?",
   ("scope-a","rule",1,0,10),
  ).fetchall()
  self.assertIn("e12a6_lifecycle_candidate_version_history",
   " ".join(row["detail"] for row in plan))

 def test_candidate_history_projection_backfills_typed_ownership(self):
  self.m._append("legacy:action","e12a6_lifecycle","scope-a",{
   "kind":"action_applied","body":{"action":{"action_id":"legacy-action",
    "candidate_id":"legacy-rule","candidate_version":3}}})
  self.m.close()
  self.m=ZPCMMemory(self.path)
  row=self.m.db.execute(
   "SELECT candidate_id,candidate_version,action_id FROM e12a6_lifecycle_event_projection "
   "WHERE event_id='legacy:action'"
  ).fetchone()
  self.assertEqual(tuple(row),("legacy-rule",3,"legacy-action"))


 def test_e12a6_current_state_projection_tracks_candidate_evidence_and_actions(self):
  candidate={"candidate_id":"rule-a","version":1,"state":"OBSERVED","canonical_expression":"x > y"}
  evidence={"evidence_id":"ev-a","episode_id":"ep-a","split_role":"TRAIN"}
  action={"action_id":"act-a","candidate_id":"rule-a","candidate_version":1,
          "from_state":"OBSERVED","to_state":"PROPOSED"}
  receipts=self.m.append_lifecycle_events(scope="scope-a",expected_sequence=0,events=[
   {"event_id":"candidate:rule-a@1","payload":{"schema_version":"e12a6-lifecycle-event-v1",
    "kind":"candidate_registered","body":{"candidate":candidate}}},
   {"event_id":"evidence:ev-a","payload":{"schema_version":"e12a6-lifecycle-event-v1",
    "kind":"evidence_registered","body":{"evidence":evidence}}},
   {"event_id":"action:act-a","payload":{"schema_version":"e12a6-lifecycle-event-v1",
    "kind":"action_applied","body":{"action":action}}},
  ])
  projected=self.m.get_lifecycle_candidate_projection(
      scope="scope-a",candidate_id="rule-a",candidate_version=1)
  self.assertEqual(projected["candidate"]["state"],"PROPOSED")
  self.assertEqual(projected["source_seq"],receipts[-1]["sequence"])
  self.assertEqual(self.m.get_lifecycle_evidence_projection(
      scope="scope-a",evidence_id="ev-a")["evidence"],evidence)
  self.assertEqual(self.m.get_lifecycle_action_projection(
      scope="scope-a",action_id="act-a")["action"],action)
  self.assertEqual(self.m.lifecycle_state_projection_counts(scope="scope-a"),
      {"candidates":1,"evidence":1,"actions":1})
  self.assertIsNone(self.m.get_lifecycle_candidate_projection(
      scope="other",candidate_id="rule-a",candidate_version=1))

 def test_e12a6_current_state_projection_rebuilds_after_projection_rows_are_lost(self):
  candidate={"candidate_id":"rule-rebuild","version":1,"state":"OBSERVED"}
  action={"action_id":"act-rebuild","candidate_id":"rule-rebuild","candidate_version":1,
          "from_state":"OBSERVED","to_state":"PROPOSED"}
  self.m.append_lifecycle_events(scope="scope-a",expected_sequence=0,events=[
   {"event_id":"candidate:rebuild@1","payload":{"kind":"candidate_registered","body":{"candidate":candidate}}},
   {"event_id":"action:rebuild","payload":{"kind":"action_applied","body":{"action":action}}},
  ])
  self.m.db.execute("DELETE FROM e12a6_candidate_state_projection")
  self.m.db.execute("DELETE FROM e12a6_action_state_projection")
  self.m.close()
  self.m=ZPCMMemory(self.path)
  row=self.m.get_lifecycle_candidate_projection(
      scope="scope-a",candidate_id="rule-rebuild",candidate_version=1)
  self.assertEqual(row["candidate"]["state"],"PROPOSED")
  self.assertEqual(self.m.lifecycle_state_projection_counts(scope="scope-a"),
      {"candidates":1,"evidence":0,"actions":1})

 def test_e12a6_current_state_projection_rolls_back_with_event_append(self):
  candidate={"candidate_id":"rule-rollback","version":1,"state":"OBSERVED"}
  original=self.m._advance_authorization_projection_checkpoint
  def fail(_sequence,*,expected_previous_high_water=None):
   raise RuntimeError("injected checkpoint failure")
  self.m._advance_authorization_projection_checkpoint=fail
  with self.assertRaises(RuntimeError):
   self.m.append_lifecycle_event(event_id="candidate:rollback@1",scope="scope-a",
      payload={"kind":"candidate_registered","body":{"candidate":candidate}},
      expected_sequence=0)
  self.m._advance_authorization_projection_checkpoint=original
  self.assertIsNone(self.m.get_lifecycle_candidate_projection(
      scope="scope-a",candidate_id="rule-rollback",candidate_version=1))
  self.assertEqual(self.m.db.execute(
      "SELECT COUNT(*) FROM memory_events WHERE event_id='candidate:rollback@1'").fetchone()[0],0)


if __name__=="__main__":unittest.main()
