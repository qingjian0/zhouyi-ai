"""M66: multiple-instrument bounded-invalidity sets under linear moments.

For a selected vector Z of graph-screened instruments, regress D and Y on Z:
  gamma = Var(Z)^-1 Cov(Z,D)
  Gamma = Var(Z)^-1 Cov(Z,Y)
and impose |Gamma_j - beta*gamma_j| <= delta_j for each instrument.
The intersection is a sensitivity set for a linear structural coefficient.
It is not a finite-sample confidence set or a nonparametric ATE/LATE bound.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Mapping, Sequence

from prototype.yixiang_m60_causal_transfer import _decode, _d_separated, _graph_parts


def _has_directed_path(edges, source: str, target: str) -> bool:
    children: Dict[str, list[str]] = {}
    for left, right in edges:
        children.setdefault(left, []).append(right)
    pending = list(children.get(source, []))
    seen = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(children.get(node, []))
    return False


def _moments(joint: Mapping[str, float], variables: Sequence[str],
             names: Sequence[str], target: str):
    means = {name: 0.0 for name in [*names, target]}
    cross = {(a, b): 0.0 for a in names for b in [*names, target]}
    total = 0.0
    for key, probability in joint.items():
        if not isfinite(float(probability)) or probability < 0:
            raise ValueError("joint_probabilities_must_be_finite_nonnegative")
        assignment = _decode(key, variables)
        total += probability
        for name in means:
            means[name] += assignment[name] * probability
        for a in names:
            for b in [*names, target]:
                cross[(a, b)] += assignment[a] * assignment[b] * probability
    if abs(total - 1.0) > 1e-9:
        raise ValueError("joint_distribution_must_sum_to_one")
    covariance = {
        pair: value - means[pair[0]] * means[pair[1]]
        for pair, value in cross.items()
    }
    return covariance


def _solve(matrix, vector, tolerance: float = 1e-12):
    size = len(vector)
    augmented = [list(map(float, matrix[i])) + [float(vector[i])]
                 for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size),
                    key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= tolerance:
            raise ValueError("singular_instrument_covariance_matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][j] - factor * augmented[column][j]
                for j in range(size + 1)
            ]
    return [augmented[i][-1] for i in range(size)]


def _bounds_for_instruments(bound: float | Mapping[str, float],
                            instruments: Sequence[str]) -> Dict[str, float]:
    values = ({name: bound for name in instruments}
              if isinstance(bound, (int, float)) and not isinstance(bound, bool)
              else dict(bound) if isinstance(bound, Mapping) else None)
    if values is None:
        raise ValueError("violation_bound_must_be_number_or_mapping")
    result = {}
    for name in instruments:
        value = values.get(name)
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not isfinite(float(value)) or value < 0):
            raise ValueError("each_instrument_bound_must_be_finite_nonnegative")
        result[name] = float(value)
    return result


def bounded_multiple_iv_effect_set(
    case: Mapping[str, Any],
    reduced_form_violation_bound: float | Mapping[str, float],
    min_abs_conditional_first_stage: float = 1e-8,
) -> Dict[str, Any]:
    """Intersect per-instrument linear-moment restrictions for beta.

    The graph is a supplied-DAG assumption screen. Exclusion is deliberately
    relaxed: each selected instrument's reduced-form coefficient deviation
    from beta times its conditional first-stage coefficient is bounded.
    """
    if (not isinstance(min_abs_conditional_first_stage, (int, float))
            or isinstance(min_abs_conditional_first_stage, bool)
            or not isfinite(float(min_abs_conditional_first_stage))
            or min_abs_conditional_first_stage < 0):
        raise ValueError("first_stage_threshold_must_be_finite_nonnegative")

    nodes, edges, _, _ = _graph_parts(case)
    observed = list(case["observed_variables"])
    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    if len(set(nodes)) != len(nodes) or len(set(edges)) != len(edges):
        raise ValueError("duplicate_dag_node_or_edge")
    if any(a not in nodes or b not in nodes for a, b in edges):
        raise ValueError("dag_edge_references_unknown_node")
    if not {exposure, outcome} <= set(observed) or not set(observed) <= set(nodes):
        raise ValueError("query_variables_missing_from_observed_data")

    requested = case.get("instrument_candidates")
    if requested is None:
        requested = [name for name in observed if name not in (exposure, outcome)]
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("instrument_candidates_must_be_nonempty_and_unique")

    screened = []
    for instrument in requested:
        if instrument not in observed or instrument in (exposure, outcome):
            screened.append({"instrument": instrument, "status": "not_observed"})
            continue
        relevant = _has_directed_path(edges, instrument, exposure)
        backdoor_graph = [(a, b) for a, b in edges if a != instrument]
        exogenous = _d_separated(nodes, backdoor_graph, instrument, outcome, [])
        if relevant and exogenous:
            screened.append({"instrument": instrument, "status": "graph_exogeneity_relevance_supported"})
        else:
            screened.append({
                "instrument": instrument, "status": "excluded_by_graph_screen",
                "relevance_path": relevant,
                "no_open_backdoor_path_to_outcome": exogenous,
            })

    selected = [item["instrument"] for item in screened
                if item["status"] == "graph_exogeneity_relevance_supported"]
    if not selected:
        return {"status": "no_graph_screened_instruments", "identified_set": None,
                "instrument_screen": screened}

    bounds = _bounds_for_instruments(reduced_form_violation_bound, selected)
    moments = _moments(case["observational_joint"], observed, selected, exposure)
    outcome_moments = _moments(case["observational_joint"], observed, selected, outcome)
    covariance_matrix = [[moments[(left, right)] for right in selected]
                         for left in selected]
    exposure_covariances = [moments[(name, exposure)] for name in selected]
    outcome_covariances = [outcome_moments[(name, outcome)] for name in selected]
    try:
        first_stage = _solve(covariance_matrix, exposure_covariances)
        reduced_form = _solve(covariance_matrix, outcome_covariances)
    except ValueError as error:
        return {"status": str(error), "identified_set": None,
                "instruments": selected, "instrument_screen": screened}

    if any(abs(value) <= min_abs_conditional_first_stage for value in first_stage):
        return {
            "status": "weak_or_irrelevant_conditional_first_stage",
            "identified_set": None, "instruments": selected,
            "conditional_first_stage": dict(zip(selected, first_stage)),
            "instrument_screen": screened,
        }

    lower, upper = float("-inf"), float("inf")
    per_instrument = []
    for name, gamma, gamma_y in zip(selected, first_stage, reduced_form):
        delta = bounds[name]
        endpoints = ((gamma_y - delta) / gamma, (gamma_y + delta) / gamma)
        lo, hi = min(endpoints), max(endpoints)
        lower, upper = max(lower, lo), min(upper, hi)
        per_instrument.append({
            "instrument": name,
            "conditional_first_stage": gamma,
            "reduced_form_coefficient": gamma_y,
            "violation_bound": delta,
            "compatible_beta_interval": [lo, hi],
        })

    if lower > upper + 1e-10:
        return {
            "status": "incompatible_with_declared_violation_bounds",
            "identified_set": None, "per_instrument": per_instrument,
            "instrument_screen": screened,
        }
    if lower > upper:
        lower = upper = (lower + upper) / 2.0
    return {
        "status": "bounded_multiple_iv_effect_set_under_linear_moment_assumptions",
        "identified_set": [lower, upper],
        "instruments": selected,
        "conditional_first_stage": dict(zip(selected, first_stage)),
        "reduced_form_coefficients": dict(zip(selected, reduced_form)),
        "per_instrument": per_instrument,
        "assumptions": [
            "each_selected_instrument_is_exogenous_given_the_supplied_DAG",
            "instrument_covariance_matrix_is_nonsingular",
            "linear_reduced_form_projection_and_constant_structural_coefficient",
            "per_instrument_absolute_reduced_form_violation_bounds",
        ],
        "estimand": "linear_structural_coefficient_not_automatically_ATE_or_LATE",
        "instrument_screen": screened,
    }
