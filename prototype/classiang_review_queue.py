"""Evidence-preserving active review queue for Classiang text spans.

The queue ranks unreviewed spans for human annotation. Model suggestions are
never promoted to Gold labels and unannotated spans remain unknown.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from prototype.classiang_learning import (
    NONE_LABEL,
    TextRecord,
    TrainableTextEncoder,
    _candidate_spans,
    _validate_record,
    load_records,
)


def _digest(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_entropy(probabilities: dict[str, float]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    values = tuple(probabilities.values())
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("span scores must be finite and non-negative")
    total = sum(values)
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("span scores must have a positive finite sum")
    entropy = -sum(
        (value / total) * math.log(value / total)
        for value in values if value > 0.0
    )
    return min(1.0, max(0.0, entropy / math.log(len(values))))


def _validate_limit(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def build_review_queue(
    records: tuple[TextRecord, ...],
    model: TrainableTextEncoder,
    *,
    model_sha256: str,
    max_items: int = 200,
    max_per_domain: int = 50,
    max_per_group: int = 10,
    max_per_observation: int = 3,
    max_candidates_per_record: int = 5000,
    min_uncertainty: float = 0.0,
) -> dict[str, Any]:
    """Rank unreviewed text spans for independent human review.

    Exact spans already present in positive or reviewed-negative annotations
    are excluded. Partially overlapping spans remain eligible because they
    may expose boundary disagreements. Selection is deterministic and capped
    by domain, source group, and observation.

    Entropy and margins are model-relative ranking signals only. No predicted
    label is written back into training data.
    """
    for name, value in (
        ("max_items", max_items),
        ("max_per_domain", max_per_domain),
        ("max_per_group", max_per_group),
        ("max_per_observation", max_per_observation),
        ("max_candidates_per_record", max_candidates_per_record),
    ):
        _validate_limit(name, value)
    if (
        not isinstance(min_uncertainty, (int, float))
        or isinstance(min_uncertainty, bool)
        or not math.isfinite(min_uncertainty)
        or not 0.0 <= min_uncertainty <= 1.0
    ):
        raise ValueError("min_uncertainty must be between 0 and 1")
    if not isinstance(model, TrainableTextEncoder) or not model.classes:
        raise ValueError("a trained TrainableTextEncoder is required")
    if (
        not isinstance(model_sha256, str)
        or len(model_sha256) != 64
        or any(char not in "0123456789abcdef" for char in model_sha256.lower())
    ):
        raise ValueError("model_sha256 must be a 64-character hexadecimal digest")
    if not isinstance(records, tuple) or not records:
        raise ValueError("records must be a non-empty tuple")

    candidates: list[dict[str, Any]] = []
    skipped_records: list[dict[str, str]] = []
    candidate_spans_scored = 0
    span_budget = min(max_candidates_per_record, model.max_candidates)

    for record in records:
        _validate_record(record)
        reviewed_spans = {
            (annotation.start_char, annotation.end_char)
            for annotation in record.annotations
        } | set(record.negative_annotations)
        try:
            spans = _candidate_spans(
                record.text,
                max_tokens=model.max_tokens,
                max_span_chars=model.max_span_chars,
                max_candidates=span_budget,
            )
        except ValueError as exc:
            if str(exc) != "text span search budget exceeded":
                raise
            skipped_records.append({
                "observation_id": record.observation_id,
                "reason": "candidate_span_budget_exceeded",
            })
            continue

        group_key = record.group_id or record.subject_id
        for start, end in spans:
            if (start, end) in reviewed_spans:
                continue
            surface = record.text[start:end]
            probabilities = model.score_span(surface)
            if not probabilities:
                continue
            ranked = sorted(
                probabilities.items(), key=lambda item: (-item[1], item[0])
            )
            top_label, top_probability = ranked[0]
            second_probability = ranked[1][1] if len(ranked) > 1 else 0.0
            margin = max(0.0, top_probability - second_probability)
            entropy = _normalized_entropy(probabilities)
            if entropy < min_uncertainty:
                continue

            if top_label == NONE_LABEL:
                suggestion = None
            else:
                decoded = json.loads(top_label)
                if (
                    not isinstance(decoded, list)
                    or len(decoded) != 2
                    or not all(isinstance(part, str) for part in decoded)
                ):
                    raise ValueError("model emitted a malformed feature label")
                suggestion = {"dimension": decoded[0], "value": decoded[1]}

            evidence_ref = f"text:{record.source_id}:chars:{start}-{end}"
            identity = {
                "model_sha256": model_sha256.lower(),
                "observation_id": record.observation_id,
                "source_id": record.source_id,
                "start_char": start,
                "end_char": end,
                "surface": surface,
            }
            candidates.append({
                "review_item_id": _digest(identity),
                "observation_id": record.observation_id,
                "subject_id": record.subject_id,
                "domain": record.domain,
                "source_id": record.source_id,
                "group_id": group_key,
                "start_char": start,
                "end_char": end,
                "surface": surface,
                "evidence_ref": evidence_ref,
                "suggested_annotation": suggestion,
                "suggested_label": top_label,
                "class_scores": {
                    label: probabilities[label] for label in sorted(probabilities)
                },
                "top_score": top_probability,
                "runner_up_score": second_probability,
                "score_margin": margin,
                "normalized_entropy": entropy,
                "score_interpretation": "uncalibrated_model_relative_softmax",
                "review_status": "pending_review",
            })
            candidate_spans_scored += 1

    candidates.sort(key=lambda item: (
        -item["normalized_entropy"],
        item["score_margin"],
        item["domain"],
        item["group_id"],
        item["source_id"],
        item["observation_id"],
        item["start_char"],
        item["end_char"],
    ))

    selected: list[dict[str, Any]] = []
    domain_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    observation_counts: Counter[str] = Counter()
    for item in candidates:
        if len(selected) >= max_items:
            break
        if domain_counts[item["domain"]] >= max_per_domain:
            continue
        if group_counts[item["group_id"]] >= max_per_group:
            continue
        if observation_counts[item["observation_id"]] >= max_per_observation:
            continue
        selected.append(item)
        domain_counts[item["domain"]] += 1
        group_counts[item["group_id"]] += 1
        observation_counts[item["observation_id"]] += 1

    payload: dict[str, Any] = {
        "schema_version": 1,
        "model_sha256": model_sha256.lower(),
        "selection_policy": {
            "rank": "normalized_entropy_desc_then_score_margin_asc",
            "max_items": max_items,
            "max_per_domain": max_per_domain,
            "max_per_group": max_per_group,
            "max_per_observation": max_per_observation,
            "max_candidates_per_record": span_budget,
            "min_uncertainty": float(min_uncertainty),
            "exact_reviewed_spans_excluded": True,
            "overlapping_boundary_candidates_retained": True,
            "predictions_are_not_gold": True,
        },
        "candidate_spans_scored": candidate_spans_scored,
        "selected_count": len(selected),
        "skipped_records": skipped_records,
        "items": selected,
        "claim_boundary": (
            "Human-review queue only. Suggestions and softmax scores are "
            "uncalibrated model outputs; no label is automatically accepted, "
            "and unreviewed spans remain unknown."
        ),
    }
    payload["queue_sha256"] = _digest(payload)
    return payload


def write_review_queue(path: str | Path, queue: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-items", type=int, default=200)
    parser.add_argument("--max-per-domain", type=int, default=50)
    parser.add_argument("--max-per-group", type=int, default=10)
    parser.add_argument("--max-per-observation", type=int, default=3)
    parser.add_argument("--max-candidates-per-record", type=int, default=5000)
    parser.add_argument("--min-uncertainty", type=float, default=0.0)
    args = parser.parse_args(argv)

    model_bytes = args.checkpoint.read_bytes()
    model = TrainableTextEncoder.load(args.checkpoint)
    records = load_records(args.dataset)
    queue = build_review_queue(
        records,
        model,
        model_sha256=hashlib.sha256(model_bytes).hexdigest(),
        max_items=args.max_items,
        max_per_domain=args.max_per_domain,
        max_per_group=args.max_per_group,
        max_per_observation=args.max_per_observation,
        max_candidates_per_record=args.max_candidates_per_record,
        min_uncertainty=args.min_uncertainty,
    )
    write_review_queue(args.output, queue)
    print(json.dumps({
        "output": str(args.output),
        "queue_sha256": queue["queue_sha256"],
        "candidate_spans_scored": queue["candidate_spans_scored"],
        "selected_count": queue["selected_count"],
        "skipped_records": queue["skipped_records"],
        "claim_boundary": queue["claim_boundary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
