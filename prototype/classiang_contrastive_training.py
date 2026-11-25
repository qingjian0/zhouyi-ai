"""Deterministic synthetic smoke training for the reviewed-negative contrastive learner.

This fixture verifies the training and artifact path only; it is not a semantic
Gold dataset and must not be reported as real-world generalization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from prototype.classiang_learning import TextAnnotation, TextRecord
from prototype.classiang_contrastive import train_contrastive


def build_records(count: int = 12) -> tuple[TextRecord, ...]:
    rows = []
    for index in range(count):
        text = f"Device{index} transfers water; reference code R{index}."
        positive = "transfers water"
        negative = "reference code"
        start = text.index(positive)
        neg_start = text.index(negative)
        rows.append(TextRecord(
            observation_id=f"contrastive-smoke-{index:03d}",
            subject_id=f"device-{index:03d}",
            domain="mechanical" if index % 2 == 0 else "infrastructure",
            source_id=f"synthetic-source-{index:03d}",
            text=text,
            annotations=(TextAnnotation(
                start, start + len(positive), "function", "transfers-water",
                ("recognition",),
            ),),
            context=("data_origin=synthetic_generated",),
            group_id=f"synthetic-source-family-{index:03d}",
            negative_annotations=((neg_start, neg_start + len(negative)),),
        ))
    return tuple(rows)


def train_smoke(output_dir: str | Path, seed: int = 17) -> dict:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    records = build_records()
    dataset = {
        "schema_version": 1,
        "examples": [
            {
                "observation_id": row.observation_id,
                "subject_id": row.subject_id,
                "domain": row.domain,
                "source_id": row.source_id,
                "group_id": row.group_id,
                "text": row.text,
                "context": list(row.context),
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
                "negative_annotations": [
                    {"start_char": start, "end_char": end}
                    for start, end in row.negative_annotations
                ],
            }
            for row in records
        ],
    }
    dataset_raw = json.dumps(dataset, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    dataset_path = target / "contrastive-reviewed-negative-smoke.json"
    dataset_path.write_text(dataset_raw, encoding="utf-8")
    model, report = train_contrastive(records, seed=seed, threshold=0.2)
    checkpoint_sha = model.save(target / "contrastive-reviewed-negative-smoke.checkpoint.json")
    report.update({
        "data_origin": "synthetic_generated",
        "claim_boundary": "Pipeline smoke training only; not real semantic generalization.",
        "dataset_path": str(dataset_path),
        "dataset_sha256": hashlib.sha256(dataset_raw.encode("utf-8")).hexdigest(),
        "checkpoint_sha256": checkpoint_sha,
        "reviewed_negative_annotations": sum(len(row.negative_annotations) for row in records),
        "unannotated_text_treated_as_negative": False,
    })
    (target / "contrastive-reviewed-negative-smoke.report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="artifacts/classiang-contrastive")
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    report = train_smoke(args.output_dir, args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
