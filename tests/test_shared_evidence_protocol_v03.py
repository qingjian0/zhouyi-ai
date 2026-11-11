import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import MissingReference, ProtocolError, SQLiteEvidenceStore, canonical_json, digest_payload
from prototype.shared_evidence_protocol_v03 import (
    BatchConflict, ProjectionRecoveryRequired, SQLiteEvidenceStoreV03,
    candidate_definition_payload,
)
from prototype.e12a6_lifecycle_contract import Candidate, CandidateState



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



if __name__ == "__main__":
    unittest.main()
