"""M64: graph-screened binary instrumental-variable identification diagnostics.

The module reports a Wald estimand and labels it as a LATE only when
monotonicity is explicitly declared. Graph validity is conditional on the
supplied fully specified DAG; it is not inferred from observational data.
"""
from __future__ import annotations

from itertools import product
from typing import Any, Dict, Mapping, Sequence, Tuple

from prototype.yixiang_m60_causal_transfer import (
    _decode, _d_separated, _graph_parts, enumerate_joint,
)


def _has_directed_path(edges: Sequence[Tuple[str, str]],
                       source: str, target: str) -> bool:
    children: Dict[str, list[str]] = {}
    for left, right in edges:
        children.setdefault(left, []).append(right)
    pending = list(children.get(source, []))
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in visited:
            visited.add(node)
            pending.extend(children.get(node, []))
    return False


def _all_directed_paths_pass_through(edges: Sequence[Tuple[str, str]],
                                     source: str, target: str,
                                     required: str) -> bool:
    """True iff no directed source→target path can avoid required."""
    children: Dict[str, list[str]] = {}
    for left, right in edges:
        children.setdefault(left, []).append(right)
    pending = list(children.get(source, []))
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == required or node in visited:
            continue
        if node == target:
            return False
        visited.add(node)
        pending.extend(children.get(node, []))
    return True


def _covariance(joint: Mapping[str, float], variables: Sequence[str],
                left: str, right: str) -> float:
    mean_left = mean_right = cross = 0.0
    decoded = []
    for key, probability in joint.items():
        assignment = _decode(key, variables)
        decoded.append((assignment, probability))
        mean_left += assignment[left] * probability
        mean_right += assignment[right] * probability
        cross += assignment[left] * assignment[right] * probability
    return cross - mean_left * mean_right


def infer_iv_instrument(case: Mapping[str, Any], instrument: str | None = None,
                        min_abs_first_stage: float = 1e-8) -> Dict[str, Any]:
    """Check graphical IV exclusion/exogeneity and observed population relevance."""
    nodes, edges, _, _ = _graph_parts(case)
    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    observed = list(case["observed_variables"])
    if len(set(nodes)) != len(nodes) or len(set(edges)) != len(edges):
        raise ValueError("duplicate_dag_node_or_edge")
    if any(a not in nodes or b not in nodes for a, b in edges):
        raise ValueError("dag_edge_references_unknown_node")
    if not {exposure, outcome} <= set(observed) or not set(observed) <= set(nodes):
        raise ValueError("query_variables_missing_from_observed_data")
    candidates = [instrument] if instrument else [
        node for node in observed if node not in (exposure, outcome)
    ]
    results = []
    for candidate in candidates:
        if candidate not in observed or candidate in (exposure, outcome):
            continue
        relevant = _has_directed_path(edges, candidate, exposure)
        exclusion = _all_directed_paths_pass_through(
            edges, candidate, outcome, exposure
        )
        # Delete outgoing instrument edges: remaining Z-Y paths are back-door paths.
        backdoor_graph = [(a, b) for a, b in edges if a != candidate]
        exogenous = _d_separated(nodes, backdoor_graph, candidate, outcome, [])
        first_stage = _covariance(
            case["observational_joint"], observed, candidate, exposure
        )
        graph_valid = relevant and exclusion and exogenous
        if not graph_valid:
            status = "invalid_instrument_graph"
        elif abs(first_stage) <= min_abs_first_stage:
            status = "irrelevant_instrument"
        else:
            status = "valid_iv_candidate"
        results.append({
            "instrument": candidate,
            "status": status,
            "graph_valid": graph_valid,
            "relevance_path": relevant,
            "exclusion_restriction_graphically_supported": exclusion,
            "no_open_backdoor_path_to_outcome": exogenous,
            "first_stage_covariance": first_stage,
        })
    valid = [item for item in results if item["status"] == "valid_iv_candidate"]
    if valid:
        return {"iv_identified": True, "reason": "valid_graphical_iv_candidate",
                "candidate": valid[0]["instrument"], "candidates": results}
    return {"iv_identified": False, "reason": "no_valid_relevant_iv_candidate",
            "candidate": None, "candidates": results}


