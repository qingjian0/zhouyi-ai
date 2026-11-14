"""M60: exact-distribution causal identification and intervention controls.

A small binary-SCM diagnostic. Public cases expose a DAG and observed joint
distribution, but not structural equations or evaluator ATE labels.
"""
from __future__ import annotations

from itertools import product
from typing import Any, Dict, Mapping, Sequence, Tuple

SCHEMA_VERSION = "m60-causal-case-v0.1"


def _key(values: Sequence[int]) -> str:
    return ",".join(str(value) for value in values)


def _decode(key: str, variables: Sequence[str]) -> Dict[str, int]:
    values = [int(value) for value in key.split(",")]
    if len(values) != len(variables):
        raise ValueError("joint_assignment_width_mismatch")
    return dict(zip(variables, values))


def enumerate_joint(scm: Mapping[str, Any],
                    intervention: Mapping[str, int] | None = None) -> Dict[str, float]:
    """Enumerate a finite binary SCM exactly, optionally applying do(.) values."""
    nodes = scm["nodes"]
    order = list(scm["topological_order"])
    intervention = dict(intervention or {})
    if not set(intervention) <= set(nodes) or any(v not in (0, 1) for v in intervention.values()):
        raise ValueError("invalid_intervention")
    distribution: Dict[str, float] = {}
    for values in product((0, 1), repeat=len(order)):
        assignment = dict(zip(order, values))
        probability = 1.0
        for variable in order:
            if variable in intervention:
                probability *= 1.0 if assignment[variable] == intervention[variable] else 0.0
                continue
            node = nodes[variable]
            parents = node["parents"]
            if parents:
                probability_one = node["cpt"][_key([assignment[p] for p in parents])]
            else:
                probability_one = node["p1"]
            probability *= probability_one if assignment[variable] else (1.0 - probability_one)
        if probability:
            distribution[_key(values)] = probability
    return distribution


def _observed_joint(scm: Mapping[str, Any]) -> Dict[str, float]:
    full = enumerate_joint(scm)
    full_order = list(scm["topological_order"])
    observed = list(scm["observed_variables"])
    totals: Dict[str, float] = {}
    for key, probability in full.items():
        assignment = _decode(key, full_order)
        observed_key = _key([assignment[v] for v in observed])
        totals[observed_key] = totals.get(observed_key, 0.0) + probability
    return totals


def _conditional_mean(joint: Mapping[str, float], variables: Sequence[str],
                      outcome: str, exposure: str, exposure_value: int,
                      condition: Mapping[str, int]) -> float | None:
    mass = outcome_mass = 0.0
    for key, probability in joint.items():
        assignment = _decode(key, variables)
        if assignment[exposure] != exposure_value:
            continue
        if any(assignment[var] != value for var, value in condition.items()):
            continue
        mass += probability
        outcome_mass += probability * assignment[outcome]
    return outcome_mass / mass if mass > 0 else None


def observational_difference(case: Mapping[str, Any]) -> float | None:
    query = case["query"]
    variables = case["observed_variables"]
    joint = case["observational_joint"]
    mean_one = _conditional_mean(joint, variables, query["outcome"],
                                 query["exposure"], 1, {})
    mean_zero = _conditional_mean(joint, variables, query["outcome"],
                                  query["exposure"], 0, {})
    return None if mean_one is None or mean_zero is None else mean_one - mean_zero


def backdoor_adjusted_effect(case: Mapping[str, Any],
                             adjustment_set: Sequence[str]) -> float | None:
    query = case["query"]
    variables = case["observed_variables"]
    exposure, outcome = query["exposure"], query["outcome"]
    joint = case["observational_joint"]
    adjustment = list(adjustment_set)
    if exposure in adjustment or outcome in adjustment or not set(adjustment) <= set(variables):
        raise ValueError("invalid_adjustment_set")
    effect = 0.0
    strata = list(product((0, 1), repeat=len(adjustment)))
    for values in strata:
        condition = dict(zip(adjustment, values))
        stratum_mass = sum(
            probability for key, probability in joint.items()
            if all(_decode(key, variables)[var] == value
                   for var, value in condition.items())
        )
        if stratum_mass == 0:
            continue
        mean_one = _conditional_mean(joint, variables, outcome, exposure, 1, condition)
        mean_zero = _conditional_mean(joint, variables, outcome, exposure, 0, condition)
        if mean_one is None or mean_zero is None:
            return None
        effect += stratum_mass * (mean_one - mean_zero)
    return effect


