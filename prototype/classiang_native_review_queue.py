"""Evidence-bound human review queue for native Classiang relation compositions.

This queue complements the existing text-span queue: it proposes relation
combinations for human annotation but never assigns labels or promotes model
outputs to Gold. Final labels must still pass M19/M1/M2 admission.
"""
from __future__ import annotations

import argparse
from itertools import combinations
import hashlib
import json
from pathlib import Path
from typing import Any

from prototype.classiang_native_learning import graph_from_json


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_native_relation_review_queue(
    graph,
    *,
    max_items: int = 500,
    max_per_source_family: int = 50,
    max_per_relation: int = 10,
    max_candidates: int = 100_000,
) -> dict[str, Any]:
    """Create deterministic, evidence-preserving relation-pair review tasks.

    Only pairs whose relation evidence is already reviewed and belongs to one
    source family are eligible. Pair generation is deliberately label-agnostic:
    no positive, negative, or unknown label is inferred by this function.
    """
    for name, value in (
        ("max_items", max_items),
        ("max_per_source_family", max_per_source_family),
        ("max_per_relation", max_per_relation),
        ("max_candidates", max_candidates),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")

    graph.validate(require_reviewed=False)
    evidence = {item.evidence_id: item for item in graph.evidence}
    eligible = []
    skipped_relations = []
    for relation in graph.relations:
        refs = [evidence[item] for item in relation.evidence_ids]
        families = {item.source_family for item in refs}
        if not all(item.reviewed for item in refs):
            skipped_relations.append({
                "relation_id": relation.relation_id,
                "reason": "unreviewed_evidence",
            })
            continue
        if len(families) != 1:
            skipped_relations.append({
                "relation_id": relation.relation_id,
                "reason": "mixed_source_family",
            })
            continue
        family = next(iter(families))
        eligible.append((family, relation))

    eligible.sort(key=lambda row: (row[0], row[1].relation_id))
    grouped: dict[str, list[Any]] = {}
    for family, relation in eligible:
        grouped.setdefault(family, []).append(relation)

    candidates = []
    for family in sorted(grouped):
        relations = grouped[family]
        for left, right in combinations(relations, 2):
            relation_ids = tuple(sorted((left.relation_id, right.relation_id)))
            evidence_ids = tuple(sorted(set(left.evidence_ids) | set(right.evidence_ids)))
            payload = {
                "source_family": family,
                "relation_ids": relation_ids,
                "evidence_ids": evidence_ids,
            }
            item_id = _digest(payload)
            candidates.append({
                "review_item_id": item_id,
                **payload,
                "source_ids": sorted({evidence[item].source_id for item in evidence_ids}),
                "source_locators": sorted({
                    f"{evidence[item].source_id}:{evidence[item].locator}"
                    for item in evidence_ids
                }),
                "relations": [
                    {
                        "relation_id": relation.relation_id,
                        "relation_type": relation.relation_type,
                        "roles": [list(pair) for pair in relation.roles],
                        "conditions": list(relation.conditions),
                        "context": list(relation.context),
                        "evidence_ids": list(relation.evidence_ids),
                    }
                    for relation in sorted((left, right), key=lambda row: row.relation_id)
                ],
                "annotation": {
                    "decision": None,
                    "scope": None,
                    "conditions": [],
                    "rationale": None,
                    "reviewer_ids": [],
                    "adjudicator_id": None,
                },
                "review_status": "pending_independent_review",
                "gold_status": "not_gold",
            })
            if len(candidates) > max_candidates:
                raise ValueError("relation-pair candidate budget exceeded")

    candidates.sort(key=lambda item: (
        item["source_family"], item["review_item_id"]
    ))
    selected = []
    family_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for item in candidates:
        if len(selected) >= max_items:
            break
        family = item["source_family"]
        if family_counts.get(family, 0) >= max_per_source_family:
            continue
        if any(relation_counts.get(rid, 0) >= max_per_relation for rid in item["relation_ids"]):
            continue
        selected.append(item)
        family_counts[family] = family_counts.get(family, 0) + 1
        for relation_id in item["relation_ids"]:
            relation_counts[relation_id] = relation_counts.get(relation_id, 0) + 1

    payload = {
        "schema_version": 1,
        "queue_type": "native_relation_composition_review",
        "selection_policy": {
            "label_agnostic": True,
            "same_source_family_only": True,
            "reviewed_evidence_only": True,
            "predictions_are_not_gold": True,
            "max_items": max_items,
            "max_per_source_family": max_per_source_family,
            "max_per_relation": max_per_relation,
            "max_candidates": max_candidates,
        },
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "skipped_relations": skipped_relations,
        "items": selected,
        "gold_admission": (
            "This queue is not a Gold source. Human decisions must be recorded "
            "as independent M19 reviews and adjudication, mapped to immutable "
            "M1 EvidenceRefs and byte-verified M2 spans, then admitted through "
            "prototype.classiang_native_admission."
        ),
    }
    payload["queue_sha256"] = _digest(payload)
    return payload


def write_queue(path: str | Path, queue: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(queue, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, help="schema-v1 native symbol graph JSON")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--max-per-source-family", type=int, default=50)
    parser.add_argument("--max-per-relation", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=100_000)
    args = parser.parse_args(argv)
    queue = build_native_relation_review_queue(
        graph_from_json(args.graph),
        max_items=args.max_items,
        max_per_source_family=args.max_per_source_family,
        max_per_relation=args.max_per_relation,
        max_candidates=args.max_candidates,
    )
    write_queue(args.output, queue)
    print(json.dumps({
        "output": str(args.output),
        "queue_sha256": queue["queue_sha256"],
        "candidate_count": queue["candidate_count"],
        "selected_count": queue["selected_count"],
        "skipped_relations": queue["skipped_relations"],
        "gold_admission": queue["gold_admission"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