def estimate_wald_iv(case: Mapping[str, Any], instrument: str | None = None,
                     min_abs_first_stage: float = 1e-8) -> Dict[str, Any]:
    """Compute the exact-population Wald ratio; call it LATE only with monotonicity."""
    check = infer_iv_instrument(case, instrument, min_abs_first_stage)
    if not check["iv_identified"]:
        return {"status": "not_identified_by_graphical_iv", "estimate": None,
                "identification": check}
    selected = check["candidate"]
    observed = list(case["observed_variables"])
    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    first_stage = _covariance(
        case["observational_joint"], observed, selected, exposure
    )
    reduced_form = _covariance(
        case["observational_joint"], observed, selected, outcome
    )
    if abs(first_stage) <= min_abs_first_stage:
        return {"status": "weak_or_irrelevant_instrument", "estimate": None,
                "identification": check}
    ratio = reduced_form / first_stage
    if case.get("assumptions", {}).get("monotonicity") is True:
        status = "identified_late_under_declared_assumptions"
        interpretation = "LATE_for_compliers_not_population_ATE"
    else:
        status = "wald_ratio_monotonicity_unasserted"
        interpretation = "Wald_ratio_not_automatically_LATE_or_ATE"
    return {
        "status": status, "estimate": ratio, "estimand": interpretation,
        "instrument": selected, "first_stage_covariance": first_stage,
        "reduced_form_covariance": reduced_form, "identification": check,
    }


def _make_case(case_id: str, scm: Mapping[str, Any], assumptions=None):
    full = enumerate_joint(scm)
    order = list(scm["topological_order"])
    observed = list(scm["observed_variables"])
    joint: Dict[str, float] = {}
    for key, probability in full.items():
        assignment = _decode(key, order)
        observed_key = ",".join(str(assignment[name]) for name in observed)
        joint[observed_key] = joint.get(observed_key, 0.0) + probability
    return {
        "case_id": case_id,
        "dag": {"nodes": list(scm["nodes"]),
                "edges": [list(edge) for edge in scm["edges"]]},
        "observed_variables": observed,
        "query": {"instrument": "Z", "exposure": "X", "outcome": "Y"},
        "observational_joint": joint,
        "assumptions": assumptions or {},
    }


def generate_iv_cases():
    """Return valid, exclusion-violating, confounded, and weak-IV exact SCMs."""
    valid = {
        "topological_order": ["Z", "U", "X", "Y"],
        "nodes": {
            "Z": {"parents": [], "p1": 0.5},
            "U": {"parents": [], "p1": 0.5},
            "X": {"parents": ["Z", "U"], "cpt": {
                "0,0": 0.0, "0,1": 1.0, "1,0": 1.0, "1,1": 1.0}},
            "Y": {"parents": ["X", "U"], "cpt": {
                "0,0": 0.1, "1,0": 0.5, "0,1": 0.3, "1,1": 0.9}},
        },
        "edges": [("Z", "X"), ("U", "X"), ("U", "Y"), ("X", "Y")],
        "observed_variables": ["Z", "X", "Y"],
    }
    direct = {
        **valid,
        "topological_order": ["Z", "U", "X", "Y"],
        "nodes": {
            **valid["nodes"],
            "Y": {"parents": ["X", "U", "Z"], "cpt": {
                "0,0,0": 0.1, "1,0,0": 0.5, "0,1,0": 0.3, "1,1,0": 0.9,
                "0,0,1": 0.2, "1,0,1": 0.6, "0,1,1": 0.4, "1,1,1": 0.95}},
        },
        "edges": [("Z", "X"), ("Z", "Y"), ("U", "X"), ("U", "Y"), ("X", "Y")],
    }
    confounded = {
        **valid,
        "nodes": {
            **valid["nodes"],
            "Z": {"parents": ["U"], "cpt": {"0": 0.2, "1": 0.8}},
        },
        "edges": [("U", "Z"), ("Z", "X"), ("U", "X"), ("U", "Y"), ("X", "Y")],
    }
    weak = {
        "topological_order": ["Z", "X", "Y"],
        "nodes": {
            "Z": {"parents": [], "p1": 0.5},
            "X": {"parents": ["Z"], "cpt": {"0": 0.5, "1": 0.505}},
            "Y": {"parents": ["X"], "cpt": {"0": 0.1, "1": 0.6}},
        },
        "edges": [("Z", "X"), ("X", "Y")],
        "observed_variables": ["Z", "X", "Y"],
    }
    return {
        "valid_latent_confounding": _make_case(
            "valid_latent_confounding", valid, {"monotonicity": True}),
        "exclusion_violation": _make_case("exclusion_violation", direct),
        "instrument_confounding": _make_case("instrument_confounding", confounded),
        "weak_instrument": _make_case("weak_instrument", weak, {"monotonicity": True}),
    }
