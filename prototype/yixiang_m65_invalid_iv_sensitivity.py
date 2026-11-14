"""M65: bounded-exclusion sensitivity intervals for a binary IV moment model.

This is a linear-moment sensitivity analysis, not a nonparametric ATE/LATE
bound. Instrument exogeneity and relevance remain explicit requirements.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Mapping, Sequence

from prototype.yixiang_m60_causal_transfer import _d_separated, _graph_parts
from prototype.yixiang_m64_instrumental_variable import _covariance, _has_directed_path


def infer_iv_exogeneity_and_relevance(
    case: Mapping[str, Any], instrument: str | None = None,
    min_abs_first_stage: float = 1e-8,
) -> Dict[str, Any]:
    """Check IV relevance and instrument-outcome backdoor separation, not exclusion."""
    nodes, edges, _, _ = _graph_parts(case)
    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    observed = list(case["observed_variables"])
    candidates = [instrument] if instrument else [
        name for name in observed if name not in (exposure, outcome)
    ]
    checked = []
    for candidate in candidates:
        if candidate not in observed or candidate in (exposure, outcome):
            continue
        relevance_path = _has_directed_path(edges, candidate, exposure)
        backdoor_graph = [(a, b) for a, b in edges if a != candidate]
        exogenous = _d_separated(nodes, backdoor_graph, candidate, outcome, [])
        first_stage = _covariance(
            case["observational_joint"], observed, candidate, exposure
        )
        valid = relevance_path and exogenous and abs(first_stage) > min_abs_first_stage
        checked.append({
            "instrument": candidate, "relevance_path": relevance_path,
            "no_open_backdoor_path_to_outcome": exogenous,
            "first_stage_covariance": first_stage,
            "status": "exogeneity_relevance_supported_by_dag" if valid
                      else "exogeneity_or_relevance_gate_failed",
        })
    valid = [item for item in checked
             if item["status"] == "exogeneity_relevance_supported_by_dag"]
    return {
        "valid": bool(valid), "candidate": valid[0]["instrument"] if valid else None,
        "candidates": checked,
    }


def bounded_exclusion_effect_set(
    case: Mapping[str, Any], direct_effect_bound: float,
    instrument: str | None = None, min_abs_first_stage: float = 1e-8,
) -> Dict[str, Any]:
    """Bound a linear IV coefficient when |direct Z→Y effect| <= delta.

    Moment model: Cov(Z,Y) = beta*Cov(Z,X) + gamma*Var(Z), |gamma| <= delta.
    The interval is a set for beta under this model, not a generic binary-outcome
    ATE or LATE interval.
    """
    if (not isinstance(direct_effect_bound, (int, float))
            or not isfinite(float(direct_effect_bound))
            or direct_effect_bound < 0):
        raise ValueError("direct_effect_bound_must_be_finite_nonnegative")
    check = infer_iv_exogeneity_and_relevance(
        case, instrument, min_abs_first_stage
    )
    if not check["valid"]:
        return {
            "status": "not_identified_by_exogeneity_relevance_gate",
            "identified_set": None, "sensitivity_parameter": direct_effect_bound,
            "identification": check,
        }
    selected = check["candidate"]
    observed = list(case["observed_variables"])
    exposure, outcome = case["query"]["exposure"], case["query"]["outcome"]
    first_stage = _covariance(
        case["observational_joint"], observed, selected, exposure
    )
    reduced_form = _covariance(
        case["observational_joint"], observed, selected, outcome
    )
    mean_z = sum(
        _decode(key, observed)[selected] * probability
        for key, probability in case["observational_joint"].items()
    )
    variance_z = mean_z * (1.0 - mean_z)
    if variance_z <= 0:
        return {
            "status": "instrument_variance_zero", "identified_set": None,
            "sensitivity_parameter": direct_effect_bound,
            "identification": check,
        }
    endpoints = (
        (reduced_form - direct_effect_bound * variance_z) / first_stage,
        (reduced_form + direct_effect_bound * variance_z) / first_stage,
    )
    lower, upper = min(endpoints), max(endpoints)
    return {
        "status": "bounded_effect_set_under_linear_moment_assumptions",
        "identified_set": [lower, upper],
        "sensitivity_parameter": direct_effect_bound,
        "instrument": selected,
        "first_stage_covariance": first_stage,
        "reduced_form_covariance": reduced_form,
        "instrument_variance": variance_z,
        "assumptions": [
            "instrument_outcome_exogeneity_given_the_supplied_DAG",
            "nonzero_population_first_stage",
            "linear_covariance_moment_model",
            "absolute_reduced_form_direct_effect_bounded_by_delta",
        ],
        "estimand": "linear_structural_coefficient_not_automatically_ATE_or_LATE",
        "identification": check,
    }