def _graph_parts(case: Mapping[str, Any]):
    nodes = list(case["dag"]["nodes"])
    edges = [(source, target) for source, target in case["dag"]["edges"]]
    if len(set(nodes)) != len(nodes) or any(
        source not in nodes or target not in nodes for source, target in edges
    ):
        raise ValueError("invalid_dag_nodes_or_edges")
    if len(set(edges)) != len(edges):
        raise ValueError("duplicate_dag_edge")
    parents = {node: set() for node in nodes}
    children = {node: set() for node in nodes}
    for source, target in edges:
        parents[target].add(source)
        children[source].add(target)
    return nodes, edges, parents, children


def _descendants(node: str, children: Mapping[str, set[str]]) -> set[str]:
    found: set[str] = set()
    pending = list(children[node])
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(children[current])
    return found


def _d_separated(nodes: Sequence[str], edges: Sequence[Tuple[str, str]],
                 left: str, right: str, conditioned: Sequence[str]) -> bool:
    """Pearl d-separation via ancestral moralization."""
    conditioned_set = set(conditioned)
    if left in conditioned_set or right in conditioned_set:
        return False
    parents = {node: set() for node in nodes}
    children = {node: set() for node in nodes}
    for source, target in edges:
        parents[target].add(source)
        children[source].add(target)
    relevant = {left, right} | conditioned_set
    ancestors = set(relevant)
    pending = list(relevant)
    while pending:
        current = pending.pop()
        for parent in parents[current]:
            if parent not in ancestors:
                ancestors.add(parent)
                pending.append(parent)
    moral = {node: set() for node in ancestors}
    for child in ancestors:
        ancestral_parents = parents[child] & ancestors
        for parent in ancestral_parents:
            moral[parent].add(child)
            moral[child].add(parent)
        for first in ancestral_parents:
            for second in ancestral_parents:
                if first != second:
                    moral[first].add(second)
    for node in conditioned_set:
        moral.pop(node, None)
    for neighbors in moral.values():
        neighbors.difference_update(conditioned_set)
    if left not in moral or right not in moral:
        return True
    visited = {left}
    pending = [left]
    while pending:
        current = pending.pop()
        if current == right:
            return False
        for neighbor in moral[current] - visited:
            visited.add(neighbor)
            pending.append(neighbor)
    return True


def _valid_backdoor_adjustment(case: Mapping[str, Any],
                               adjustment: Sequence[str]) -> bool:
    nodes, edges, parents, children = _graph_parts(case)
    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    observed = set(case["observed_variables"])
    adjustment_set = set(adjustment)
    if (len(adjustment_set) != len(adjustment)
            or not adjustment_set <= observed
            or exposure in adjustment_set or outcome in adjustment_set):
        return False
    # The adjustment set must not contain descendants of the treatment.
    if adjustment_set & _descendants(exposure, children):
        return False
    # Back-door graph G_{̅X}: remove all outgoing edges from treatment.
    backdoor_edges = [(source, target) for source, target in edges
                      if source != exposure]
    return _d_separated(nodes, backdoor_edges, exposure, outcome, adjustment)


def infer_backdoor_set(case: Mapping[str, Any]) -> Dict[str, Any]:
    """Find a minimum observed valid adjustment set using DAG d-separation.

    This implements the sufficient back-door criterion for a fully specified
    DAG, not general do-calculus or all possible identification strategies.
    Hidden nodes remain in the graph but cannot be selected for adjustment.
    """
    from itertools import combinations

    exposure = case["query"]["exposure"]
    outcome = case["query"]["outcome"]
    nodes, edges, parents, children = _graph_parts(case)
    observed = list(case["observed_variables"])
    if exposure not in observed or outcome not in nodes or exposure not in nodes:
        raise ValueError("query_variables_missing_from_dag")
    candidates = [node for node in observed
                  if node not in (exposure, outcome)
                  and node not in _descendants(exposure, children)]
    if len(candidates) > 18:
        return {"identified": False, "reason": "adjustment_search_budget_exceeded",
                "latent_parents": [], "adjustment_set": []}
    for size in range(len(candidates) + 1):
        for adjustment in combinations(candidates, size):
            if _valid_backdoor_adjustment(case, adjustment):
                return {"identified": True, "reason": "valid_backdoor_adjustment",
                        "latent_parents": [], "adjustment_set": list(adjustment)}
    return {"identified": False, "reason": "no_observed_backdoor_adjustment_set",
            "latent_parents": [], "adjustment_set": []}


