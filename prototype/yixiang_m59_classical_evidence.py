"""M59: provenance-first validation for classical yixiang evidence records.

This module validates source-grounded annotations. It does not create gold
labels, authenticate editions, or infer relations from text.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Mapping, Sequence

SCHEMA_VERSION = "m59-classical-evidence-v0.1"
SPLITS = ("train", "validation", "test")
WORK_PERIODS = ("pre_qing", "qing_and_after", "uncertain")
SOURCE_KINDS = ("primary_text", "critical_edition", "modern_commentary")
EVIDENCE_POLICIES = ("core_pre_qing", "variant_collation", "secondary_only")
CLAIM_STATUSES = ("explicit", "analogy", "metaphor", "commentarial", "research_hypothesis")
ANNOTATION_DECISIONS = ("accept", "reject", "uncertain")


def _require_text(value: Any, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)


def validate_record(record: Mapping[str, Any]) -> None:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported_schema_version")
    _require_text(record.get("record_id"), "record_id_required")
    source = record.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("source_required")
    for key in ("work_id", "title", "composition_period", "attribution",
                "work_lineage_group", "text_dependence_group"):
        _require_text(source.get(key), "source_" + key + "_required")
    if source.get("attribution_status") not in ("known", "traditional", "contested", "anonymous", "unknown"):
        raise ValueError("invalid_attribution_status")
    if source.get("work_period_class") not in WORK_PERIODS:
        raise ValueError("invalid_work_period_class")
    if source.get("source_kind") not in SOURCE_KINDS:
        raise ValueError("invalid_source_kind")
    policy = source.get("evidence_policy")
    if policy not in EVIDENCE_POLICIES:
        raise ValueError("invalid_evidence_policy")
    if policy == "core_pre_qing":
        if source["work_period_class"] != "pre_qing":
            raise ValueError("post_qing_or_uncertain_source_cannot_be_core")
        if source["source_kind"] == "modern_commentary":
            raise ValueError("commentary_cannot_be_core_primary_evidence")
    if source["source_kind"] == "modern_commentary" and policy != "secondary_only":
        raise ValueError("modern_commentary_must_be_secondary_only")

    witnesses = record.get("witnesses")
    if not isinstance(witnesses, list) or not witnesses:
        raise ValueError("at_least_one_witness_required")
    witness_by_id: Dict[str, Mapping[str, Any]] = {}
    for witness in witnesses:
        if not isinstance(witness, Mapping):
            raise ValueError("invalid_witness")
        for key in ("witness_id", "edition", "publisher", "publication_date",
                    "digitization_source", "access_date", "locator", "text"):
            _require_text(witness.get(key), "witness_" + key + "_required")
        if not isinstance(witness.get("variants"), list):
            raise ValueError("witness_variants_must_be_a_list")
        if witness.get("witness_period_class") not in WORK_PERIODS:
            raise ValueError("invalid_witness_period_class")
        witness_id = witness["witness_id"]
        if witness_id in witness_by_id:
            raise ValueError("duplicate_witness_id")
        witness_by_id[witness_id] = witness

    if policy == "core_pre_qing":
        if source["source_kind"] == "primary_text" and not any(
            witness["witness_period_class"] == "pre_qing"
            for witness in witness_by_id.values()
        ):
            raise ValueError("core_primary_text_requires_pre_qing_witness")
        if source["source_kind"] == "critical_edition":
            basis = source.get("basis_witness_ids")
            if not isinstance(basis, list) or not basis or not set(basis) <= set(witness_by_id):
                raise ValueError("critical_edition_requires_registered_basis_witnesses")
            if not any(witness_by_id[witness_id]["witness_period_class"] == "pre_qing"
                       for witness_id in basis):
                raise ValueError("critical_edition_requires_pre_qing_basis")

    spans = record.get("evidence_spans")
    if not isinstance(spans, list) or not spans:
        raise ValueError("evidence_spans_required")
    span_ids = set()
    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError("invalid_evidence_span")
        span_id = span.get("span_id")
        if not isinstance(span_id, str) or not span_id.strip() or span_id in span_ids:
            raise ValueError("invalid_or_duplicate_span_id")
        span_ids.add(span_id)
        witness_id = span.get("witness_id")
        if witness_id not in witness_by_id:
            raise ValueError("span_unknown_witness")
        start, end, quote = span.get("start"), span.get("end"), span.get("quote")
        if (not isinstance(start, int) or isinstance(start, bool)
                or not isinstance(end, int) or isinstance(end, bool)
                or start < 0 or end <= start):
            raise ValueError("invalid_span_offsets")
        text = witness_by_id[witness_id]["text"]
        if end > len(text) or text[start:end] != quote:
            raise ValueError("evidence_quote_offset_mismatch")

    claims = record.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims_required")
    claim_ids = set()
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise ValueError("invalid_claim")
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.strip() or claim_id in claim_ids:
            raise ValueError("invalid_or_duplicate_claim_id")
        claim_ids.add(claim_id)
        for key in ("subject_role", "predicate", "object_role"):
            _require_text(claim.get(key), "claim_" + key + "_required")
        if claim.get("claim_status") not in CLAIM_STATUSES:
            raise ValueError("invalid_claim_status")
        refs = claim.get("evidence_span_ids")
        if not isinstance(refs, list) or not refs or not set(refs) <= span_ids:
            raise ValueError("claim_evidence_span_missing_or_unknown")

    annotations = record.get("independent_annotations")
    if not isinstance(annotations, list) or len(annotations) < 2:
        raise ValueError("two_independent_annotations_required")
    annotators = set()
    for annotation in annotations:
        if not isinstance(annotation, Mapping):
            raise ValueError("invalid_annotation")
        annotator = annotation.get("annotator_id")
        if not isinstance(annotator, str) or not annotator.strip() or annotator in annotators:
            raise ValueError("annotators_must_be_distinct")
        annotators.add(annotator)
        decisions = annotation.get("decisions")
        if not isinstance(decisions, Mapping) or set(decisions) != claim_ids:
            raise ValueError("annotation_claim_coverage_mismatch")
        if any(value not in ANNOTATION_DECISIONS for value in decisions.values()):
            raise ValueError("invalid_annotation_decision")

    adjudication = record.get("adjudication")
    if not isinstance(adjudication, Mapping):
        raise ValueError("adjudication_required")
    status = adjudication.get("status")
    if status == "pending":
        if adjudication.get("decisions") not in (None, {}):
            raise ValueError("pending_adjudication_cannot_have_final_decisions")
    elif status == "adjudicated":
        _require_text(adjudication.get("adjudicator_id"), "adjudicator_required")
        decisions = adjudication.get("decisions")
        if not isinstance(decisions, Mapping) or set(decisions) != claim_ids:
            raise ValueError("adjudication_claim_coverage_mismatch")
        if any(value not in ANNOTATION_DECISIONS for value in decisions.values()):
            raise ValueError("invalid_adjudication_decision")
    else:
        raise ValueError("invalid_adjudication_status")

    if record.get("split") not in SPLITS:
        raise ValueError("invalid_split")


def validate_split_assignments(records: Sequence[Mapping[str, Any]]) -> None:
    """Prevent work/edition lineage or dependent texts crossing data splits."""
    group_splits: Dict[str, set] = defaultdict(set)
    for record in records:
        validate_record(record)
        source = record["source"]
        group_splits["work:" + source["work_lineage_group"]].add(record["split"])
        group_splits["text:" + source["text_dependence_group"]].add(record["split"])
    if any(len(splits) > 1 for splits in group_splits.values()):
        raise ValueError("source_or_text_dependence_group_crosses_splits")


def audit_corpus(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    ids = [record.get("record_id") for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_record_id")
    validate_split_assignments(records)
    period_counts = Counter(record["source"]["work_period_class"] for record in records)
    policy_counts = Counter(record["source"]["evidence_policy"] for record in records)
    split_counts = Counter(record["split"] for record in records)
    annotation_counts = [len(record["independent_annotations"]) for record in records]
    return {
        "records": len(records),
        "work_period_counts": dict(period_counts),
        "evidence_policy_counts": dict(policy_counts),
        "split_counts": {split: split_counts.get(split, 0) for split in SPLITS},
        "minimum_independent_annotations": min(annotation_counts, default=0),
        "all_evidence_spans_exact": True,
        "source_and_text_leakage_checked": True,
    }
