import io
import base64
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pathlib import Path

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_observation_receipt import E09ObservationReceiptVerifier, build_observation_receipt
from prototype.m2_semantic_unit_store import PersistentSemanticUnitCandidateStore
from prototype.m2_yixiang_grounding_adapter import (
    coordinate_trlw_grounded_yixiang_csg_gcr,
)
from prototype.observation_contract import (
    EpistemicStatus,
    GroundingStatus,
    RecordEnvelope,
    RoleBinding,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
    record_digest,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.trlw_working_set import TRLWQuery, build_trlw_working_set
from prototype.yixiang_role_transform import RoleTransform
from prototype.zpcm_memory import ZPCMMemory


class _E09ReceiptSigner:
    def __init__(self, private_key):
        self.private_key = private_key

    def sign(self, verifier_id, message):
        return base64.b64encode(self.private_key.sign(message)).decode("ascii")


class PersistentTRLWYixiangCSGGCRE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        evidence_db = root / "m1.sqlite3"
        memory_db = root / "zpcm.sqlite3"

        ingestor = SQLiteEvidenceIngestor(evidence_db)
        source = "甲作为行动者导致乙的状态变化".encode("utf-8")
        result = ingestor.ingest(
            "doc-causal-1", "causal-fixture.txt",
            io.BytesIO(source), chunk_bytes=256,
        )
        self.assertTrue(result.complete)
        chunk = ingestor.get_chunks("doc-causal-1")[0]
        resolver = SQLiteEvidenceRefResolver(evidence_db)
        self.reference = resolver.make_reference("doc-causal-1", chunk.chunk_id)

        self.memory = ZPCMMemory(memory_db)
        self.addCleanup(self.memory.close)
        self.store = PersistentSemanticUnitCandidateStore(
            self.memory, resolver, scope="world:causal-fixture",
        )

    def candidate(self, record_id, kind, *, roles=()):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1",
                record_id=record_id,
                record_kind="SemanticUnitCandidate",
                producer="fixture-grounder",
                producer_version="1.0",
                recorded_at="2026-11-12T00:00:00Z",
                scope="world:causal-fixture",
                source_refs=(self.reference,),
            ),
            kind=kind,
            surface_forms=(record_id,),
            role_bindings=tuple(RoleBinding(name, target) for name, target in roles),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            truth_status=TruthStatus.UNKNOWN,
        )

    def test_m1_to_zpcm_to_trlw_to_yixiang_srok_to_csg_gcr(self):
        relation = self.candidate(
            "relation:causes:1",
            UnitKind.EVENT,
            roles=(("cause", "actor:a"), ("effect", "state:a")),
        )
        workspace = (
            self.candidate("actor:a", UnitKind.ENTITY),
            self.candidate("actor:b", UnitKind.ENTITY),
            self.candidate("state:a", UnitKind.STATE),
            self.candidate("state:b", UnitKind.STATE),
        )
        for record in (relation, *workspace):
            self.store.record_candidate(record)

        # The iterator pages durable records; no complete candidate list is
        # restored from ZPCM before TRLW applies the working-set budgets.
        packet = build_trlw_working_set(
            self.store.iter_candidates(page_size=2),
            TRLWQuery(
                query_goal="find role-preserving causal analogies",
                scope="world:causal-fixture",
                max_records=8,
                byte_budget=100_000,
            ),
            source_complete=True,
        )
        self.assertEqual(packet.status, "COMPLETE")
        self.assertEqual(packet.returned_records, 5)

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        verifier_id = "e09-e2e-test-verifier"
        keyring = E09Ed25519IssuerKeyring({verifier_id: public_key})
        registry = StaticE09DomainRegistry({
            "world:causal-fixture": E09DomainBinding(
                domain_id="domain:causal-fixture",
                world_family="family:causal-fixture",
                registry_id="registry:causal-fixture",
                registry_version="v1",
            )
        })
        now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        receipt_verifier = E09ObservationReceiptVerifier(
            signature_verifier=keyring.verify,
            trusted_verifier_id=verifier_id,
            domain_registry=registry,
            clock=lambda: now,
        )
        signer = _E09ReceiptSigner(private_key)
        e09_event_ids = {
            "relation:causes:1": "e09:obs:relation",
            "actor:a": "e09:obs:actor-a",
            "actor:b": "e09:obs:actor-b",
            "state:a": "e09:obs:state-a",
            "state:b": "e09:obs:state-b",
        }
        receipts = {}
        for record in (relation, *workspace):
            event_id = e09_event_ids[record.envelope.record_id]
            receipts[record.envelope.record_id] = build_observation_receipt(
                signer=signer,
                verifier_id=verifier_id,
                episode_id="episode:causal-fixture",
                scope=record.envelope.scope,
                learner_track="learner:causal-fixture",
                candidate_record_id=record.envelope.record_id,
                candidate_record_digest=record_digest(record),
                domain_id="domain:causal-fixture",
                world_family="family:causal-fixture",
                domain_registry_id="registry:causal-fixture",
                domain_registry_version="v1",
                observations=[{
                    "event_id": event_id,
                    "event_digest": hashlib.sha256(event_id.encode()).hexdigest(),
                    "observation_id": "observation:" + record.envelope.record_id,
                    "episode_id": "episode:causal-fixture",
                }],
                issued_at=now,
                expires_at=now + timedelta(minutes=1),
            )
        result = coordinate_trlw_grounded_yixiang_csg_gcr(
            packet,
            relation_record_id="relation:causes:1",
            relation_type="causes",
            e09_observation_receipts_by_record=receipts,
            receipt_verifier=receipt_verifier,
            transform=RoleTransform(
                "cause-effect-role-view",
                "1.0.0",
                "causes",
                "effect_of",
                (1, 0),
                evidence_refs=("xsl-prior:causal-role-view",),
            ),
            parent_state_ref="world:root",
            branch_id="branch:causal-analogy",
        )

        self.assertTrue(result.working_set.search_exhaustive)
        self.assertTrue(result.srok_search_exhaustive)
        self.assertTrue(result.csg_gcr_search_exhaustive)
        self.assertTrue(result.end_to_end_search_exhaustive)
        self.assertFalse(result.lifecycle_advanced)
        self.assertTrue(result.csg_gcr.proposals)
        for proposal in result.csg_gcr.proposals:
            self.assertEqual(proposal.semantic_status, "HYPOTHESIS_ONLY")
            self.assertIn("e09:obs:relation", proposal.proposal.evidence_refs)
            self.assertNotIn("xsl-prior:causal-role-view", proposal.proposal.evidence_refs)

        # The durable candidate stream remains unchanged; proposing analogies
        # does not mutate facts or promote any hypothesis to an observed record.
        self.assertEqual(
            [item.envelope.record_id for item in self.store.iter_candidates(page_size=2)],
            [
                "relation:causes:1",
                "actor:a",
                "actor:b",
                "state:a",
                "state:b",
            ],
        )


if __name__ == "__main__":
    unittest.main()
