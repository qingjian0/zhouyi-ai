"""Build a reviewed, source-family-aware native training graph from Gold text data.

This is a data-preparation command, not the learner. It validates the Gold
manifest before exporting one requested train or dev split. Locked-test labels
are never exported to learner artifacts.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from itertools import combinations
from pathlib import Path
import tempfile

from prototype.classiang_learning import load_records
from prototype.classiang_dataset_manifest import validate_manifest
from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_learning import CompositionLabel


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\\0".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:20]}"


def build_training_corpus(
    manifest_path: str | Path,
    *,
    split: str = "train",
    max_pairs_per_record: int = 256,
) -> tuple[SymbolGraph, tuple[CompositionLabel, ...], dict]:
    """Export co-observed positive pairs and cross-observation hard negatives.

    Both labels use the same has_aspect relation type. Positive pairs share
    one observed subject; negative pairs combine aspects from distinct records
    in the same source family. This removes the explicit negative-marker
    shortcut from the first-generation training objective.
    """
    if split not in {"train", "dev"}:
        raise ValueError("only train and dev splits may be exported to the learner")
    if isinstance(max_pairs_per_record, bool) or not isinstance(max_pairs_per_record, int) or max_pairs_per_record < 1:
        raise ValueError("max_pairs_per_record must be a positive integer")
    manifest_file = Path(manifest_path).resolve()
    admission = validate_manifest(manifest_file)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    dataset_path = (manifest_file.parent / manifest["dataset"]["path"]).resolve()
    groups = {row["group_id"]: row for row in manifest["groups"]}
    sources = {row["source_id"]: row for row in manifest["sources"]}
    records = load_records(dataset_path)
    split_records = tuple(row for row in records if groups[row.group_id]["split"] == split)

    evidence_by_id: dict[str, EvidenceRef] = {}
    symbols: list[Symbol] = []
    relations: list[Relation] = []
    labels: list[CompositionLabel] = []
    family_records: dict[str, list[dict]] = {}
    used_records = 0

    for record in split_records:
        if not record.annotations:
            continue
        source = sources[record.source_id]
        family = source["source_family_id"]
        subject_id = _stable_id("subject", record.observation_id)
        subject_evidence: list[str] = []
        positive_relations: list[str] = []

        for index, annotation in enumerate(record.annotations):
            evidence_id = (
                f"text:{record.observation_id}:{record.source_id}:"
                f"chars:{annotation.start_char}-{annotation.end_char}"
            )
            evidence_by_id[evidence_id] = EvidenceRef(
                evidence_id, record.source_id, family,
                f"observation:{record.observation_id}:chars:{annotation.start_char}-{annotation.end_char}",
                source["license_id"], True,
            )
            subject_evidence.append(evidence_id)
            aspect_id = _stable_id(
                "aspect", record.observation_id, str(index),
                annotation.dimension, annotation.value,
            )
            symbols.append(Symbol(
                aspect_id, record.domain, "annotated_aspect",
                (("dimension", annotation.dimension), ("value", annotation.value)),
                (evidence_id,), record.context,
            ))
            relation_id = _stable_id("relation", record.observation_id, "aspect", str(index))
            relations.append(Relation(
                relation_id, "has_aspect",
                (("subject", subject_id), ("aspect", aspect_id)),
                (evidence_id,),
                conditions=tuple(sorted(f"purpose:{item}" for item in annotation.purposes)),
                context=record.context,
            ))
            positive_relations.append(relation_id)

        symbols.append(Symbol(
            subject_id, record.domain, "observed_subject",
            (("subject_id", record.subject_id),),
            tuple(sorted(set(subject_evidence))), record.context,
        ))
        record_positive_pairs = list(combinations(positive_relations, 2))
        for index, pair in enumerate(record_positive_pairs):
            relation_ids = tuple(sorted(pair))
            evidence_ids = tuple(sorted({
                evidence_id
                for relation in relations if relation.relation_id in relation_ids
                for evidence_id in relation.evidence_ids
            }))
            labels.append(CompositionLabel(
                example_id=_stable_id("example", record.observation_id, "positive", str(index)),
                group_id=record.group_id, source_family=family,
                relation_ids=relation_ids, evidence_ids=evidence_ids,
                label=1, reviewed=True,
            ))
        family_records.setdefault(family, []).append({
            "observation_id": record.observation_id,
            "group_id": record.group_id,
            "relation_ids": tuple(positive_relations),
        })
        used_records += 1

    negative_examples = 0
    for family, family_rows in sorted(family_records.items()):
        cross_record_pairs = [
            (left, right)
            for left_index, left_row in enumerate(family_rows)
            for right_row in family_rows[left_index + 1:]
            for left in left_row["relation_ids"]
            for right in right_row["relation_ids"]
        ]
        if len(cross_record_pairs) > max_pairs_per_record * max(1, len(family_rows)):
            raise ValueError(
                f"source family {family} exceeds max_pairs_per_record hard-negative budget"
            )
        for index, pair in enumerate(cross_record_pairs):
            relation_ids = tuple(sorted(pair))
            evidence_ids = tuple(sorted({
                evidence_id
                for relation in relations if relation.relation_id in relation_ids
                for evidence_id in relation.evidence_ids
            }))
            selected_relations = [
                relation for relation in relations if relation.relation_id in relation_ids
            ]
            subject_ids = {dict(relation.roles)["subject"] for relation in selected_relations}
            if len(subject_ids) != 2:
                raise ValueError("hard-negative pair must span two distinct observed subjects")
            group_ids = sorted({
                row["group_id"] for row in family_rows
                if set(row["relation_ids"]) & set(relation_ids)
            })
            labels.append(CompositionLabel(
                example_id=_stable_id("example", family, "cross-record-negative", str(index), *relation_ids),
                group_id="|".join(group_ids), source_family=family,
                relation_ids=relation_ids, evidence_ids=evidence_ids,
                label=0, reviewed=True,
            ))
            negative_examples += 1

    graph = SymbolGraph(
        evidence=tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
        symbols=tuple(symbols),
        relations=tuple(relations),
    )
    graph.validate()
    if not labels or not any(row.label == 1 for row in labels) or not any(row.label == 0 for row in labels):
        raise ValueError(
            f"{split} split must contain within-record positive pairs and "
            "cross-record negatives from the same source family"
        )
    family_count = len({row.source_family for row in labels})
    report = {
        "schema_version": 1,
        "dataset_sha256": admission["dataset_sha256"],
        "dataset_record_count": admission["record_count"],
        "exported_split": split,
        "exported_record_count": len(split_records),
        "records_used": used_records,
        "excluded_train_records": admission["records_by_split"]["train"] if split != "train" else 0,
        "excluded_dev_records": admission["records_by_split"]["dev"] if split != "dev" else 0,
        "excluded_locked_test_records": admission["records_by_split"]["locked_test"],
        "exported_source_family_count": family_count,
        "positive_examples": sum(row.label == 1 for row in labels),
        "negative_examples": sum(row.label == 0 for row in labels),
        "negative_sampling": "cross_observation_same_source_family",
        "label_shortcut_control": {
            "positive_relation_types": ["has_aspect"],
            "negative_relation_types": ["has_aspect"],
            "explicit_negative_marker_used": False,
        },
        "locked_test_loaded_into_learner_artifact": False,
        "limitations": [
            "the first objective tests within-record co-observation versus cross-record composition, not analogy or causal validity",
            "negative examples are source-family-matched structural hard negatives, not universally false semantic claims",
            "dev and locked-test labels are excluded from training artifacts",
            "manifest validation checks declared provenance and permissions; it does not independently prove legal rights or semantic truth",
        ],
    }
    return graph, tuple(labels), report

def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, delete=False,
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--graph-out", default="artifacts/classiang-native-train-graph.json")
    parser.add_argument("--labels-out", default="artifacts/classiang-native-train-labels.jsonl")
    parser.add_argument("--report-out", default="artifacts/classiang-native-dataset-report.json")
    parser.add_argument("--max-pairs-per-record", type=int, default=256)
    parser.add_argument("--split", choices=("train", "dev"), default="train")
    args = parser.parse_args()
    graph, labels, report = build_training_corpus(
        args.manifest, split=args.split,
        max_pairs_per_record=args.max_pairs_per_record,
    )
    graph_payload = {
        "schema_version": 1,
        "evidence": [asdict(item) for item in graph.evidence],
        "symbols": [asdict(item) for item in graph.symbols],
        "relations": [asdict(item) for item in graph.relations],
    }
    _write_json(args.graph_out, graph_payload)
    labels_path = Path(args.labels_out)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in labels)
    labels_path.write_text(encoded, encoding="utf-8")
    report["graph_sha256"] = hashlib.sha256(Path(args.graph_out).read_bytes()).hexdigest()
    report["labels_sha256"] = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    _write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
