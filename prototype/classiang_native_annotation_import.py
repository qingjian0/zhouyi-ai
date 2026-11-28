"""Import independently adjudicated M19 packets for native relation-pair Gold.

The importer binds every annotation to an existing queue item and preserves the
full M19/M1/M2 bundle for the existing native admission verifier. It never
creates evidence references or byte spans.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from prototype.classiang_native_learning import CompositionLabel, graph_from_json
from prototype.classiang_native_admission import _review_packet_from_json
from prototype.yixiang_annotation_adjudication import ReviewStatus, assess_review_packet


class NativeAnnotationImportError(ValueError):
    """An adjudication cannot be safely bound to a native review item."""


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_queue(path: str | Path) -> dict:
    queue = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(queue, dict) or queue.get("queue_type") != "native_relation_composition_review":
        raise NativeAnnotationImportError("input is not a native relation review queue")
    supplied_digest = queue.get("queue_sha256")
    unsigned = dict(queue)
    unsigned.pop("queue_sha256", None)
    if not isinstance(supplied_digest, str) or _canonical_digest(unsigned) != supplied_digest:
        raise NativeAnnotationImportError("review queue digest mismatch")
    items = queue.get("items")
    if not isinstance(items, list):
        raise NativeAnnotationImportError("review queue items must be a list")
    by_id = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("review_item_id"), str):
            raise NativeAnnotationImportError("invalid review queue item")
        if item["review_item_id"] in by_id:
            raise NativeAnnotationImportError("duplicate review_item_id in queue")
        by_id[item["review_item_id"]] = item
    return by_id


def import_adjudicated_rows(
    *,
    graph,
    queue_path: str | Path,
    adjudications_path: str | Path,
) -> tuple[list[dict], list[dict]]:
    """Return native label rows and complete admission bundles.

    Each input JSONL row must contain review_item_id, m19, m19_reference_map,
    native_evidence_map, and m2. The evidence maps and M2 record are passed
    through unchanged and are verified later against the real M1 SQLite DB.
    """
    queue_items = _load_queue(queue_path)
    labels: list[dict] = []
    admissions: list[dict] = []
    seen: set[str] = set()
    for line_number, line in enumerate(Path(adjudications_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise NativeAnnotationImportError(f"invalid adjudication JSONL line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise NativeAnnotationImportError(f"line {line_number} must be an object")
        item_id = row.get("review_item_id")
        if not isinstance(item_id, str) or item_id not in queue_items:
            raise NativeAnnotationImportError(f"line {line_number} references an unknown queue item")
        if item_id in seen:
            raise NativeAnnotationImportError(f"duplicate adjudication for queue item {item_id}")
        seen.add(item_id)
        item = queue_items[item_id]
        required = ("m19", "m19_reference_map", "native_evidence_map", "m2")
        missing = [key for key in required if key not in row]
        if missing:
            raise NativeAnnotationImportError(f"line {line_number} missing admission fields: {missing}")
        try:
            packet = _review_packet_from_json(row["m19"])
            assessment = assess_review_packet(packet)
        except (TypeError, ValueError, KeyError) as exc:
            raise NativeAnnotationImportError(f"line {line_number} has invalid M19 packet: {exc}") from exc
        if assessment.status is not ReviewStatus.ADJUDICATED or not assessment.gold_eligible:
            raise NativeAnnotationImportError(
                f"line {line_number} M19 packet is not Gold-eligible: "
                f"status={assessment.status.value}, blockers={assessment.blockers}"
            )
        final = packet.adjudication
        if final is None:
            raise NativeAnnotationImportError(f"line {line_number} has no final M19 adjudication")
        decision_to_label = {"reject": 0, "accept": 1, "conditional": 1, "abstain": 2}
        if final.decision not in decision_to_label:
            raise NativeAnnotationImportError(f"line {line_number} has unsupported M19 decision")
        reviewers = sorted(assessment.reviewer_ids)
        if not reviewers:
            raise NativeAnnotationImportError(f"line {line_number} has no independent reviewers")
        conditions = list(final.scope_conditions) or ["unconditional"]
        label = CompositionLabel(
            example_id=item_id,
            group_id=packet.independence_group,
            source_family=item["source_family"],
            relation_ids=tuple(item["relation_ids"]),
            evidence_ids=tuple(item["evidence_ids"]),
            label=decision_to_label[final.decision],
            reviewed=True,
            label_basis="human_reviewed_pair",
            reviewer_id=reviewers[0],
            adjudication_id=final.adjudicator_id,
            scope=final.claim,
            conditions=tuple(conditions),
        )
        try:
            label.validate(graph)
        except ValueError as exc:
            raise NativeAnnotationImportError(f"line {line_number} does not bind to the queued graph pair: {exc}") from exc
        labels.append({
            "example_id": label.example_id,
            "group_id": label.group_id,
            "source_family": label.source_family,
            "relation_ids": list(label.relation_ids),
            "evidence_ids": list(label.evidence_ids),
            "label": label.label,
            "reviewed": label.reviewed,
            "label_basis": label.label_basis,
            "reviewer_id": label.reviewer_id,
            "adjudication_id": label.adjudication_id,
            "scope": label.scope,
            "conditions": list(label.conditions),
            "annotation_schema_version": label.annotation_schema_version,
        })
        admissions.append({
            "example_id": item_id,
            "m19": row["m19"],
            "m19_reference_map": row["m19_reference_map"],
            "native_evidence_map": row["native_evidence_map"],
            "m2": row["m2"],
        })
    return labels, admissions


def _write_jsonl(path: str | Path, rows: list[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="native symbol graph JSON")
    parser.add_argument("queue", type=Path, help="native relation review queue JSON")
    parser.add_argument("adjudications", type=Path, help="completed M19/M1/M2 bundle JSONL")
    parser.add_argument("--labels-out", type=Path, required=True)
    parser.add_argument("--admission-out", type=Path, required=True)
    args = parser.parse_args(argv)
    labels, admissions = import_adjudicated_rows(
        graph=graph_from_json(args.graph),
        queue_path=args.queue,
        adjudications_path=args.adjudications,
    )
    _write_jsonl(args.labels_out, labels)
    _write_jsonl(args.admission_out, admissions)
    print(json.dumps({
        "labels_written": len(labels),
        "admission_bundles_written": len(admissions),
        "gold_admission": "pending M1 SQLite resolution and M2 byte-span verification",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
