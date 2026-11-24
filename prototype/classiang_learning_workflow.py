"""Integrated text-to-classiang learning workflow.

This composes the trainable text span encoder with the existing evidence-
grounded symbolic classiang cycle. Feedback remains explicitly reviewed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from prototype.classiang_learning import (
    TextAnnotation, TextRecord, TrainableTextEncoder, evaluate, load_records,
    train_and_evaluate,
)
from prototype.classiang_pipeline import (
    ClassiangCycleRequest, ClassiangCycleResult, run_classiang_cycle,
)
from prototype.classiang_engine import ClassExample, select_aspects
from prototype.classiang_discovery import DiscoveryResult, ObjectView, discover_classes


def load_reviewed_feedback(path: str | Path) -> tuple[TextRecord, ...]:
    """Load reviewed accept/correct/reject events as supervised records.

    Each event's record uses the same fields as one dataset example. A reject
    event must carry an empty annotation list and therefore becomes an explicit
    hard-negative document. Event IDs are unique and every source span is
    revalidated by the normal dataset loader.
    """
    target = Path(path)
    if not target.exists():
        return ()
    events = []
    seen = set()
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"feedback line {line_number} is invalid JSON") from exc
        if not isinstance(event, dict) or set(event) != {
            "event_id", "reviewer_id", "decision", "record"
        }:
            raise ValueError(f"feedback line {line_number} has invalid fields")
        event_id = event["event_id"]
        if not isinstance(event_id, str) or not event_id.strip() or event_id in seen:
            raise ValueError("feedback event IDs must be non-empty and unique")
        seen.add(event_id)
        if not isinstance(event["reviewer_id"], str) or not event["reviewer_id"].strip():
            raise ValueError("feedback reviewer_id must be non-empty")
        if event["decision"] not in {"accept", "correct", "reject"}:
            raise ValueError("feedback decision is invalid")
        record = event["record"]
        if not isinstance(record, dict):
            raise ValueError("feedback record must be an object")
        if event["decision"] == "reject" and record.get("annotations") != []:
            raise ValueError("rejected feedback must be an explicit empty-annotation record")
        events.append(record)
    if not events:
        return ()
    # Reuse the strict versioned dataset parser instead of duplicating offsets validation.
    payload = {"schema_version": 1, "examples": events}
    temporary = target.with_name(target.name + ".validated.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return load_records(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def cross_domain_evaluation(records: tuple[TextRecord, ...], *, threshold: float = 0.55):
    domains = sorted({row.domain for row in records})
    if len(domains) < 2:
        return {"status": "not_run", "reason": "at least two domains are required"}
    folds = []
    for held_out in domains:
        train = tuple(row for row in records if row.domain != held_out)
        test = tuple(row for row in records if row.domain == held_out)
        if not train or not test or not any(row.annotations for row in train):
            folds.append({"held_out_domain": held_out, "status": "not_run",
                          "reason": "training fold has no positive annotations"})
            continue
        model = TrainableTextEncoder().fit(train)
        folds.append({
            "held_out_domain": held_out, "status": "evaluated",
            "train_domains": sorted({row.domain for row in train}),
            "test": evaluate(model, test, threshold=threshold),
        })
    evaluated = [row for row in folds if row["status"] == "evaluated"]
    return {
        "status": "evaluated" if evaluated else "not_run",
        "fold_count": len(folds), "evaluated_folds": len(evaluated),
        "folds": folds,
    }


def train_deploy_workflow(
    dataset_path: str | Path,
    *,
    checkpoint_path: str | Path,
    report_path: str | Path,
    feedback_path: str | Path | None = None,
    seed: int = 17,
    validation_fraction: float = 0.2,
    threshold: float = 0.55,
):
    base = load_records(dataset_path)
    feedback = load_reviewed_feedback(feedback_path) if feedback_path else ()
    merged = base + feedback
    ids = [row.observation_id for row in merged]
    if len(ids) != len(set(ids)):
        raise ValueError("base dataset and feedback contain duplicate observation IDs")
    model, report = train_and_evaluate(
        merged, seed=seed, validation_fraction=validation_fraction,
        threshold=threshold,
    )
    report["feedback_records"] = len(feedback)
    report["cross_domain"] = cross_domain_evaluation(merged, threshold=threshold)
    report["dataset_sha256"] = hashlib.sha256(Path(dataset_path).read_bytes()).hexdigest()
    report["feedback_sha256"] = (
        hashlib.sha256(Path(feedback_path).read_bytes()).hexdigest()
        if feedback_path and Path(feedback_path).exists() else None
    )
    report["checkpoint_sha256"] = model.save(checkpoint_path)
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return model, report


def discover_text_classes(
    model: TrainableTextEncoder,
    records: tuple[TextRecord, ...],
    *,
    purpose: str,
    min_relevance: float = 0.5,
    min_support: float = 0.2,
    max_order: int = 3,
    max_candidate_evaluations: int = 10000,
) -> DiscoveryResult:
    """Turn model-proposed, evidence-grounded text features into unreviewed class candidates."""
    objects = []
    for row in records:
        observation = model.predict(
            observation_id=row.observation_id, subject_id=row.subject_id,
            domain=row.domain, source_id=row.source_id, text=row.text,
            context=row.context,
        )
        selected = select_aspects(
            observation, purpose=purpose, min_relevance=min_relevance,
        ).selected
        objects.append(ObjectView(
            object_id=row.observation_id, features=selected,
            evidence_refs=observation.evidence_refs,
        ))
    return discover_classes(
        tuple(objects), min_support=min_support, max_order=max_order,
        max_candidate_evaluations=max_candidate_evaluations,
    )


def run_text_classiang_cycle(
    model: TrainableTextEncoder,
    *,
    observation_id: str,
    subject_id: str,
    domain: str,
    source_id: str,
    text: str,
    class_id: str,
    purpose: str,
    validity_scope: str,
    positive_examples: tuple[ClassExample, ...],
    negative_examples: tuple[ClassExample, ...] = (),
    min_relevance: float = 0.5,
) -> ClassiangCycleResult:
    """Infer evidence-grounded text features, then run the existing symbolic cycle."""
    observation = model.predict(
        observation_id=observation_id, subject_id=subject_id, domain=domain,
        source_id=source_id, text=text,
    )
    request = ClassiangCycleRequest(
        class_id=class_id, purpose=purpose, validity_scope=validity_scope,
        query_observation=observation, positive_examples=positive_examples,
        negative_examples=negative_examples, min_relevance=min_relevance,
    )
    return run_classiang_cycle(request)