def predict(case: Mapping[str, Any], method: str = "graph_backdoor") -> Dict[str, Any]:
    if method == "naive_observational":
        estimate = observational_difference(case)
        return {"case_id": case["case_id"], "status": "identified",
                "estimate": estimate, "adjustment_set": [], "method": method}
    if method == "all_observed_adjustment":
        adjustment = [v for v in case["observed_variables"]
                      if v not in (case["query"]["exposure"], case["query"]["outcome"])]
        estimate = backdoor_adjusted_effect(case, adjustment)
        return {"case_id": case["case_id"], "status": "identified",
                "estimate": estimate, "adjustment_set": adjustment, "method": method}
    if method != "graph_backdoor":
        raise ValueError("unknown_causal_baseline")
    result = infer_backdoor_set(case)
    if not result["identified"]:
        return {"case_id": case["case_id"], "status": "not_identifiable",
                "estimate": None, "adjustment_set": [], "reason": result["reason"],
                "method": method}
    estimate = backdoor_adjusted_effect(case, result["adjustment_set"])
    if estimate is None:
        return {"case_id": case["case_id"], "status": "not_identifiable",
                "estimate": None, "adjustment_set": result["adjustment_set"],
                "reason": "positivity_failure", "method": method}
    return {"case_id": case["case_id"], "status": "identified",
            "estimate": estimate, "adjustment_set": result["adjustment_set"],
            "method": method}


def _make_case(case_id: str, scm: Mapping[str, Any], exposure: str,
               outcome: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    full_joint = enumerate_joint(scm)
    observed = list(scm["observed_variables"])
    joint = _observed_joint(scm)
    do_one = enumerate_joint(scm, {exposure: 1})
    do_zero = enumerate_joint(scm, {exposure: 0})
    order = list(scm["topological_order"])
    def p_y_one(distribution: Mapping[str, float]) -> float:
        return sum(prob for key, prob in distribution.items()
                   if _decode(key, order)[outcome] == 1)
    truth = {"ate": p_y_one(do_one) - p_y_one(do_zero)}
    public = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "dag": {"nodes": list(scm["nodes"]), "edges": [list(e) for e in scm["edges"]]},
        "observed_variables": observed,
        "query": {"exposure": exposure, "outcome": outcome, "estimand": "total_effect"},
        "observational_joint": joint,
    }
    truth["identifiable"] = infer_backdoor_set(public)["identified"]
    return public, truth


