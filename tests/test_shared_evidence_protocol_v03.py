import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import MissingReference, ProtocolError, SQLiteEvidenceStore, canonical_json, digest_payload
from prototype.shared_evidence_protocol_v03 import (
    BatchConflict, ProjectionRecoveryRequired, SQLiteEvidenceStoreV03,
    candidate_definition_payload, evidence_definition_payload,
)
from prototype.e12a6_lifecycle_contract import Action, ActionType, Candidate, CandidateState, Evidence, LifecycleLedger, SplitRole



class SharedEvidenceProtocolV03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "v03.sqlite3"
        self.store = SQLiteEvidenceStoreV03(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def observation(self, observation_id="obs-1"):
        return {
            "event_id": f"event-{observation_id}",
            "event_type": "observation",
            "payload": {"observation_id": observation_id},
        }

    def ingest(self, *, evidence_id="train-1", role="train", observation_id="obs-1"):
        return {
            "event_id": f"ingest-event-{evidence_id}",
            "event_type": "evidence_ingest",
            "idempotency_key": f"ingest-key-{evidence_id}",
            "payload": {
                "evidence_id": evidence_id,
                "observation_ref": f"event-{observation_id}",
                "split_role": role,
                "outcome_ref": f"sha256:{evidence_id}",
                "source_provenance": {"source_kind": "dataset", "source_id": "fixture-1"},
                "learner_track": "e12",
            },
        }

    def test_train_ingest_supports_structure_without_fake_prediction_reveal(self):
        receipts = self.store.append_events(
            episode_id="ep", idempotency_key="batch-1",
            events=[
                self.observation(),
                self.ingest(),
                {
                    "event_id": "structure-1", "event_type": "structure_version",
                    "idempotency_key": "structure-key",
                    "payload": {
                        "structure_id": "primitive-set", "version_id": "v1",
                        "kind": "primitive", "definition": {"predicate": "x>y"},
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "ingested", "id": "train-1"}],
                    },
                },
            ],
        )
        self.assertEqual([r.sequence_no for r in receipts], [1, 2, 3])
        events = self.store.replay_episode("ep")
        self.assertEqual([e["event_type"] for e in events], ["observation", "evidence_ingest", "structure_version"])

    def test_ingest_rejects_locked_test_and_gate_final(self):
        for role in ("locked_test", "post_deploy", "gate_final", "gate_dev"):
            with self.subTest(role=role):
                with self.assertRaises(ProtocolError):
                    self.store.append_event(
                        episode_id=f"ep-{role}", event_id="ingest", event_type="evidence_ingest",
                        idempotency_key="ingest",
                        payload=self.ingest(role=role)["payload"],
                    )

    def test_forward_reference_rejected_and_whole_batch_rolled_back(self):
        with self.assertRaises(MissingReference):
            self.store.append_events(
                episode_id="ep", idempotency_key="bad-batch",
                events=[
                    self.observation(),
                    {
                        "event_id": "structure-first", "event_type": "structure_version",
                        "payload": {
                            "structure_id": "s", "version_id": "v1", "kind": "rule",
                            "definition": {}, "parent_version_ids": [],
                            "support_evidence_ids": [{"kind": "ingested", "id": "late"}],
                        },
                    },
                    self.ingest(evidence_id="late"),
                ],
            )
        self.assertEqual(self.store.replay_episode("ep"), [])
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM idempotency WHERE episode_id='ep'").fetchone()[0],
            0,
        )

    def test_batch_retry_returns_same_receipts_and_conflicting_retry_fails(self):
        events = [self.observation(), self.ingest()]
        first = self.store.append_events(episode_id="ep", events=events, idempotency_key="batch")
        retry = self.store.append_events(episode_id="ep", events=events, idempotency_key="batch")
        self.assertEqual([r.sequence_no for r in first], [1, 2])
        self.assertTrue(all(r.replayed for r in retry))
        changed = list(reversed(events))
        with self.assertRaises(BatchConflict):
            self.store.append_events(episode_id="ep", events=changed, idempotency_key="batch")
        self.assertEqual(len(self.store.replay_episode("ep")), 2)

    def test_lifecycle_action_uses_e12_transition_contract(self):
        self.store.append_event(
            episode_id="ep", event_id="candidate-v1", event_type="structure_version",
            idempotency_key="candidate-v1",
            payload={
                "structure_id": "candidate", "version_id": "candidate@1",
                "kind": "candidate", "definition": {"expression": "x>y"},
                "parent_version_ids": [], "support_evidence_ids": [],
            },
        )
        action = {
            "action_id": "propose-1", "action_type": "propose",
            "candidate_id": "candidate", "candidate_version": 1,
            "from_state": "observed", "to_state": "proposed",
            "evidence_refs": [], "cost": 0.1, "note": "proposal",
            "candidate_lineage_refs": [], "learner_track": "e12",
        }
        receipt = self.store.append_event(
            episode_id="ep", event_id="action-1", event_type="lifecycle_action",
            idempotency_key="action-1", payload=action,
        )
        self.assertEqual(receipt.sequence_no, 2)
        illegal = dict(action, action_id="illegal", action_type="gate_validate",
                       from_state="proposed", to_state="gate_validated")
        with self.assertRaises(ProtocolError):
            self.store.append_event(
                episode_id="ep", event_id="action-illegal", event_type="lifecycle_action",
                idempotency_key="action-illegal", payload=illegal,
            )

    def test_restart_replay_keeps_v03_events(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="batch",
            events=[self.observation(), self.ingest()],
        )
        before = [(x["event_id"], x["payload_digest"]) for x in self.store.replay_episode("ep")]
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        after = [(x["event_id"], x["payload_digest"]) for x in self.store.replay_episode("ep")]
        self.assertEqual(before, after)


    def test_non_transition_e12_action_can_be_recorded_without_candidate_state(self):
        receipt = self.store.append_event(
            episode_id="ep", event_id="measure-1", event_type="lifecycle_action",
            idempotency_key="measure-1",
            payload={
                "action_id": "measure-1", "action_type": "measure",
                "candidate_id": None, "candidate_version": None,
                "from_state": None, "to_state": None,
                "evidence_refs": [], "cost": 0.5, "note": "active measurement",
                "candidate_lineage_refs": [], "learner_track": "e12",
            },
        )
        self.assertEqual(receipt.sequence_no, 1)



    def test_single_event_retry_preserves_v02_idempotency_behavior(self):
        first = self.store.append_event(
            episode_id="ep", event_id="first-event", event_type="observation",
            idempotency_key="same-key", payload={"observation_id": "obs-1"},
        )
        retry = self.store.append_event(
            episode_id="ep", event_id="different-event-id", event_type="observation",
            idempotency_key="same-key", payload={"observation_id": "obs-1"},
        )
        self.assertTrue(retry.replayed)
        self.assertEqual((retry.event_id, retry.sequence_no), (first.event_id, first.sequence_no))



    def test_lifecycle_action_rejects_unknown_candidate_version(self):
        action = {
            "action_id": "phantom-propose", "action_type": "propose",
            "candidate_id": "missing", "candidate_version": 1,
            "from_state": "observed", "to_state": "proposed",
            "evidence_refs": [], "cost": 0.1, "note": "phantom",
            "candidate_lineage_refs": [], "learner_track": "e12",
        }
        with self.assertRaises(MissingReference):
            self.store.append_event(
                episode_id="ep", event_id="phantom-action", event_type="lifecycle_action",
                idempotency_key="phantom-action", payload=action,
            )

    def test_lifecycle_action_rejects_non_finite_cost(self):
        payload = {
            "action_id": "measure-nan", "action_type": "measure",
            "candidate_id": None, "candidate_version": None,
            "from_state": None, "to_state": None,
            "evidence_refs": [], "cost": float("nan"), "note": "invalid cost",
            "candidate_lineage_refs": [], "learner_track": "e12",
        }
        with self.assertRaises(ValueError):
            self.store.append_event(
                episode_id="ep", event_id="measure-nan", event_type="lifecycle_action",
                idempotency_key="measure-nan", payload=payload,
            )



    def test_revision_batch_is_atomic_and_follows_e12_create_revision_order(self):
        # Parent candidate starts at OBSERVED.
        self.store.append_event(
            episode_id="ep", event_id="candidate-v1", event_type="structure_version",
            idempotency_key="candidate-v1",
            payload={
                "structure_id": "candidate", "version_id": "candidate@1",
                "kind": "candidate", "definition": {"expression": "x>y"},
                "parent_version_ids": [], "support_evidence_ids": [],
            },
        )

        # Visible TRAIN evidence is ingested without fabricating a prediction/reveal.
        self.store.append_events(
            episode_id="ep", idempotency_key="train-evidence",
            events=[self.observation("obs-train"), self.ingest(
                evidence_id="train-1", role="train", observation_id="obs-train"
            )],
        )

        def reveal(evidence_id, observation_id, prediction_id, role):
            self.store.append_events(
                episode_id="ep", idempotency_key=f"reveal-{evidence_id}",
                events=[
                    self.observation(observation_id),
                    {
                        "event_id": f"commit-{evidence_id}", "event_type": "prediction_commit",
                        "payload": {
                            "prediction_id": prediction_id, "observation_id": observation_id,
                            "model_version": "test-model", "learner_track": "e12",
                            "decision_status": "PREDICT",
                        },
                    },
                    {
                        "event_id": f"reveal-{evidence_id}", "event_type": "evidence_reveal",
                        "payload": {
                            "prediction_id": prediction_id, "learner_track": "e12",
                            "target_or_feedback": {"result": "observed"},
                            "split_role": role,
                        },
                    },
                ],
            )

        reveal("gate", "obs-gate", "pred-gate", "gate_final")
        reveal("locked", "obs-locked", "pred-locked", "locked_test")

        def action(action_id, action_type, from_state, to_state, evidence_refs=(), lineage=()):
            self.store.append_event(
                episode_id="ep", event_id=f"event-{action_id}", event_type="lifecycle_action",
                idempotency_key=f"key-{action_id}",
                payload={
                    "action_id": action_id, "action_type": action_type,
                    "candidate_id": "candidate", "candidate_version": 1,
                    "from_state": from_state, "to_state": to_state,
                    "evidence_refs": list(evidence_refs), "cost": 0.1, "note": action_id,
                    "candidate_lineage_refs": list(lineage), "learner_track": "e12",
                },
            )

        action("propose", "propose", "observed", "proposed")
        action("discriminate", "request_discrimination", "proposed", "discrimination_pending")
        action("train", "train_support", "discrimination_pending", "train_supported",
               [{"kind": "ingested", "id": "train-1"}])
        action("gate", "gate_validate", "train_supported", "gate_validated",
               [{"kind": "revealed", "id": "reveal-gate"}])
        action("challenge", "challenge", "gate_validated", "challenged",
               [{"kind": "revealed", "id": "reveal-locked"}])

        parent_revise = {
            "event_id": "revise-parent", "event_type": "lifecycle_action",
            "payload": {
                "action_id": "revise-parent", "action_type": "revise",
                "candidate_id": "candidate", "candidate_version": 1,
                "from_state": "challenged", "to_state": "revised",
                "evidence_refs": [{"kind": "revealed", "id": "reveal-locked"}],
                "cost": 0.2, "note": "revise after locked-test counterexample",
                "candidate_lineage_refs": [], "learner_track": "e12",
            },
        }
        child_version = {
            "event_id": "candidate-v2", "event_type": "structure_version",
            "payload": {
                "structure_id": "candidate", "version_id": "candidate@2",
                "kind": "candidate", "definition": {"expression": "x>y and z"},
                "parent_version_ids": ["candidate@1"],
                "support_evidence_ids": [{"kind": "ingested", "id": "train-1"}],
            },
        }
        child_register = {
            "event_id": "register-child", "event_type": "lifecycle_action",
            "payload": {
                "action_id": "register-child", "action_type": "register_revision",
                "candidate_id": "candidate", "candidate_version": 2,
                "from_state": "observed", "to_state": "revalidation_pending",
                "evidence_refs": [{"kind": "revealed", "id": "reveal-locked"}],
                "cost": 0.0, "note": "register revision child",
                "candidate_lineage_refs": ["candidate@1"], "learner_track": "e12",
            },
        }
        revision = {
            "event_id": "revision-record", "event_type": "revision",
            "payload": {
                "revision_id": "revision-1", "operation": "revise",
                "trigger_evidence_ids": ["reveal-locked"],
                "before_version_ids": ["candidate@1"],
                "after_version_ids": ["candidate@2"],
            },
        }

        # Invalid final event must roll back all three preceding revision events.
        bad_revision = {
            **revision,
            "payload": {**revision["payload"], "trigger_evidence_ids": ["missing-reveal"]},
        }
        with self.assertRaises(MissingReference):
            self.store.append_events(
                episode_id="ep", idempotency_key="revision-bad",
                events=[parent_revise, child_version, child_register, bad_revision],
            )
        self.assertIsNone(self.store._event_by_payload_id("ep", "structure_version", "version_id", "candidate@2"))
        latest = self.store._db.execute(
            "SELECT payload_json FROM events WHERE episode_id='ep' AND event_type='lifecycle_action' "
            "AND json_extract(payload_json, '$.candidate_id')='candidate' "
            "AND json_extract(payload_json, '$.candidate_version')=1 ORDER BY sequence_no DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(__import__("json").loads(latest["payload_json"])["to_state"], "challenged")

        receipts = self.store.append_events(
            episode_id="ep", idempotency_key="revision-good",
            events=[parent_revise, child_version, child_register, revision],
        )
        self.assertEqual(len(receipts), 4)
        self.assertEqual([r.sequence_no for r in receipts], list(range(receipts[0].sequence_no, receipts[0].sequence_no + 4)))
        self.assertEqual(
            self.store._db.execute(
                "SELECT json_extract(payload_json, '$.to_state') FROM events "
                "WHERE episode_id='ep' AND event_type='lifecycle_action' "
                "AND json_extract(payload_json, '$.candidate_version')=1 "
                "ORDER BY sequence_no DESC LIMIT 1"
            ).fetchone()[0],
            "revised",
        )
        self.assertEqual(
            self.store._db.execute(
                "SELECT json_extract(payload_json, '$.to_state') FROM events "
                "WHERE episode_id='ep' AND event_type='lifecycle_action' "
                "AND json_extract(payload_json, '$.candidate_version')=2 "
                "ORDER BY sequence_no DESC LIMIT 1"
            ).fetchone()[0],
            "revalidation_pending",
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(projection.candidates["candidate@1"]["state"], "revised")
        self.assertEqual(projection.candidates["candidate@2"]["state"], "revalidation_pending")
        self.assertEqual(projection.revisions["revision-1"]["before_version_ids"], ["candidate@1"])
        self.assertEqual(projection.revisions["revision-1"]["after_version_ids"], ["candidate@2"])
        before_digest = projection.digest
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        after = self.store.replay_projection("ep")
        self.assertEqual(after.digest, before_digest)




    def test_projection_replays_ingested_support_and_is_deterministic(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="base",
            events=[
                self.observation(),
                self.ingest(),
                {
                    "event_id": "structure-1", "event_type": "structure_version",
                    "payload": {
                        "structure_id": "primitive-set", "version_id": "v1",
                        "kind": "primitive", "definition": {"predicate": "x>y"},
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "ingested", "id": "train-1"}],
                    },
                },
            ],
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(projection.last_sequence, 3)
        self.assertEqual(projection.evidence["ingested:train-1"]["split_role"], "train")
        self.assertEqual(projection.structures["v1"]["support_evidence_ids"], ["train-1"])
        digest = projection.digest
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        self.assertEqual(self.store.replay_projection("ep").digest, digest)

    def test_projection_detects_durable_event_digest_tampering(self):
        self.store.append_event(
            episode_id="ep", event_id="obs", event_type="observation",
            idempotency_key="obs", payload={"observation_id": "obs-1"},
        )
        self.store._db.execute(
            "UPDATE events SET payload_json=? WHERE episode_id='ep' AND event_id='obs'",
            ('{"observation_id":"tampered"}',),
        )
        with self.assertRaises(ProtocolError):
            self.store.replay_projection("ep")

    def test_projection_replays_v02_causal_evidence(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="causal",
            events=[
                self.observation("obs-v02"),
                {
                    "event_id": "commit-v02", "event_type": "prediction_commit",
                    "payload": {
                        "prediction_id": "pred-v02", "observation_id": "obs-v02",
                        "model_version": "m1", "learner_track": "legacy",
                        "decision_status": "PREDICT",
                    },
                },
                {
                    "event_id": "reveal-v02", "event_type": "evidence_reveal",
                    "payload": {
                        "prediction_id": "pred-v02", "learner_track": "legacy",
                        "target_or_feedback": {"label": 1}, "split_role": "locked_test",
                    },
                },
            ],
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(projection.predictions["pred-v02"]["observation_id"], "obs-v02")
        self.assertEqual(projection.evidence["revealed:reveal-v02"]["split_role"], "locked_test")



    def test_lifecycle_candidate_identity_must_match_structure_version(self):
        self.store.append_event(
            episode_id="ep", event_id="candidate-v1", event_type="structure_version",
            idempotency_key="candidate-v1",
            payload={
                "structure_id": "candidate", "version_id": "candidate@1",
                "kind": "candidate", "definition": {}, "parent_version_ids": [],
                "support_evidence_ids": [],
            },
        )
        with self.assertRaises(ProtocolError):
            self.store.append_event(
                episode_id="ep", event_id="candidate-action", event_type="lifecycle_action",
                idempotency_key="candidate-action",
                payload={
                    "action_id": "candidate-action", "action_type": "propose",
                    "candidate_id": "wrong-candidate", "candidate_version": 1,
                    "from_state": "observed", "to_state": "proposed",
                    "evidence_refs": [], "cost": 0.1, "note": "identity mismatch",
                    "candidate_lineage_refs": [], "learner_track": "e12",
                },
            )

    def test_lifecycle_lineage_must_match_candidate_parent_versions(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="candidate-versions",
            events=[
                {
                    "event_id": "parent", "event_type": "structure_version",
                    "payload": {
                        "structure_id": "candidate", "version_id": "candidate@1",
                        "kind": "candidate", "definition": {}, "parent_version_ids": [],
                        "support_evidence_ids": [],
                    },
                },
                {
                    "event_id": "child", "event_type": "structure_version",
                    "payload": {
                        "structure_id": "candidate", "version_id": "candidate@2",
                        "kind": "candidate", "definition": {}, "parent_version_ids": ["candidate@1"],
                        "support_evidence_ids": [],
                    },
                },
            ],
        )
        with self.assertRaises(ProtocolError):
            self.store.append_event(
                episode_id="ep", event_id="register-child", event_type="lifecycle_action",
                idempotency_key="register-child",
                payload={
                    "action_id": "register-child", "action_type": "register_revision",
                    "candidate_id": "candidate", "candidate_version": 2,
                    "from_state": "observed", "to_state": "revalidation_pending",
                    "evidence_refs": [], "cost": 0.0, "note": "missing parent lineage",
                    "candidate_lineage_refs": [], "learner_track": "e12",
                },
            )



    def test_projection_preserves_v01_implicit_legacy_track_without_rewriting_event(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="legacy",
            events=[
                self.observation("legacy-observation"),
                {
                    "event_id": "legacy-prediction", "event_type": "prediction_commit",
                    "payload": {
                        "prediction_id": "legacy-pred", "observation_id": "legacy-observation",
                        "model_version": "m0", "learner_track": "legacy",
                        "decision_status": "PREDICT",
                    },
                },
            ],
        )
        row = self.store._db.execute(
            "SELECT sequence_no, payload_json FROM events WHERE episode_id='ep' AND event_id='legacy-prediction'"
        ).fetchone()
        old_payload = __import__("json").loads(row["payload_json"])
        old_payload.pop("learner_track")
        digest = digest_payload({
            "event_type": "prediction_commit", "payload_schema": "prediction_commit@1",
            "payload": old_payload, "actor_role": "runner", "causation_refs": [],
            "integrity_metadata": {},
        })
        self.store._db.execute(
            "UPDATE events SET protocol_version='0.1', payload_json=?, payload_digest=? "
            "WHERE episode_id='ep' AND sequence_no=?",
            (canonical_json(old_payload), digest, row["sequence_no"]),
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(projection.predictions["legacy-pred"]["learner_track"], "legacy")
        stored = self.store._db.execute(
            "SELECT payload_json FROM events WHERE episode_id='ep' AND event_id='legacy-prediction'"
        ).fetchone()[0]
        self.assertNotIn("learner_track", stored)



    def test_append_events_and_project_returns_committed_projection(self):
        receipts, projection = self.store.append_events_and_project(
            episode_id="ep", idempotency_key="append-project",
            events=[self.observation("obs-project")],
        )
        self.assertEqual(receipts[0].sequence_no, 1)
        self.assertEqual(projection.last_sequence, 1)
        self.assertIn("obs-project", projection.observations)

    def test_projection_failure_after_commit_is_explicit_and_recoverable(self):
        original = self.store.replay_projection

        def fail_projection(_episode_id):
            raise RuntimeError("simulated projection failure")

        self.store.replay_projection = fail_projection
        with self.assertRaises(ProjectionRecoveryRequired) as caught:
            self.store.append_events_and_project(
                episode_id="ep", idempotency_key="committed-before-projection",
                events=[self.observation("obs-durable")],
            )
        self.assertEqual(len(caught.exception.committed_receipts), 1)
        self.assertEqual(caught.exception.committed_receipts[0].sequence_no, 1)
        self.store.replay_projection = original
        recovered = self.store.replay_projection("ep")
        self.assertIn("obs-durable", recovered.observations)
        self.assertEqual(recovered.last_sequence, 1)



    def test_typed_candidate_definition_round_trips_to_e12_candidate(self):
        candidate = Candidate(
            candidate_id="relation:greater-than", version=1,
            canonical_expression="x > y", proposer_family="relational",
            supporting_families=("relational", "residual"),
            input_types=("number", "number"), operator="GT",
            conditions=("both_inputs_observed",), uncertainty=0.35,
            complexity=2, proposal_cost=0.15,
        )
        self.store.append_events(
            episode_id="ep", idempotency_key="typed-candidate",
            events=[
                {
                    "event_id": "candidate-v1", "event_type": "structure_version",
                    "payload": {
                        "structure_id": candidate.candidate_id,
                        "version_id": "relation:greater-than@1",
                        "kind": "candidate",
                        "definition": candidate_definition_payload(candidate),
                        "parent_version_ids": [], "support_evidence_ids": [],
                    },
                },
                {
                    "event_id": "candidate-propose", "event_type": "lifecycle_action",
                    "payload": {
                        "action_id": "candidate-propose", "action_type": "propose",
                        "candidate_id": candidate.candidate_id, "candidate_version": 1,
                        "from_state": "observed", "to_state": "proposed",
                        "evidence_refs": [], "cost": 0.1, "note": "propose",
                        "candidate_lineage_refs": [], "learner_track": "e12",
                    },
                },
            ],
        )
        projection = self.store.replay_projection("ep")
        restored = projection.candidate_objects["relation:greater-than@1"]
        self.assertIsInstance(restored, Candidate)
        self.assertEqual(restored.candidate_id, candidate.candidate_id)
        self.assertEqual(restored.canonical_expression, candidate.canonical_expression)
        self.assertEqual(restored.supporting_families, candidate.supporting_families)
        self.assertEqual(restored.input_types, candidate.input_types)
        self.assertEqual(restored.conditions, candidate.conditions)
        self.assertEqual(restored.uncertainty, candidate.uncertainty)
        self.assertEqual(restored.complexity, candidate.complexity)
        self.assertEqual(restored.proposal_cost, candidate.proposal_cost)
        self.assertEqual(restored.state, CandidateState.PROPOSED)

    def test_typed_candidate_definition_rejects_missing_semantic_fields(self):
        with self.assertRaises(ProtocolError):
            self.store.append_event(
                episode_id="ep", event_id="bad-candidate", event_type="structure_version",
                idempotency_key="bad-candidate",
                payload={
                    "structure_id": "candidate", "version_id": "candidate@1",
                    "kind": "candidate",
                    "definition": {"schema": "candidate_definition@1", "canonical_expression": "x>y"},
                    "parent_version_ids": [], "support_evidence_ids": [],
                },
            )



    def test_typed_candidate_restores_evidence_ids_from_ingested_support(self):
        candidate = Candidate(
            candidate_id="relation:supported", version=1,
            canonical_expression="a relates_to b", proposer_family="relational",
            supporting_families=("relational",), input_types=("entity", "entity"),
            operator="RELATES_TO", evidence_ids=("train-1",),
        )
        self.store.append_events(
            episode_id="ep", idempotency_key="candidate-with-support",
            events=[
                self.observation(),
                self.ingest(),
                {
                    "event_id": "candidate-supported", "event_type": "structure_version",
                    "payload": {
                        "structure_id": candidate.candidate_id,
                        "version_id": "relation:supported@1", "kind": "candidate",
                        "definition": candidate_definition_payload(candidate),
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "ingested", "id": "train-1"}],
                    },
                },
            ],
        )
        restored = self.store.replay_projection("ep").candidate_objects["relation:supported@1"]
        self.assertEqual(restored.evidence_ids, ("train-1",))



    def test_typed_ingested_evidence_round_trips_to_e12_evidence(self):
        evidence = Evidence(
            evidence_id="train-typed", episode_id="ep",
            world_family="finite-rule-world", split_role=SplitRole.TRAIN,
            observation_id="obs-1", outcome="label=true",
            model_version="dataset-v1", measurement_cost=0.25,
            provenance="dataset:fixture-7",
        )
        ingest = self.ingest(evidence_id="train-typed")
        ingest["payload"]["evidence_definition"] = evidence_definition_payload(evidence)
        self.store.append_events(
            episode_id="ep", idempotency_key="typed-ingest",
            events=[self.observation(), ingest],
        )
        projection = self.store.replay_projection("ep")
        restored = projection.evidence_objects["train-typed"]
        self.assertEqual(restored, evidence)
        self.assertEqual(projection.digest, self.store.replay_projection("ep").digest)

    def test_typed_revealed_evidence_preserves_causal_visibility_steps(self):
        expected = Evidence(
            evidence_id="reveal-typed", episode_id="ep",
            world_family="finite-rule-world", split_role=SplitRole.LOCKED_TEST,
            observation_id="obs-locked", outcome=canonical_json({"label": "positive"}),
            model_version="model-v7", measurement_cost=0.4,
            prediction_commit_step=2, label_visibility_step=3,
            provenance="evaluator:locked-test",
        )
        self.store.append_events(
            episode_id="ep", idempotency_key="typed-reveal",
            events=[
                self.observation("obs-locked"),
                {
                    "event_id": "commit-typed", "event_type": "prediction_commit",
                    "payload": {
                        "prediction_id": "pred-typed", "observation_id": "obs-locked",
                        "model_version": "model-v7", "learner_track": "e12",
                        "decision_status": "PREDICT",
                    },
                },
                {
                    "event_id": "reveal-typed", "event_type": "evidence_reveal",
                    "payload": {
                        "prediction_id": "pred-typed", "learner_track": "e12",
                        "target_or_feedback": {"label": "positive"},
                        "split_role": "locked_test",
                        "evidence_definition": evidence_definition_payload(expected),
                    },
                },
            ],
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(projection.evidence_objects["reveal-typed"], expected)
        self.assertEqual(projection.evidence_objects["reveal-typed"].prediction_commit_step, 2)
        self.assertEqual(projection.evidence_objects["reveal-typed"].label_visibility_step, 3)

    def test_typed_revealed_evidence_rejects_model_version_mismatch(self):
        with self.assertRaises(ProtocolError):
            self.store.append_events(
                episode_id="ep", idempotency_key="bad-typed-reveal",
            events=[
                self.observation("obs-locked"),
                {
                    "event_id": "commit-typed", "event_type": "prediction_commit",
                    "payload": {
                        "prediction_id": "pred-typed", "observation_id": "obs-locked",
                        "model_version": "model-v7", "learner_track": "e12",
                        "decision_status": "PREDICT",
                    },
                },
                {
                    "event_id": "reveal-typed", "event_type": "evidence_reveal",
                    "payload": {
                        "prediction_id": "pred-typed", "learner_track": "e12",
                        "target_or_feedback": {"label": "positive"},
                        "split_role": "locked_test",
                        "evidence_definition": {
                            "schema": "evidence_definition@1",
                            "world_family": "finite-rule-world",
                            "outcome": canonical_json({"label": "positive"}),
                            "model_version": "wrong-model",
                        },
                    },
                },
            ],
            )

    def test_projection_hydrates_typed_e12_action_objects(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="action-hydration",
            events=[
                self.observation(),
                {
                    "event_id": "candidate-v1", "event_type": "structure_version",
                    "payload": {
                        "structure_id": "candidate", "version_id": "candidate@1",
                        "kind": "candidate",
                        "definition": {
                            "schema": "candidate_definition@1",
                            "canonical_expression": "x > y", "proposer_family": "relational",
                            "supporting_families": ["relational"], "input_types": ["number", "number"],
                            "operator": "GT", "conditions": [], "uncertainty": 0.2,
                            "complexity": 1, "proposal_cost": 0.1,
                        },
                        "parent_version_ids": [], "support_evidence_ids": [],
                    },
                },
                {
                    "event_id": "propose-event", "event_type": "lifecycle_action",
                    "payload": {
                        "action_id": "propose-candidate", "action_type": "propose",
                        "candidate_id": "candidate", "candidate_version": 1,
                        "from_state": "observed", "to_state": "proposed",
                        "evidence_refs": [], "cost": 0.1, "note": "proposer",
                        "candidate_lineage_refs": [], "learner_track": "e12",
                    },
                },
            ],
        )
        projection = self.store.replay_projection("ep")
        self.assertEqual(len(projection.action_objects), 1)
        self.assertEqual(projection.action_objects[0].action_type.value, "propose")
        self.assertEqual(projection.action_objects[0].from_state, CandidateState.OBSERVED)
        self.assertEqual(projection.action_objects[0].to_state, CandidateState.PROPOSED)



    def test_hydrate_lifecycle_ledger_replays_candidate_and_typed_train_evidence(self):
        candidate = Candidate(
            candidate_id="primitive-ledger", version=1,
            canonical_expression="x > y", proposer_family="relational",
            supporting_families=("relational",), input_types=("number", "number"),
            operator="GT", evidence_ids=("train-ledger",),
        )
        evidence = Evidence(
            evidence_id="train-ledger", episode_id="ep",
            world_family="finite-rule-world", split_role=SplitRole.TRAIN,
            observation_id="obs-1", outcome="positive", model_version="dataset-v1",
            measurement_cost=0.1, provenance="dataset:train",
        )
        ingest = self.ingest(evidence_id="train-ledger")
        ingest["payload"]["evidence_definition"] = evidence_definition_payload(evidence)
        actions = []
        transitions = [
            ("propose", "propose", "observed", "proposed", []),
            ("discriminate", "request_discrimination", "proposed", "discrimination_pending", []),
            ("train", "train_support", "discrimination_pending", "train_supported",
             [{"kind": "ingested", "id": "train-ledger"}]),
        ]
        for aid, action_type, before, after, refs in transitions:
            actions.append({
                "event_id": f"event-{aid}", "event_type": "lifecycle_action",
                "payload": {
                    "action_id": aid, "action_type": action_type,
                    "candidate_id": candidate.candidate_id, "candidate_version": 1,
                    "from_state": before, "to_state": after,
                    "evidence_refs": refs, "cost": 0.1, "note": aid,
                    "candidate_lineage_refs": [], "learner_track": "e12",
                },
            })
        self.store.append_events(
            episode_id="ep", idempotency_key="full-ledger-hydration",
            events=[
                self.observation(), ingest,
                {
                    "event_id": "candidate-ledger", "event_type": "structure_version",
                    "payload": {
                        "structure_id": candidate.candidate_id, "version_id": "primitive-ledger@1",
                        "kind": "candidate", "definition": candidate_definition_payload(candidate),
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "ingested", "id": "train-ledger"}],
                    },
                },
                *actions,
            ],
        )
        projection = self.store.replay_projection("ep")
        ledgers = projection.hydrate_lifecycle_ledgers()
        self.assertEqual(set(ledgers), {"e12"})
        ledger = ledgers["e12"]
        reference = LifecycleLedger()
        reference.add_candidate(candidate)
        reference.add_evidence(evidence)
        for aid, action_type, before, after, refs in transitions:
            reference.apply(Action(
                action_id=aid, action_type=ActionType(action_type),
                candidate_id=candidate.candidate_id, candidate_version=1,
                evidence_ids=("train-ledger",) if refs else (), cost=0.1,
                from_state=CandidateState(before), to_state=CandidateState(after),
                note=aid,
            ))
        self.assertEqual(dict(ledger.candidates), dict(reference.candidates))
        self.assertEqual(dict(ledger.evidence), dict(reference.evidence))
        self.assertEqual(ledger.actions, reference.actions)
        self.assertEqual(
            ledger.candidates[(candidate.candidate_id, 1)].state,
            CandidateState.TRAIN_SUPPORTED,
        )
        self.assertEqual(ledger.evidence["train-ledger"], evidence)
        self.assertEqual([action.action_id for action in ledger.actions],
                         ["propose", "discriminate", "train"])
        first_digest = projection.digest
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        reopened = self.store.replay_projection("ep")
        reopened_ledger = reopened.hydrate_lifecycle_ledgers()["e12"]
        self.assertEqual(reopened.digest, first_digest)
        self.assertEqual(dict(reopened_ledger.candidates), dict(reference.candidates))
        self.assertEqual(dict(reopened_ledger.evidence), dict(reference.evidence))
        self.assertEqual(reopened_ledger.actions, reference.actions)

    def test_hydration_keeps_candidate_state_isolated_per_learner_track(self):
        candidate = Candidate(
            candidate_id="shared-primitive", version=1,
            canonical_expression="a relates_to b", proposer_family="relational",
            supporting_families=("relational",), input_types=("entity", "entity"),
            operator="RELATES_TO",
        )
        self.store.append_events(
            episode_id="ep", idempotency_key="track-isolation",
            events=[
                self.observation(),
                {
                    "event_id": "shared-candidate", "event_type": "structure_version",
                    "payload": {
                        "structure_id": candidate.candidate_id, "version_id": "shared-primitive@1",
                        "kind": "candidate", "definition": candidate_definition_payload(candidate),
                        "parent_version_ids": [], "support_evidence_ids": [],
                    },
                },
                {
                    "event_id": "track-a-propose", "event_type": "lifecycle_action",
                    "payload": {
                        "action_id": "track-a-propose", "action_type": "propose",
                        "candidate_id": candidate.candidate_id, "candidate_version": 1,
                        "from_state": "observed", "to_state": "proposed",
                        "evidence_refs": [], "cost": 0.1, "note": "track A",
                        "candidate_lineage_refs": [], "learner_track": "track-a",
                    },
                },
                {
                    "event_id": "track-b-measure", "event_type": "lifecycle_action",
                    "payload": {
                        "action_id": "track-b-measure", "action_type": "measure",
                        "candidate_id": candidate.candidate_id, "candidate_version": 1,
                        "from_state": None, "to_state": None,
                        "evidence_refs": [], "cost": 0.0, "note": "track B",
                        "candidate_lineage_refs": [], "learner_track": "track-b",
                    },
                },
            ],
        )
        ledgers = self.store.replay_projection("ep").hydrate_lifecycle_ledgers()
        self.assertEqual(
            ledgers["track-a"].candidates[(candidate.candidate_id, 1)].state,
            CandidateState.PROPOSED,
        )
        self.assertEqual(
            ledgers["track-b"].candidates[(candidate.candidate_id, 1)].state,
            CandidateState.OBSERVED,
        )



    def test_ledger_hydration_fails_closed_for_legacy_untyped_evidence(self):
        candidate = Candidate(
            candidate_id="candidate-needs-typed-evidence", version=1,
            canonical_expression="x > y", proposer_family="relational",
            supporting_families=("relational",), input_types=("number", "number"),
            operator="GT", evidence_ids=("legacy-reveal",),
        )
        self.store.append_events(
            episode_id="ep", idempotency_key="legacy-evidence-no-hydration",
            events=[
                self.observation("obs-locked"),
                {
                    "event_id": "commit-legacy", "event_type": "prediction_commit",
                    "payload": {
                        "prediction_id": "pred-legacy", "observation_id": "obs-locked",
                        "model_version": "model-v1", "learner_track": "e12",
                        "decision_status": "PREDICT",
                    },
                },
                {
                    "event_id": "reveal-legacy", "event_type": "evidence_reveal",
                    "payload": {
                        "prediction_id": "pred-legacy", "learner_track": "e12",
                        "target_or_feedback": {"label": "positive"},
                        "split_role": "locked_test",
                    },
                },
                {
                    "event_id": "candidate-needs-evidence", "event_type": "structure_version",
                    "payload": {
                        "structure_id": candidate.candidate_id,
                        "version_id": "candidate-needs-typed-evidence@1",
                        "kind": "candidate", "definition": candidate_definition_payload(candidate),
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "revealed", "id": "reveal-legacy"}],
                    },
                },
                {
                    "event_id": "candidate-propose", "event_type": "lifecycle_action",
                    "payload": {
                        "action_id": "candidate-propose", "action_type": "propose",
                        "candidate_id": candidate.candidate_id, "candidate_version": 1,
                        "from_state": "observed", "to_state": "proposed",
                        "evidence_refs": [], "cost": 0.1, "note": "propose",
                        "candidate_lineage_refs": [], "learner_track": "e12",
                    },
                },
            ],
        )
        with self.assertRaisesRegex(ProtocolError, "without typed E12 definitions"):
            self.store.replay_projection("ep").hydrate_lifecycle_ledgers()


    def test_dependency_edges_are_persisted_projected_and_reopened(self):
        def make_candidate(cid, expression):
            return Candidate(candidate_id=cid, version=1, canonical_expression=expression,
                proposer_family="relational", supporting_families=("relational",),
                input_types=("number", "number"), operator="GT")
        base = make_candidate("base", "x > y")
        consumer = make_candidate("consumer", "x > y and z")
        events = [self.observation()]
        for cid, candidate in (("base", base), ("consumer", consumer)):
            events.append({
                "event_id": f"{cid}-version", "event_type": "structure_version",
                "payload": {"structure_id": cid, "version_id": f"{cid}@1",
                    "kind": "candidate", "definition": candidate_definition_payload(candidate),
                    "parent_version_ids": [], "support_evidence_ids": []},
            })
            events.append({
                "event_id": f"{cid}-propose", "event_type": "lifecycle_action",
                "payload": {"action_id": f"{cid}-propose", "action_type": "propose",
                    "candidate_id": cid, "candidate_version": 1,
                    "from_state": "observed", "to_state": "proposed",
                    "evidence_refs": [], "cost": 0.1, "note": "proposal",
                    "candidate_lineage_refs": [], "learner_track": "track-a"},
            })
        events.append({
            "event_id": "edge-base-consumer", "event_type": "dependency_added",
            "payload": {"dependent_version_id": "consumer@1", "dependency_version_id": "base@1",
                "learner_track": "track-a", "role": "uses", "impact_policy": "blocking", "evidence_refs": []},
        })
        receipts, projection = self.store.append_events_and_project(
            episode_id="ep", idempotency_key="dependency-batch", events=events)
        self.assertEqual(len(receipts), len(events))
        self.assertEqual(len(projection.dependencies), 1)
        self.assertEqual(projection.dependencies[0]["dependent_version_id"], "consumer@1")
        self.assertEqual(projection.dependency_revalidation_queue, ())
        digest = projection.digest
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        reopened = self.store.replay_projection("ep")
        self.assertEqual(reopened.dependencies, projection.dependencies)
        self.assertEqual(reopened.dependency_revalidation_queue, ())
        self.assertEqual(reopened.digest, digest)

    def test_dependency_rejects_unknown_endpoint_and_unbound_track(self):
        candidate = Candidate(candidate_id="only-a", version=1, canonical_expression="x",
            proposer_family="test", supporting_families=("test",), input_types=("number",), operator="IDENTITY")
        self.store.append_events(episode_id="ep", idempotency_key="candidate-a", events=[
            self.observation(),
            {"event_id":"candidate-a","event_type":"structure_version","payload":{
                "structure_id":"only-a","version_id":"only-a@1","kind":"candidate",
                "definition":candidate_definition_payload(candidate),"parent_version_ids":[],"support_evidence_ids":[]}},
            {"event_id":"candidate-a-propose","event_type":"lifecycle_action","payload":{
                "action_id":"candidate-a-propose","action_type":"propose","candidate_id":"only-a","candidate_version":1,
                "from_state":"observed","to_state":"proposed","evidence_refs":[],"cost":0.1,"note":"proposal",
                "candidate_lineage_refs":[],"learner_track":"track-a"}},
        ])
        with self.assertRaises(MissingReference):
            self.store.append_event(episode_id="ep",event_id="unknown-edge",event_type="dependency_added",
                idempotency_key="unknown-edge",payload={"dependent_version_id":"only-a@1",
                "dependency_version_id":"missing@1","learner_track":"track-a","role":"uses",
                "impact_policy":"blocking","evidence_refs":[]})
        with self.assertRaises(MissingReference):
            self.store.append_event(episode_id="ep",event_id="unbound-track",event_type="dependency_added",
                idempotency_key="unbound-track",payload={"dependent_version_id":"only-a@1",
                "dependency_version_id":"only-a@1","learner_track":"track-b","role":"uses",
                "impact_policy":"blocking","evidence_refs":[]})
        self.assertEqual(len(self.store.replay_episode("ep")), 3)

    def test_dependency_impact_policies_drive_track_local_queue(self):
        def run_episode(episode_id, first_policy):
            events = [self.observation()]
            events.append(self.ingest(evidence_id=f"{episode_id}-train"))
            events.extend([
                self.observation("obs-gate"),
                {"event_id":f"{episode_id}-commit-gate","event_type":"prediction_commit","payload":{
                    "prediction_id":f"{episode_id}-pred-gate","observation_id":"obs-gate",
                    "model_version":"model-v1","learner_track":"track-a","decision_status":"PREDICT"}},
                {"event_id":f"{episode_id}-reveal-gate","event_type":"evidence_reveal","payload":{
                    "prediction_id":f"{episode_id}-pred-gate","learner_track":"track-a",
                    "target_or_feedback":{"label":"gate"},"split_role":"gate_final"}},
                self.observation("obs-locked"),
                {"event_id":f"{episode_id}-commit-locked","event_type":"prediction_commit","payload":{
                    "prediction_id":f"{episode_id}-pred-locked","observation_id":"obs-locked",
                    "model_version":"model-v1","learner_track":"track-a","decision_status":"PREDICT"}},
                {"event_id":f"{episode_id}-reveal-locked","event_type":"evidence_reveal","payload":{
                    "prediction_id":f"{episode_id}-pred-locked","learner_track":"track-a",
                    "target_or_feedback":{"label":"counterexample"},"split_role":"locked_test"}},
            ])
            for cid in ("root", "consumer", "leaf"):
                candidate = Candidate(candidate_id=f"{episode_id}-{cid}", version=1,
                    canonical_expression=f"{cid}(x)", proposer_family="test",
                    supporting_families=("test",), input_types=("symbol",), operator="IDENTITY")
                events.append({"event_id":f"{episode_id}-{cid}-version","event_type":"structure_version","payload":{
                    "structure_id":candidate.candidate_id,"version_id":f"{candidate.candidate_id}@1",
                    "kind":"candidate","definition":candidate_definition_payload(candidate),
                    "parent_version_ids":[],"support_evidence_ids":[]}})
                transitions = [
                    ("propose","propose","observed","proposed",[]),
                    ("discriminate","request_discrimination","proposed","discrimination_pending",[]),
                    ("train","train_support","discrimination_pending","train_supported",[{"kind":"ingested","id":f"{episode_id}-train"}]),
                    ("gate","gate_validate","train_supported","gate_validated",[{"kind":"revealed","id":f"{episode_id}-reveal-gate"}]),
                ]
                for aid, action_type, before, after, refs in transitions:
                    events.append({"event_id":f"{episode_id}-{cid}-{aid}","event_type":"lifecycle_action","payload":{
                        "action_id":f"{episode_id}-{cid}-{aid}","action_type":action_type,
                        "candidate_id":candidate.candidate_id,"candidate_version":1,
                        "from_state":before,"to_state":after,"evidence_refs":refs,
                        "cost":0.1,"note":aid,"candidate_lineage_refs":[],"learner_track":"track-a"}})
            root, consumer, leaf = (f"{episode_id}-{name}@1" for name in ("root","consumer","leaf"))
            events.extend([
                {"event_id":f"{episode_id}-edge-consumer-root","event_type":"dependency_added","payload":{
                    "dependent_version_id":consumer,"dependency_version_id":root,"learner_track":"track-a",
                    "role":"uses","impact_policy":first_policy,"evidence_refs":[]}},
                {"event_id":f"{episode_id}-edge-leaf-consumer","event_type":"dependency_added","payload":{
                    "dependent_version_id":leaf,"dependency_version_id":consumer,"learner_track":"track-a",
                    "role":"composes","impact_policy":"blocking","evidence_refs":[]}},
                {"event_id":f"{episode_id}-challenge-root","event_type":"lifecycle_action","payload":{
                    "action_id":f"{episode_id}-challenge-root","action_type":"challenge",
                    "candidate_id=f"{episode_id}-root","candidate_version":1,
                    "from_state":"gate_validated","to_state":"challenged",
                    "evidence_refs":[{"kind":"revealed","id":f"{episode_id}-reveal-locked"}],
                    "cost":0.2,"note":"locked counterexample","candidate_lineage_refs":[],"learner_track":"track-a"}},
            ])
            projection = self.store.append_events_and_project(
                episode_id=episode_id, idempotency_key=f"{episode_id}-batch", events=events
            )[1]
            return {item["version_id"] for item in projection.dependency_revalidation_queue}

        self.assertEqual(run_episode("blocking", "blocking"), {"blocking-consumer@1", "blocking-leaf@1"})
        self.assertEqual(run_episode("review", "review"), {"review-consumer@1"})
        self.assertEqual(run_episode("advisory", "advisory"), set())

    def test_dependency_cycle_is_rejected_without_consuming_sequence(self):
        events = [self.observation()]
        for cid in ("left", "right"):
            candidate = Candidate(candidate_id=cid, version=1, canonical_expression=cid,
                proposer_family="test", supporting_families=("test",), input_types=("symbol",), operator="IDENTITY")
            events.append({"event_id":f"{cid}-version","event_type":"structure_version","payload":{
                "structure_id":cid,"version_id":f"{cid}@1","kind":"candidate",
                "definition":candidate_definition_payload(candidate),"parent_version_ids":[],"support_evidence_ids":[]}})
            events.append({"event_id":f"{cid}-propose","event_type":"lifecycle_action","payload":{
                "action_id":f"{cid}-propose","action_type":"propose","candidate_id":cid,"candidate_version":1,
                "from_state":"observed","to_state":"proposed","evidence_refs":[],"cost":0.1,"note":"proposal",
                "candidate_lineage_refs":[],"learner_track":"e12"}})
        events.append({"event_id":"left-to-right","event_type":"dependency_added","payload":{
            "dependent_version_id":"left@1","dependency_version_id":"right@1","learner_track":"e12",
            "role":"uses","impact_policy":"blocking","evidence_refs":[]}})
        self.store.append_events(episode_id="ep",idempotency_key="first-edge",events=events)
        with self.assertRaises(ProtocolError):
            self.store.append_event(episode_id="ep",event_id="right-to-left",event_type="dependency_added",
                idempotency_key="cycle-edge",payload={"dependent_version_id":"right@1",
                "dependency_version_id":"left@1","learner_track":"e12","role":"uses",
                "impact_policy":"blocking","evidence_refs":[]})
        self.assertEqual(len(self.store.replay_episode("ep")),len(events))


if __name__ == "__main__":
    unittest.main()
