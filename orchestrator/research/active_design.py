"""Deterministic, budget-aware selector for preregistered experiment candidates.

This module ranks caller-authored candidate designs. It does not invent
scientific claims, estimate information gain, or execute experiments.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

_ALLOWED_GATES = {"ood", "control", "replication", "parameter_match"}


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate design must be finite JSON data") from exc


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def design_next_experiment(
    *,
    hypothesis_id: str,
    required_gates: Sequence[str],
    candidates: Sequence[Mapping[str, Any]],
    compute_budget: float,
) -> dict[str, Any]:
    """Select the strongest feasible preregistered candidate by transparent rules.

    Candidate fields: candidate_id, hypothesis_id, covers, estimated_compute,
    expected_discrimination (caller-supplied 0..1), preregistration_ref,
    preregistered, and design (finite JSON object).

    Ranking is lexicographic: most uncovered gates covered, highest declared
    discrimination, lowest compute cost, then candidate_id. The score is not
    a learned probability or an automatically estimated information gain.
    """
    if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
        raise ValueError("hypothesis_id must be a non-empty string")
    budget = _finite(compute_budget, "compute_budget")
    if budget <= 0:
        raise ValueError("compute_budget must be positive")
    if not isinstance(required_gates, Sequence) or isinstance(required_gates, (str, bytes)) or not required_gates:
        raise ValueError("required_gates must be a non-empty sequence")
    gates = list(required_gates)
    if any(not isinstance(gate, str) or gate not in _ALLOWED_GATES for gate in gates):
        raise ValueError(f"required_gates must be drawn from {sorted(_ALLOWED_GATES)}")
    if len(set(gates)) != len(gates):
        raise ValueError("required_gates must be unique")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("candidates must be a sequence")

    seen_ids: set[str] = set()
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for index, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            raise ValueError(f"candidates[{index}] must be an object")
        required = {"candidate_id", "hypothesis_id", "covers", "estimated_compute",
                    "expected_discrimination", "preregistration_ref", "preregistered", "design"}
        if not required <= raw.keys():
            raise ValueError(f"candidates[{index}] is missing required fields")
        candidate_id = raw["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"candidates[{index}].candidate_id must be non-empty")
        if candidate_id in seen_ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        seen_ids.add(candidate_id)
        if raw["hypothesis_id"] != hypothesis_id:
            excluded.append({"candidate_id": candidate_id, "reason": "hypothesis_mismatch"})
            continue
        if not isinstance(raw["preregistered"], bool):
            raise ValueError(f"{candidate_id}: preregistered must be boolean")
        if not raw["preregistered"]:
            excluded.append({"candidate_id": candidate_id, "reason": "not_preregistered"})
            continue
        preregistration_ref = raw["preregistration_ref"]
        if not isinstance(preregistration_ref, str) or not preregistration_ref.strip():
            raise ValueError(f"{candidate_id}: preregistration_ref is required")
        covers = raw["covers"]
        if (not isinstance(covers, list) or not covers
                or any(not isinstance(gate, str) or gate not in _ALLOWED_GATES for gate in covers)
                or len(set(covers)) != len(covers)):
            raise ValueError(f"{candidate_id}: covers must be unique supported gate names")
        cost = _finite(raw["estimated_compute"], f"{candidate_id}.estimated_compute")
        discrimination = _finite(raw["expected_discrimination"], f"{candidate_id}.expected_discrimination")
        if cost < 0 or not 0.0 <= discrimination <= 1.0:
            raise ValueError(f"{candidate_id}: invalid cost or expected_discrimination")
        design = raw["design"]
        if not isinstance(design, Mapping):
            raise ValueError(f"{candidate_id}.design must be an object")
        _canonical(design)
        coverage = sorted(set(covers).intersection(gates))
        if not coverage:
            excluded.append({"candidate_id": candidate_id, "reason": "covers_no_required_gate"})
            continue
        if cost > budget:
            excluded.append({"candidate_id": candidate_id, "reason": "over_compute_budget"})
            continue
        eligible.append({
            "candidate_id": candidate_id,
            "covers": sorted(covers),
            "new_gate_coverage": coverage,
            "coverage_count": len(coverage),
            "estimated_compute": cost,
            "expected_discrimination": discrimination,
            "preregistration_ref": preregistration_ref,
            "design": dict(design),
        })

    input_digest = hashlib.sha256(_canonical({
        "hypothesis_id": hypothesis_id,
        "required_gates": gates,
        "compute_budget": budget,
        "candidates": list(candidates),
    })).hexdigest()
    if not eligible:
        return {
            "schema_version": 1, "status": "no_feasible_candidate",
            "hypothesis_id": hypothesis_id, "required_gates": gates,
            "compute_budget": budget, "selected": None,
            "excluded": excluded, "input_digest": input_digest,
            "limitations": [
                "No candidate was generated or inferred; the caller must author candidate designs.",
                "Expected discrimination is a caller-supplied heuristic, not a probability or measured information gain.",
                "Selection does not execute, preregister, or validate an experiment.",
            ],
        }

    eligible.sort(key=lambda item: (
        -item["coverage_count"],
        -item["expected_discrimination"],
        item["estimated_compute"],
        item["candidate_id"],
    ))
    selected = eligible[0]
    return {
        "schema_version": 1, "status": "selected",
        "hypothesis_id": hypothesis_id, "required_gates": gates,
        "compute_budget": budget,
        "selected": selected,
        "alternatives": eligible[1:],
        "excluded": excluded,
        "input_digest": input_digest,
        "limitations": [
            "Expected discrimination is supplied by the experiment author; it is not learned or calibrated here.",
            "The selector optimizes declared gate coverage before declared discrimination and compute cost.",
            "Selection does not execute, preregister, or validate an experiment.",
            "A human must review data leakage, controls, metric choice, power, and multiplicity before execution.",
        ],
    }