def generate_dataset() -> Tuple[list[Dict[str, Any]], Dict[str, Any]]:
    """Return four exact synthetic SCM cases and evaluator-only intervention effects."""
    cases: list[Dict[str, Any]] = []
    truth: Dict[str, Any] = {}
    scms = [
        ("observed_confounder", {
            "topological_order": ["U", "X", "Y"],
            "nodes": {
                "U": {"parents": [], "p1": 0.5},
                "X": {"parents": ["U"], "cpt": {"0": 0.1, "1": 0.9}},
                "Y": {"parents": ["U", "X"], "cpt": {
                    "0,0": 0.05, "0,1": 0.25, "1,0": 0.65, "1,1": 0.85}},
            },
            "edges": [("U", "X"), ("U", "Y"), ("X", "Y")],
            "observed_variables": ["U", "X", "Y"],
        }),
        ("mediated_total_effect", {
            "topological_order": ["X", "M", "Y"],
            "nodes": {
                "X": {"parents": [], "p1": 0.5},
                "M": {"parents": ["X"], "cpt": {"0": 0.1, "1": 0.9}},
                "Y": {"parents": ["X", "M"], "cpt": {
                    "0,0": 0.05, "0,1": 0.55, "1,0": 0.15, "1,1": 0.65}},
            },
            "edges": [("X", "M"), ("M", "Y"), ("X", "Y")],
            "observed_variables": ["X", "M", "Y"],
        }),
        ("collider_selection", {
            "topological_order": ["X", "Y", "C"],
            "nodes": {
                "X": {"parents": [], "p1": 0.5},
                "Y": {"parents": [], "p1": 0.5},
                "C": {"parents": ["X", "Y"], "cpt": {
                    "0,0": 0.1, "0,1": 0.8, "1,0": 0.8, "1,1": 0.9}},
            },
            "edges": [("X", "C"), ("Y", "C")],
            "observed_variables": ["X", "Y", "C"],
        }),
        ("latent_confounder", {
            "topological_order": ["L", "X", "Y"],
            "nodes": {
                "L": {"parents": [], "p1": 0.5},
                "X": {"parents": ["L"], "cpt": {"0": 0.1, "1": 0.9}},
                "Y": {"parents": ["L", "X"], "cpt": {
                    "0,0": 0.05, "0,1": 0.25, "1,0": 0.65, "1,1": 0.85}},
            },
            "edges": [("L", "X"), ("L", "Y"), ("X", "Y")],
            "observed_variables": ["X", "Y"],
        }),
    ]
    for case_id, scm in scms:
        case, labels = _make_case(case_id, scm, "X", "Y")
        cases.append(case)
        truth[case_id] = labels
    return cases, truth


def evaluate_predictions(cases: Sequence[Mapping[str, Any]],
                         predictions: Sequence[Mapping[str, Any]],
                         truth: Mapping[str, Any]) -> Dict[str, Any]:
    by_id = {item["case_id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {c["case_id"] for c in cases}:
        raise ValueError("prediction_case_id_mismatch")
    absolute_errors = []
    identification_correct = 0
    for case in cases:
        label = truth[case["case_id"]]
        prediction = by_id[case["case_id"]]
        predicted_identifiable = prediction["status"] == "identified"
        if predicted_identifiable == label["identifiable"]:
            identification_correct += 1
        if label["identifiable"] and predicted_identifiable and prediction["estimate"] is not None:
            absolute_errors.append(abs(prediction["estimate"] - label["ate"]))
    mae = (sum(absolute_errors) / len(absolute_errors)
           if absolute_errors else None)
    if mae is not None and mae < 1e-12:
        mae = 0.0
    return {
        "cases": len(cases),
        "identification_accuracy": identification_correct / len(cases) if cases else 0.0,
        "identified_case_mae": mae,
        "identified_cases_scored": len(absolute_errors),
    }


def run_baselines(cases: Sequence[Mapping[str, Any]],
                  truth: Mapping[str, Any]) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for method in ("naive_observational", "all_observed_adjustment", "graph_backdoor"):
        predictions = [predict(case, method) for case in cases]
        results[method] = {
            "metrics": evaluate_predictions(cases, predictions, truth),
            "predictions": predictions,
        }
    return results



def rename_case(case: Mapping[str, Any], mapping: Mapping[str, str],
                case_id: str | None = None) -> Dict[str, Any]:
    """Create a label-renamed domain view while preserving graph/data structure."""
    nodes = case["dag"]["nodes"]
    if set(mapping) != set(nodes) or len(set(mapping.values())) != len(mapping):
        raise ValueError("rename_mapping_must_be_total_and_injective")
    old_observed = list(case["observed_variables"])
    new_observed = [mapping[name] for name in old_observed]
    renamed_joint = {}
    for key, probability in case["observational_joint"].items():
        assignment = _decode(key, old_observed)
        renamed_joint[_key([assignment[name] for name in old_observed])] = probability
    return {
        "schema_version": case["schema_version"],
        "case_id": case_id or (case["case_id"] + "_renamed"),
        "dag": {
            "nodes": [mapping[name] for name in nodes],
            "edges": [[mapping[source], mapping[target]]
                      for source, target in case["dag"]["edges"]],
        },
        "observed_variables": new_observed,
        "query": {
            "exposure": mapping[case["query"]["exposure"]],
            "outcome": mapping[case["query"]["outcome"]],
            "estimand": case["query"]["estimand"],
        },
        "observational_joint": renamed_joint,
    }
