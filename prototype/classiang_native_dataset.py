"""Build a reviewed, source-family-aware native training graph from Gold text data.

This is a data-preparation command, not the learner. It validates the Gold
manifest before exporting only train-split records; dev and locked-test labels
are excluded from the emitted graph and JSONL.
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
    max_pairs_per_record: int = 256,
) -> tuple[SymbolGraph, tuple[CompositionLabel, ...], dict]:
    """Validate Gold admission, then export train-only relation compositions.

    Label semantics are deliberately narrow:
    - positive: two human-reviewed positive aspects co-annotated in one record;
    - negative: one human-reviewed positive aspect paired with an explicitly
      reviewed negative span from the same record.

    These labels teach structural co-occurrence vs explicit negative evidence;
    they do not establish analogy, semantic equivalence, or causal validity.
    """
    if isinstance(max_pairs_per_record, bool) or not isinstance(max_pairs_per_record, int) or max_pairs_per_record < 1:
        raise ValueError("max_pairs_per_record must be a positive integer")
    manifest_file = Path(manifest_path).resolve()
    admission = validate_manifest(manifest_file)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    dataset_path = (manifest_file.parent / manifest["dataset"]["path"]).resolve()
    groups = {
        row["group_id"]: row
        for row in manifest["groups"]
    }
    sources = {
        row["source_id"]: row
        for row in manifest["sources"]
    }
    # This process is the data-preparation boundary. The learner receives only
    # the emitted train-only graph and labels, never dev or locked-test labels.
    records = load_records(dataset_path)
    train_records = tuple(
        row for row in records
        if groups[row.group_id]["split"] == "train"
    )

    evidence_by_id: dict[str, EvidenceRef] = {}
    symbols: list[Symbol] = []
    relations: list[Relation] = []
    labels: list[CompositionLabel] = []
    used_records = 0
    for record in train_records:
        source = sources[record.source_id]
        family = source["source_family_id"]
        positive_relations: list[str] = []
        negative_relations: list[str] = []
        subject_id = _stable_id("subject", record.observation_id)
        subject_evidence: list[str] = []

        for index, annotation in enumerate(record.annotations):
            evidence_id = f"text:{record.source_id}:chars:{annotation.start_char}-{annotation.end_char}"
            evidence_by_id[evidence_id] = EvidenceRef(
                evidence_id, record.source_id, family,
                f"chars:{annotation.start_char}-{annotation.end_char}",
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
            relation_id = _stable_id("relation", record.observation_id, "positive", str(index))
            relations.append(Relation(
                relation_id, "has_aspect",
                (("subject", subject_id), ("aspect", aspect_id)),
                (evidence_id,),
                conditions=tuple(sorted(f"purpose:{item}" for item in annotation.purposes)),
                context=record.context,
            ))
            positive_relations.append(relation_id)

        for index, (start, end) in enumerate(record.negative_annotations):
            evidence_id = f"text:{record.source_id}:chars:{start}-{end}"
            evidence_by_id[evidence_id] = EvidenceRef(
                evidence_id, record.source_id, family, f"chars:{start}-{end}",
                source["license_id"], True,
            )
            subject_evidence.append(evidence_id)
            aspect_id = _stable_id(
                "negative_aspect", record.observation_id, str(index), str(start), str(end),
            )
            symbols.append(Symbol(
                aspect_id, record.domain, "reviewed_negative_span",
                (("span_length", str(end - start)),),
                (evidence_id,), record.context,
            ))
            relation_id = _stable_id("relation", record.observation_id, "negative", str(index))
            relations.append(Relation(
                relation_id, "has_reviewed_negative",
                (("subject", subject_id), ("aspect", aspect_id)),
                (evidence_id,), context=record.context,
            ))
            negative_relations.append(relation_id)

        positive_pairs = list(combinations(positive_relations, 2))
        negative_pairs = [
            (positive_id, negative_id)
            for positive_id in positive_relations
            for negative_id in negative_relations
        ]
        if len(positive_pairs) + len(negative_pairs) > max_pairs_per_record:
            raise ValueError(
                f"record {record.observation_id} exceeds max_pairs_per_record"
            )
        if not positive_pairs or not negative_pairs:
            # Without both positive co-occurrence and explicit negative spans,
            # this record cannot supervise the binary structural objective.
            continue
        symbols.append(Symbol(
            subject_id, record.domain, "observed_subject",
            (("subject_id", record.subject_id),),
            tuple(sorted(set(subject_evidence))), record.context,
        ))
        for index, pair in enumerate(positive_pairs):
            relation_ids = tuple(sorted(pair))
            evidence_ids = tuple(sorted(set().union(*(
                set(next(item.evidence_ids for item in relations if item.relation_id == rid))
                for rid in relation_ids
            ))))
            labels.append(CompositionLabel(
                example_id=_stable_id("example", record.observation_id, "positive", str(index)),
                group_id=record.group_id, source_family=family,
                relation_ids=relation_ids, evidence_ids=evidence_ids,
                label=1, reviewed=True,
            ))
        for index, pair in enumerate(negative_pairs):
            relation_ids = tuple(sorted(pair))
            evidence_ids = tuple(sorted(set().union(*(
                set(next(item.evidence_ids for item in relations if item.relation_id == rid))
                for rid in relation_ids
            ))))
            labels.append(CompositionLabel(
                example_id=_stable_id("example", record.observation_id, "negative", str(index)),
                group_id=record.group_id, source_family=family,
                relation_ids=relation_ids, evidence_ids=evidence_ids,
                label=0, reviewed=True,
            ))
        used_records += 1

    graph = SymbolGraph(
        evidence=tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
        symbols=tuple(symbols),
        relations=tuple(relations),
    )
    graph.validate()
    if not labels or not any(row.label == 1 for row in labels) or not any(row.label == 0 for row in labels):
        raise ValueError("train split must yield both positive and negative structural examples")
    family_count = len({row.source_family for row in labels})
    if family_count < 2:
        raise ValueError("at least two train source families are required for leakage-safe evaluation")
    report = {
        "schema_version": 1,
        "dataset_sha256": admission["dataset_sha256"],
        "dataset_record_count": admission["record_count"],
        "train_record_count": len(train_records),
        "train_records_used": used_records,
        "excluded_dev_records": admission["records_by_split"]["dev"],
        "excluded_locked_test_records": admission["records_by_split"]["locked_test"],
        "train_source_family_count": family_count,
        "positive_examples": sum(row.label == 1 for row in labels),
        "negative_examples": sum(row.label == 0 for row in labels),
        "label_semantics": {
            "positive": "two human-reviewed positive aspects co-annotated in one record",
            "negative": "one human-reviewed positive aspect paired with an explicitly reviewed negative span",
        },
        "locked_test_loaded_into_learner_artifact": False,
        "limitations": [
            "this objective learns reviewed within-record structural co-occurrence, not general analogy or causal validity",
            "dev and locked-test labels are excluded from exported training artifacts",
            "manifest validation checks declared provenance and permissions; it does not independently prove legal rights or semantic truth",
        ],
    }
    return graph, tuple(labels), report


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\\n"
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
    args = parser.parse_args()
    graph, labels, report = build_training_corpus(
        args.manifest, max_pairs_per_record=args.max_pairs_per_record,
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
    encoded = "".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) + "\\n" for row in labels)
    labels_path.write_text(encoded, encoding="utf-8")
    report["graph_sha256"] = hashlib.sha256(Path(args.graph_out).read_bytes()).hexdigest()
    report["labels_sha256"] = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    _write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
