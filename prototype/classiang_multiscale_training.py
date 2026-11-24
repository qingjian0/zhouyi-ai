"""Deterministic multi-scale synthetic training harness for Classiang text learning.

This generates auditable synthetic records at four source-document scales and
trains the existing span learner on bounded chunks. It deliberately reports
chunk-level metrics only: the current NB encoder does not model cross-chunk
memory or document-level semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from prototype.classiang_learning import TextAnnotation, TextRecord, TrainableTextEncoder, evaluate, train_and_evaluate

BANDS = ("short_sentence", "long_sentence", "long_document", "ultra_long_context")


def _annotated_sentence(index: int) -> tuple[str, tuple[tuple[str, str, str], ...]]:
    # Stable, repeated concepts make this a pipeline smoke corpus, not a
    # semantic generalization benchmark.
    text = (
        f"样本{index}采用耐磨材料，并具有防水表层；"
        "部件通过卡扣连接，长期使用后逐渐变化。"
    )
    spans = []
    for surface, dimension, value in (
        ("耐磨", "attribute", "耐磨"),
        ("防水", "attribute", "防水"),
        ("卡扣连接", "relation", "卡扣连接"),
        ("逐渐变化", "process", "逐渐变化"),
    ):
        start = text.index(surface)
        spans.append((surface, dimension, value))
    return text, tuple(spans)


def _record(
    *, doc_id: str, band: str, chunk_index: int, global_offset: int,
    text: str, annotations: list[TextAnnotation],
) -> TextRecord:
    return TextRecord(
        observation_id=f"{doc_id}:chunk:{chunk_index:05d}",
        subject_id=doc_id,
        domain="synthetic-classiang-smoke",
        source_id=f"{doc_id}:chunk:{chunk_index:05d}",
        text=text,
        annotations=tuple(annotations),
        context=(
            f"length_band={band}",
            f"document_id={doc_id}",
            f"chunk_index={chunk_index}",
            f"global_char_offset={global_offset}",
            "data_origin=synthetic_generated",
        ),
        group_id=doc_id,
    )


def build_band_records(band: str, *, documents: int = 4) -> tuple[TextRecord, ...]:
    if band not in BANDS:
        raise ValueError(f"unknown band: {band}")
    if documents < 2:
        raise ValueError("at least two independent documents are required")
    records: list[TextRecord] = []
    for doc_no in range(documents):
        doc_id = f"synthetic-{band}-doc-{doc_no:03d}"
        if band == "short_sentence":
            text = "耐磨防水"
            annotations = [
                TextAnnotation(0, 2, "attribute", "耐磨"),
                TextAnnotation(2, 4, "attribute", "防水"),
            ]
            records.append(_record(
                doc_id=doc_id, band=band, chunk_index=0, global_offset=0,
                text=text, annotations=annotations,
            ))
            continue

        sentence_count = {
            "long_sentence": 1,
            "long_document": 160,
            "ultra_long_context": 320,
        }[band]
        sentences = [_annotated_sentence(i)[0] for i in range(sentence_count)]
        # Keep model input bounded. Every chunk carries its source-document
        # identity and global character offset; groups remain document-disjoint.
        max_chunk_chars = 220
        chunk_text = ""
        chunk_annotations: list[TextAnnotation] = []
        chunk_start = 0
        chunk_index = 0
        document_offset = 0

        for sentence in sentences:
            if chunk_text and len(chunk_text) + len(sentence) > max_chunk_chars:
                records.append(_record(
                    doc_id=doc_id, band=band, chunk_index=chunk_index,
                    global_offset=chunk_start, text=chunk_text,
                    annotations=chunk_annotations,
                ))
                chunk_index += 1
                chunk_start = document_offset
                chunk_text = ""
                chunk_annotations = []

            local_start = len(chunk_text)
            for surface, dimension, value in (
                ("耐磨", "attribute", "耐磨"),
                ("防水", "attribute", "防水"),
                ("卡扣连接", "relation", "卡扣连接"),
                ("逐渐变化", "process", "逐渐变化"),
            ):
                pos = sentence.index(surface)
                chunk_annotations.append(TextAnnotation(
                    local_start + pos, local_start + pos + len(surface),
                    dimension, value, ("description",),
                ))
            chunk_text += sentence
            document_offset += len(sentence)

        if chunk_text:
            records.append(_record(
                doc_id=doc_id, band=band, chunk_index=chunk_index,
                global_offset=chunk_start, text=chunk_text,
                annotations=chunk_annotations,
            ))
    return tuple(records)


def train_all_bands(
    *, output_dir: str | Path | None = None, seed: int = 17,
) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    target_dir = Path(output_dir) if output_dir is not None else None
    if target_dir is not None:
        target_dir.mkdir(parents=True, exist_ok=True)

    for band in BANDS:
        records = build_band_records(band)
        model, report = train_and_evaluate(records, seed=seed)
        # The model has no cross-chunk memory. These are chunk-level scores,
        # and the document grouping is used only to prevent split leakage.
        lengths = [len(row.text) for row in records]
        report.update({
            "length_band": band,
            "synthetic_documents": len({row.group_id for row in records}),
            "source_chunks": len(records),
            "source_characters_total": sum(lengths),
            "chunk_characters_max": max(lengths),
            "global_offsets_recorded": True,
            "cross_chunk_memory": False,
            "metric_scope": "chunk_level_only",
            "data_origin": "synthetic_generated",
            "seed": seed,
        })
        if target_dir is not None:
            dataset_path = target_dir / f"{band}.json"
            payload = {
                "schema_version": 1,
                "examples": [
                    {
                        "observation_id": row.observation_id,
                        "subject_id": row.subject_id,
                        "domain": row.domain,
                        "source_id": row.source_id,
                        "text": row.text,
                        "context": list(row.context),
                        "group_id": row.group_id,
                        "annotations": [
                            {
                                "start_char": ann.start_char,
                                "end_char": ann.end_char,
                                "dimension": ann.dimension,
                                "value": ann.value,
                                "purposes": list(ann.purposes),
                            }
                            for ann in row.annotations
                        ],
                    }
                    for row in records
                ],
            }
            raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            dataset_path.write_text(raw, encoding="utf-8")
            report["dataset_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            report["dataset_path"] = str(dataset_path)
            report["checkpoint_sha256"] = model.save(target_dir / f"{band}.checkpoint.json")
            (target_dir / f"{band}.report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        reports[band] = report

    return {
        "format": "zhouyi-ai.classiang-multiscale-training-report",
        "schema_version": 1,
        "seed": seed,
        "bands": reports,
        "claim_boundary": (
            "Synthetic pipeline training only. Results validate data generation, "
            "group-disjoint chunk training, and checkpoint production; they do not "
            "establish real-world generalization, cross-chunk memory, or million-token "
            "reasoning. Real licensed and independently annotated corpora are still required."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="artifacts/classiang-multiscale")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    report = train_all_bands(output_dir=args.output_dir, seed=args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
