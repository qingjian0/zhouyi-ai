"""Conservative, deterministic evaluation of preregistered research evidence."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any

_REQUIRED = {"evidence_id", "split", "control", "effect_mean", "ci_lower", "ci_upper", "seeds", "valid", "preregistered"}

def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite number")
    return result

def evaluate_evidence(*, predicted_direction: str, evidence: Sequence[Mapping[str, Any]], min_seeds: int = 10) -> dict[str, Any]:
    """Evaluate supplied confidence intervals; this function does not perform inference."""
    if not isinstance(predicted_direction, str) or predicted_direction not in {"positive", "negative"}:
        raise ValueError("predicted_direction must be positive or negative")
    if isinstance(min_seeds, bool) or not isinstance(min_seeds, int) or min_seeds < 2:
        raise ValueError("min_seeds must be an integer >= 2")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        raise ValueError("evidence must be a sequence of records")
    rows, seen = [], set()
    for index, raw in enumerate(evidence):
        if not isinstance(raw, Mapping) or not _REQUIRED <= raw.keys():
            raise ValueError(f"evidence[{index}] is missing required fields")
        evidence_id = raw["evidence_id"]
        if not isinstance(evidence_id, str) or not evidence_id.strip() or evidence_id in seen:
            raise ValueError("evidence_id values must be unique non-empty strings")
        seen.add(evidence_id)
        if not isinstance(raw["split"], str) or raw["split"] not in {"iid", "ood"}:
            raise ValueError(f"{evidence_id}: split must be iid or ood")
        if not isinstance(raw["control"], str) or raw["control"] not in {"none", "shuffled", "random"}:
            raise ValueError(f"{evidence_id}: unsupported control")
        if not isinstance(raw["valid"], bool) or not isinstance(raw["preregistered"], bool):
            raise ValueError(f"{evidence_id}: valid and preregistered must be booleans")
        seeds = raw["seeds"]
        if isinstance(seeds, bool) or not isinstance(seeds, int) or seeds < 0:
            raise ValueError(f"{evidence_id}: seeds must be a non-negative integer")
        mean = _finite_number(raw["effect_mean"], "effect_mean")
        lower = _finite_number(raw["ci_lower"], "ci_lower")
        upper = _finite_number(raw["ci_upper"], "ci_upper")
        if lower > upper or not lower <= mean <= upper:
            raise ValueError(f"{evidence_id}: expected ci_lower <= effect_mean <= ci_upper")
        if not raw["valid"] or not raw["preregistered"] or seeds < min_seeds:
            status = "excluded"
            reason = "invalid" if not raw["valid"] else "not_preregistered" if not raw["preregistered"] else "insufficient_seeds"
        elif predicted_direction == "positive":
            status = "favorable" if lower > 0 else "adverse" if upper < 0 else "uncertain"
            reason = "confidence_interval"
        else:
            status = "favorable" if upper < 0 else "adverse" if lower > 0 else "uncertain"
            reason = "confidence_interval"
        rows.append({"evidence_id": evidence_id, "split": raw["split"], "control": raw["control"], "seeds": seeds, "status": status, "reason": reason})
    eligible = [row for row in rows if row["status"] != "excluded"]
    ood = [row for row in eligible if row["split"] == "ood"]
    controls = [row for row in eligible if row["control"] in {"shuffled", "random"}]
    favorable_ood_ids = {row["evidence_id"] for row in ood if row["status"] == "favorable"}
    adverse_ood = any(row["status"] == "adverse" for row in ood)
    favorable_control_ids = {row["evidence_id"] for row in controls if row["status"] == "favorable"}
    adverse_control = any(row["status"] == "adverse" for row in controls)
    # Require two distinct evidence rows; one row cannot satisfy both gates.
    independent_support = any(ood_id != control_id
                              for ood_id in favorable_ood_ids
                              for control_id in favorable_control_ids)
    verdict = "rejected" if adverse_ood or adverse_control else "supported" if independent_support else "inconclusive"
    return {
        "schema_version": 1, "verdict": verdict,
        "gates": {"ood_favorable": bool(favorable_ood_ids), "ood_adverse": adverse_ood, "control_favorable": bool(favorable_control_ids), "control_adverse": adverse_control, "independent_support_rows": independent_support, "has_eligible_ood": bool(ood), "has_eligible_control": bool(controls)},
        "evidence": rows,
        "limitations": [
            "Confidence intervals are accepted as supplied; this module does not calculate or validate their statistical method.",
            "Support requires favorable OOD and favorable shuffled/random-control evidence from two distinct evidence rows.",
            "This rule gate is not a substitute for multiplicity correction, power analysis, or expert review.",
        ],
    }
