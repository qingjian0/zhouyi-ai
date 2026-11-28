"""Strict bridge from M19 adjudication and M1/M2 evidence into native Classiang labels.

This adapter deliberately accepts typed upstream records, not caller-supplied
receipt strings. Every M19 evidence locator and every native graph evidence ID
must map explicitly to M1 immutable EvidenceRef values, and M2 byte spans are
resolved and hashed against the configured M1 database before admission.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

from prototype.classiang_native import SymbolGraph
from prototype.classiang_native_learning import CompositionLabel
from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.m2_extraction_dataset import (
    AnnotationStatus, AnnotatedExtractionRecord, DatasetSplit, ExtractionDatasetManifest, GoldUnitEvidenceSpan,
)
from prototype.m2_extraction_evaluation import ExtractionGoldCase, GoldSemanticUnit
from prototype.m2_gold_evidence_verifier import verify_gold_evidence_spans
from prototype.observation_contract import EvidenceRef, UnitKind
from prototype.yixiang_annotation_adjudication import (
    FinalAdjudication, IndependentAnnotation, ReviewPacket, ReviewStatus, SourceVerification, assess_review_packet,
)


class NativeGoldAdmissionError(ValueError):
    """A reviewed native label cannot be proven through M19/M1/M2."""


@dataclass(frozen=True)
class NativeGoldAdmissionReceipt:
    example_id: str
    case_id: str
    split: str
    source_lineage: tuple[str, ...]
    native_evidence_ids: tuple[str, ...]
    m1_reference_count: int
    verified_span_count: int
    m2_record_sha256: str
    m2_verification_sha256: str


def verify_native_gold_admission(
    *,
    packet: ReviewPacket,
    record: AnnotatedExtractionRecord,
    graph: SymbolGraph,
    label: CompositionLabel,
    resolver: SQLiteEvidenceRefResolver,
    m19_reference_map: Mapping[str, EvidenceRef],
    native_evidence_map: Mapping[str, Sequence[EvidenceRef]],
    expected_split: DatasetSplit,
) -> NativeGoldAdmissionReceipt:
    """Verify one pair label against independent M19 review and immutable M1 bytes.

    m19_reference_map maps each literal evidence reference appearing in the
    source verification, both independent reviews, and final adjudication to
    one M1 EvidenceRef. native_evidence_map maps each native graph evidence_id
    to the M1 references that prove that exact graph evidence.
    """
    if not isinstance(packet, ReviewPacket):
        raise NativeGoldAdmissionError("packet must be an M19 ReviewPacket")
    if not isinstance(record, AnnotatedExtractionRecord):
        raise NativeGoldAdmissionError("record must be an M2 AnnotatedExtractionRecord")
    if not isinstance(graph, SymbolGraph) or not isinstance(label, CompositionLabel):
        raise NativeGoldAdmissionError("graph and label must use native Classiang types")
    if not isinstance(resolver, SQLiteEvidenceRefResolver):
        raise NativeGoldAdmissionError("resolver must be SQLiteEvidenceRefResolver backed by the M1 database")
    if not isinstance(expected_split, DatasetSplit) or record.split is not expected_split:
        raise NativeGoldAdmissionError("M2 record split does not match the requested native training split")

    assessment = assess_review_packet(packet)
    if assessment.status is not ReviewStatus.ADJUDICATED or not assessment.gold_eligible:
        raise NativeGoldAdmissionError(
            f"M19 packet is not Gold-eligible: status={assessment.status.value}, blockers={assessment.blockers}"
        )
    final = packet.adjudication
    assert final is not None
    if final.decision not in {"accept", "conditional", "reject"}:
        raise NativeGoldAdmissionError("abstained M19 adjudications cannot become pair labels")
    if label.label == 2:
        if label.label_basis != "human_reviewed_pair" or not label.reviewed:
            raise NativeGoldAdmissionError("unknown labels must remain explicitly reviewed")
    elif label.label not in (0, 1):
        raise NativeGoldAdmissionError("native Gold label must be positive, explicit-negative, or unknown")
    if label.label_basis != "human_reviewed_pair" or not label.reviewed:
        raise NativeGoldAdmissionError("native learner labels must be independently adjudicated Gold")
    if label.label != 2:
        if (final.decision == "accept" and label.label != 1) or (final.decision == "reject" and label.label != 0):
            raise NativeGoldAdmissionError("native pair label conflicts with the final M19 adjudication decision")
        if final.decision == "conditional" and (label.label != 1 or not set(final.scope_conditions) <= set(label.conditions)):
            raise NativeGoldAdmissionError("conditional M19 acceptance requires a positive label carrying every adjudicated condition")
    elif final.decision == "abstain":
        raise NativeGoldAdmissionError("abstained M19 adjudications cannot be represented as unknown Gold labels")

    m19_refs = set(packet.source.verification_refs)
    m19_refs.update(final.evidence_refs)
    for annotation in packet.annotations:
        m19_refs.update(annotation.evidence_refs)
    if not m19_refs:
        raise NativeGoldAdmissionError("M19 packet contains no evidence references")
    missing_m19 = sorted(ref for ref in m19_refs if ref not in m19_reference_map)
    if missing_m19:
        raise NativeGoldAdmissionError(f"M19 evidence references lack explicit M1 mapping: {missing_m19}")

    graph.validate()
    label.validate(graph)
    graph_evidence = {item.evidence_id for item in graph.evidence}
    selected_native = set(label.evidence_ids)
    if not selected_native <= graph_evidence:
        raise NativeGoldAdmissionError("label references native evidence absent from graph")
    missing_native = sorted(item for item in selected_native if item not in native_evidence_map)
    if missing_native:
        raise NativeGoldAdmissionError(f"native graph evidence lacks explicit M1 mapping: {missing_native}")

    mapped_refs: set[EvidenceRef] = {m19_reference_map[item] for item in m19_refs}
    for native_id in selected_native:
        refs = native_evidence_map[native_id]
        if not isinstance(refs, (tuple, list)) or not refs:
            raise NativeGoldAdmissionError(f"native evidence mapping is empty: {native_id}")
        if any(not isinstance(ref, EvidenceRef) for ref in refs):
            raise NativeGoldAdmissionError(f"native evidence mapping contains a non-M1 reference: {native_id}")
        mapped_refs.update(refs)

    record_refs = set(record.evidence_refs)
    if not mapped_refs <= record_refs:
        raise NativeGoldAdmissionError("M19/native evidence mapping references M1 chunks absent from the M2 record")
    if set(record.source_lineage_ids) != {
        packet.source.work_id, packet.source.edition_id, packet.source.witness_id,
    }:
        raise NativeGoldAdmissionError("M2 source lineage must exactly bind M19 work, edition, and witness")
    if not record.gold_evidence_spans:
        raise NativeGoldAdmissionError("M2 record must contain byte-exact Gold evidence spans")
    span_refs = {span.evidence_ref for span in record.gold_evidence_spans}
    if not mapped_refs <= span_refs:
        raise NativeGoldAdmissionError("every M19/native evidence mapping must have at least one byte-exact M2 span")

    try:
        verification = verify_gold_evidence_spans(record, resolver)
    except Exception as exc:
        raise NativeGoldAdmissionError(f"M2/M1 byte-level verification failed: {exc}") from exc

    return NativeGoldAdmissionReceipt(
        example_id=label.example_id,
        case_id=packet.case_id,
        split=record.split.value,
        source_lineage=record.source_lineage_ids,
        native_evidence_ids=tuple(sorted(selected_native)),
        m1_reference_count=len(record.evidence_refs),
        verified_span_count=verification.verified_span_count,
        m2_record_sha256=verification.record_sha256,
        m2_verification_sha256=verification.verification_sha256,
    )


def verify_native_gold_dataset(
    *,
    manifest: ExtractionDatasetManifest,
    expected_split: DatasetSplit,
    resolver: SQLiteEvidenceRefResolver,
) -> tuple[str, ...]:
    """Verify every M2 record and its split/lineage isolation before label mapping.

    This dataset-level gate is intentionally separate from per-label mapping:
    it ensures that the entire selected split is backed by live M1 bytes and
    that no source lineage or M1 document is reused across splits.
    """
    if not isinstance(manifest, ExtractionDatasetManifest):
        raise NativeGoldAdmissionError("manifest must be an M2 ExtractionDatasetManifest")
    if not isinstance(expected_split, DatasetSplit):
        raise NativeGoldAdmissionError("expected_split must be DatasetSplit")
    selected = [row for row in manifest.records if row.split is expected_split]
    if not selected:
        raise NativeGoldAdmissionError(f"M2 manifest contains no {expected_split.value} records")
    receipts = []
    for row in selected:
        try:
            receipts.append(verify_gold_evidence_spans(row, resolver))
        except Exception as exc:
            raise NativeGoldAdmissionError(
                f"M2/M1 verification failed for {row.case.case_id}: {exc}"
            ) from exc
    return tuple(receipt.verification_sha256 for receipt in receipts)


def _m1_ref_from_json(value: dict) -> EvidenceRef:
    if not isinstance(value, dict):
        raise NativeGoldAdmissionError("M1 EvidenceRef JSON must be an object")
    try:
        return EvidenceRef(**value)
    except (TypeError, ValueError) as exc:
        raise NativeGoldAdmissionError(f"invalid M1 EvidenceRef: {exc}") from exc


def _review_packet_from_json(value: dict) -> ReviewPacket:
    try:
        source = SourceVerification(**value["source"])
        annotations = tuple(IndependentAnnotation(**row) for row in value["annotations"])
        adjudication_data = value.get("adjudication")
        adjudication = FinalAdjudication(**adjudication_data) if adjudication_data is not None else None
        return ReviewPacket(
            case_id=value["case_id"], claim_kind=value["claim_kind"],
            independence_group=value["independence_group"], source=source,
            annotations=annotations, adjudication=adjudication,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeGoldAdmissionError(f"invalid serialized M19 ReviewPacket: {exc}") from exc


def _m2_record_from_json(value: dict) -> AnnotatedExtractionRecord:
    try:
        case_data = value["case"]
        units = tuple(
            GoldSemanticUnit(
                kind=UnitKind(item["kind"]),
                canonical_key=item["canonical_key"],
                role_bindings=tuple(tuple(pair) for pair in item.get("role_bindings", ())),
            )
            for item in case_data["expected_units"]
        )
        case = ExtractionGoldCase(case_data["case_id"], case_data["domain"], units)
        refs = tuple(_m1_ref_from_json(item) for item in value["evidence_refs"])
        spans = tuple(
            GoldUnitEvidenceSpan(
                unit_index=item["unit_index"],
                evidence_ref=_m1_ref_from_json(item["evidence_ref"]),
                byte_start=item["byte_start"], byte_end=item["byte_end"],
                span_sha256=item["span_sha256"],
            )
            for item in value["gold_evidence_spans"]
        )
        return AnnotatedExtractionRecord(
            case=case, split=DatasetSplit(value["split"]),
            source_lineage_ids=tuple(value["source_lineage_ids"]),
            evidence_refs=refs,
            annotation_status=AnnotationStatus(value["annotation_status"]),
            gold_evidence_spans=spans,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativeGoldAdmissionError(f"invalid serialized M2 AnnotatedExtractionRecord: {exc}") from exc


def verify_native_gold_admission_jsonl(
    *,
    graph: SymbolGraph,
    labels: Sequence[CompositionLabel],
    admission_path: str | Path,
    m1_database: str | Path,
    expected_split: DatasetSplit,
) -> tuple[NativeGoldAdmissionReceipt, ...]:
    """Verify one typed M19/M2 admission packet for every native label.

    JSONL is a transport format only. The M1 resolver and M2 span verifier are
    executed against the configured SQLite database; caller-supplied receipts
    or digests are never trusted as proof.
    """
    path = Path(admission_path)
    if not path.is_file():
        raise NativeGoldAdmissionError(f"Gold admission JSONL does not exist: {path}")
    bundles: dict[str, dict] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            bundle = json.loads(line)
        except json.JSONDecodeError as exc:
            raise NativeGoldAdmissionError(f"invalid admission JSONL at line {line_number}: {exc}") from exc
        if not isinstance(bundle, dict) or not isinstance(bundle.get("example_id"), str):
            raise NativeGoldAdmissionError(f"admission line {line_number} requires example_id")
        example_id = bundle["example_id"]
        if example_id in bundles:
            raise NativeGoldAdmissionError(f"duplicate admission example_id: {example_id}")
        bundles[example_id] = bundle

    labels_by_id = {row.example_id: row for row in labels}
    if len(labels_by_id) != len(labels):
        raise NativeGoldAdmissionError("native labels contain duplicate example IDs")
    if set(bundles) != set(labels_by_id):
        raise NativeGoldAdmissionError(
            f"admission coverage mismatch: missing={sorted(set(labels_by_id)-set(bundles))}, "
            f"extra={sorted(set(bundles)-set(labels_by_id))}"
        )

    resolver = SQLiteEvidenceRefResolver(m1_database)
    receipts = []
    for example_id in sorted(labels_by_id):
        bundle = bundles[example_id]
        try:
            packet = _review_packet_from_json(bundle["m19"])
            record = _m2_record_from_json(bundle["m2"])
            m19_map = {
                key: _m1_ref_from_json(value)
                for key, value in bundle["m19_reference_map"].items()
            }
            native_map = {
                key: tuple(_m1_ref_from_json(item) for item in values)
                for key, values in bundle["native_evidence_map"].items()
            }
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise NativeGoldAdmissionError(
                f"invalid admission bundle for {example_id}: {exc}"
            ) from exc
        receipts.append(verify_native_gold_admission(
            packet=packet, record=record, graph=graph, label=labels_by_id[example_id],
            resolver=resolver, m19_reference_map=m19_map,
            native_evidence_map=native_map, expected_split=expected_split,
        ))
    return tuple(receipts)
