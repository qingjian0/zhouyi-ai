import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from prototype.e09_authority_services import E09AuthenticatedWorkload, E09AuthorityService
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.m2_semantic_unit_reader import PersistentM2SemanticUnitReader
from prototype.m2_semantic_unit_store import PersistentM2SemanticUnitStore
from prototype.m2_yixiang_runtime import M2YixiangRuntimeError, run_persisted_yixiang_search
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, TypedAttribute, UnitKind,
)
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.trlw_working_set import TRLWQuery
from prototype.yixiang_role_transform import RoleTransform
from prototype.zpcm_memory import ZPCMMemory


class _Authenticator:
    def __init__(self, identity):
        self.identity = identity
    def authenticate(self, credential):
        if credential != "observer-cert":
            raise ValueError("unknown workload credential")
        return self.identity


class _Signer:
    def sign(self, issuer_id, message):
        return "test-signature"


class PersistedM2YixiangRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.evidence_db = root / "m1.sqlite3"
        self.memory_db = root / "zpcm.sqlite3"
        self.e09_db = root / "e09.sqlite3"
        ingestor = SQLiteEvidenceIngestor(self.evidence_db)
        raw = "甲使用工具处理乙".encode("utf-8")
        self.assertTrue(ingestor.ingest("doc-1", "fixture.txt", io.BytesIO(raw), chunk_bytes=128).complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
        self.resolver = SQLiteEvidenceRefResolver(self.evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(self.memory_db)
        self.writer = PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="world:test")

        self.identity = E09AuthenticatedWorkload(
            workload_id="spiffe://test/observer", issuer_id="issuer:test",
            roles=frozenset({"observer"}), scopes=frozenset({"world:test"}),
            identity_provider="test-spiffe", authentication_method="mTLS",
            credential_fingerprint=hashlib.sha256(b"observer").hexdigest(),
        )
        self.e09_store = SQLiteEvidenceStore(self.e09_db)
        self.authority = E09AuthorityService(
            self.e09_store, authenticator=_Authenticator(self.identity), signer=_Signer(),
            domain_registry=StaticE09DomainRegistry({
                "world:test": E09DomainBinding(
                    "domain:test", "family:test", "registry:test", "v1",
                ),
            }),
        )
        self.e09_receipt = self.authority.append_observation(
            "observer-cert", episode_id="episode-1",
            event_id="episode-1:observation:obs-1",
            idempotency_key="episode-1:observation:obs-1",
            payload={
                "observation_id": "obs-1", "query_id": "query-1",
                "scope": "world:test", "split": "SUPPORT",
            },
        )
        self.e09_refs = {
            "relation:causes:1": (self.e09_receipt.event_id,),
            "actor:a": (self.e09_receipt.event_id,),
            "state:a": (self.e09_receipt.event_id,),
        }
        self.transform = RoleTransform(
            "cause-effect-role-view", "1.0.0", "causes", "effect_of", (1, 0),
            evidence_refs=("xsl-prior:causal-role-view",),
        )

    def tearDown(self):
        self.memory.close()
        self.e09_store.close()
        self.temp.cleanup()

    def candidate(self, record_id, kind, *, roles=()):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=record_id,
                record_kind="SemanticUnitCandidate", producer="grounding-test",
                producer_version="1", recorded_at="2026-11-12T00:00:00Z",
                scope="world:test", source_refs=(self.reference,),
                derivation_refs=("obs-1",),
            ),
            kind=kind, surface_forms=(record_id,),
            typed_attributes=(TypedAttribute("surface", "text", record_id,
                                               source_refs=(self.reference,)),),
            role_bindings=tuple(RoleBinding(name, target) for name, target in roles),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            truth_status=TruthStatus.UNKNOWN,
        )

    def seed(self):
        self.writer.record_candidate(self.candidate("actor:a", UnitKind.ENTITY))
        self.writer.record_candidate(self.candidate("state:a", UnitKind.STATE))
        self.writer.record_candidate(
            self.candidate("relation:causes:1", UnitKind.EVENT,
                           roles=(("cause", "actor:a"), ("effect", "state:a"))),
        )

    def query(self, *, max_scan_events=10):
        return TRLWQuery(
            query_goal="grounded causal relation composition", scope="world:test",
            max_records=2, byte_budget=10000,
            required_types=(UnitKind.ENTITY, UnitKind.STATE),
            max_scan_events=max_scan_events,
        )

    def test_persisted_zpcm_candidates_flow_through_trlw_yixiang_srok_and_csg_gcr(self):
        self.seed()
        reader = PersistentM2SemanticUnitReader(
            self.memory, self.resolver, scope="world:test", page_size=1,
        )
        result = run_persisted_yixiang_search(
            reader, self.query(), relation_record_id="relation:causes:1",
            relation_type="causes", e09_event_refs_by_record=self.e09_refs,
            transform=self.transform, parent_state_ref="state:parent", branch_id="branch:yx",
        )
        self.assertTrue(result.working_set.source_complete)
        self.assertEqual(
            [entry.record.envelope.record_id for entry in result.working_set.entries],
            ["state:a", "actor:a"],
        )
        self.assertEqual(result.semantic_status, "HYPOTHESIS_ONLY")
        self.assertTrue(result.coordination.proposals)
        self.assertTrue(all(item.semantic_status == "HYPOTHESIS_ONLY"
                            for item in result.coordination.proposals))
        self.assertEqual(self.memory.replay_lifecycle_events(scope="world:test"), [])

    def test_incomplete_trlw_source_scan_fails_closed_before_hypothesis_search(self):
        self.seed()
        reader = PersistentM2SemanticUnitReader(
            self.memory, self.resolver, scope="world:test", page_size=1,
        )
        with self.assertRaisesRegex(M2YixiangRuntimeError, "source scan is incomplete"):
            run_persisted_yixiang_search(
                reader, self.query(max_scan_events=1),
                relation_record_id="relation:causes:1", relation_type="causes",
                e09_event_refs_by_record=self.e09_refs, transform=self.transform,
                parent_state_ref="state:parent", branch_id="branch:yx",
            )


if __name__ == "__main__":
    unittest.main()
