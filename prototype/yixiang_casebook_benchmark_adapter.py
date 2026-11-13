"""Convert classical casebooks into M8 pending-review cases without inventing gold labels."""
from __future__ import annotations
from collections.abc import Mapping, Sequence

from prototype.yixiang_benchmark import validate_dataset

FOCUS_TO_RELATION = {
    "category_membership": "structural",
    "predicate_preservation": "structural",
    "material_composition": "structural",
    "action_object_relation": "functional",
    "quantity_predicate": "structural",
    "observed_result": "empirical_correlation",
    "explanatory_warrant": "causal_analogy",
    "selected_example": "structural",
    "selection_warrant": "causal_analogy",
    "species_specific_diet": "functional",
    "life_cycle_condition": "temporal",
    "species_context": "situated",
    "substance_effect": "causal_analogy",
    "counterexample": "structural",
    "origin_relation": "process_mechanism",
    "property_inheritance": "functional",
    "agent_goal": "situated",
    "affordance": "functional",
    "posture": "situated",
    "geometry": "structural",
    "task_condition": "situated",
    "classification_boundary": "structural",
    "inference_scope": "structural",
    "non_overextension": "structural",
    "surface_appearance": "morphological",
    "inner_disposition": "symbolic_normative",
    "practice_or_method": "functional",
}

def _required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value.strip()

def convert_casebooks_to_pending_benchmark(casebooks: Sequence[Mapping]) -> list[dict]:
    """Create exploratory, unadjudicated M8 cases; these must never be scored as gold."""
    if not isinstance(casebooks, Sequence) or isinstance(casebooks, (str, bytes)) or not casebooks:
        raise ValueError("casebooks must be a non-empty sequence")
    output = []
    seen = set()
    for book in casebooks:
        if not isinstance(book, Mapping):
            raise ValueError("each casebook must be a mapping")
        book_id = _required_text(book.get("casebook_id"), "casebook_id")
        primary_text = _required_text(book.get("primary_text"), "primary_text")
        if not isinstance(book.get("cases"), list) or not book["cases"]:
            raise ValueError("casebook cases must be a non-empty list")
        for item in book["cases"]:
            if not isinstance(item, Mapping):
                raise ValueError("case entry must be a mapping")
            local_id = _required_text(item.get("case_id"), "case_id")
            case_id = f"m18:{book_id}:{local_id}"
            if case_id in seen:
                raise ValueError(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            passage = _required_text(item.get("passage"), "passage")
            source_ref = _required_text(item.get("source_ref"), "source_ref")
            note = _required_text(item.get("note"), "note")
            focus = item.get("audit_focus")
            if not isinstance(focus, list) or not focus or any(not isinstance(x, str) or not x.strip() for x in focus):
                raise ValueError("audit_focus must be a non-empty list of strings")
            unknown = sorted(set(focus) - set(FOCUS_TO_RELATION))
            if unknown:
                raise ValueError(f"unmapped audit_focus values: {unknown}")
            relations = sorted({FOCUS_TO_RELATION[x] for x in focus})
            output.append({
                "claim_kind": "argumentative_analogy",
                "case_id": case_id,
                "source_lineage": [f"casebook:{book_id}", source_ref],
                "source_status": "unverified_transcription",
                "target_claim": f"人工审查类推案例 {local_id}：{passage}",
                "relation_families": relations,
                "shared_basis": [],
                "non_shared_basis": [],
                "scope_conditions": [],
                "required_invariants": [],
                "known_counterexamples": [],
                "causal_status": "unknown",
                "evidence_refs": [f"casebook:{book_id}#{local_id}"],
                "independence_group": f"work:{primary_text}",
                "gold_decision": "abstain",
                "gold_rationale": f"PENDING REVIEW: {note} 当前仅为待审案例占位，不是人工裁决或 gold 标签。",
                "label_status": "pending_review",
                "reviewers": [],
                "split_group": "exploratory",
            })
    validate_dataset(output)
    return output