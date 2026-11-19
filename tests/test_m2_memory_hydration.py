import unittest
from types import SimpleNamespace

from prototype.m2_memory_hydration import (
    MemoryHydrationError,
    hydrate_memory_packet,
)
from prototype.m2_memory_packet import (
    MemoryPacket,
    MemoryPacketItem,
    PacketCompleteness,
)
from prototype.observation_contract import (
    EvidenceRef,
    GroundingStatus,
    TruthStatus,
    UnitKind,
)


def reference(document, chunk, text):
    raw = text.encode("utf-8")
    return EvidenceRef(
        document_id=document,
        chunk_id=chunk,
        content_sha256="a" * 64,
        byte_start=0,
        byte_end=len(raw),
        source_version="manifest-sha256:" + "b" * 64,
    )


def packet(items):
    return MemoryPacket(
        schema_version="m2-memory-packet-v1",
        query_goal="retrieve evidence",
        scope="scope-a",
        ranking_policy="append-sequence-asc-v1",
        items=tuple(items),
        completeness=PacketCompleteness.COMPLETE,
        serialized_bytes=128,
        byte_budget=1024,
        records_scanned=len(items),
    )


def item(record_id, refs):
    return MemoryPacketItem(
        record_id=record_id,
        kind=UnitKind.ENTITY,
        source_refs=tuple(refs),
        derivation_refs=(),
        role_bindings=(),
        grounding_status=GroundingStatus.GROUNDED,
        truth_status=TruthStatus.UNKNOWN,
        valid_time_start=None,
        valid_time_end=None,
    )


class Resolver:
    def __init__(self, texts):
        self.texts = texts
        self.calls = []

    def resolve_many(self, refs):
        self.calls.append(list(refs))
        return [
            SimpleNamespace(
                reference=ref,
                text=self.texts[ref],
                ordinal=index,
            )
            for index, ref in enumerate(refs)
        ]


class MemoryHydrationTests(unittest.TestCase):
    def test_resolves_in_packet_order_and_deduplicates_shared_refs(self):
        a = reference("doc", "a", "甲")
        b = reference("doc", "b", "乙丙")
        source = packet([item("one", [a, b]), item("two", [a])])
        resolver = Resolver({a: "甲", b: "乙丙"})
        result = hydrate_memory_packet(source, resolver)
        self.assertEqual(resolver.calls, [[a, b]])
        self.assertEqual(
            [(x.record_id, x.text) for x in result.evidence],
            [("one", "甲"), ("two", "甲"), ("one", "乙丙")],
        )
        self.assertEqual(result.resolved_references, 2)
        self.assertEqual(result.evidence_bytes, len("甲乙丙".encode("utf-8")))
        self.assertEqual(result.completeness, PacketCompleteness.COMPLETE)

    def test_reference_budget_marks_partial_result(self):
        a = reference("doc", "a", "a")
        b = reference("doc", "b", "b")
        resolver = Resolver({a: "a", b: "b"})
        result = hydrate_memory_packet(
            packet([item("one", [a, b])]),
            resolver,
            max_evidence_refs=1,
        )
        self.assertEqual(result.resolved_references, 1)
        self.assertEqual(result.completeness, PacketCompleteness.BUDGET_EXHAUSTED)

    def test_byte_budget_is_checked_before_resolution(self):
        a = reference("doc", "a", "甲甲")
        resolver = Resolver({a: "甲甲"})
        result = hydrate_memory_packet(
            packet([item("one", [a])]),
            resolver,
            max_evidence_bytes=5,
        )
        self.assertEqual(resolver.calls, [[]])
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.completeness, PacketCompleteness.BUDGET_EXHAUSTED)

    def test_rejects_resolver_order_mismatch_and_wrong_utf8_span(self):
        a = reference("doc", "a", "甲")

        class WrongResolver:
            def resolve_many(self, refs):
                return [SimpleNamespace(reference=refs[0], text="x", ordinal=0)]

        with self.assertRaises(MemoryHydrationError):
            hydrate_memory_packet(packet([item("one", [a])]), WrongResolver())

    def test_propagates_source_resolution_failure(self):
        a = reference("doc", "a", "甲")

        class FailingResolver:
            def resolve_many(self, refs):
                raise RuntimeError("stale source manifest")

        with self.assertRaisesRegex(RuntimeError, "stale source manifest"):
            hydrate_memory_packet(packet([item("one", [a])]), FailingResolver())

    def test_empty_packet_does_not_call_resolver(self):
        resolver = Resolver({})
        result = hydrate_memory_packet(packet([]), resolver)
        self.assertEqual(resolver.calls, [])
        self.assertEqual(result.completeness, PacketCompleteness.COMPLETE)
        self.assertEqual(result.evidence, ())


if __name__ == "__main__":
    unittest.main()
