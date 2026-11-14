"""M58: autonomous entity alignment and relational mapping baselines.

The solver receives only the pattern and target graph. It deliberately ignores
M57's supplied candidate_mappings, and never reads evaluator truth. This is a
small exact symbolic baseline, not a learned or human-level reasoning claim.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from prototype.yixiang_m57_nonpath_benchmark import check_mapping

MODES = ("type_only", "path_only", "full_constraints")


class SearchBudgetExceeded(RuntimeError):
    pass


def _edge_set(target: Mapping[str, Any]) -> set[Tuple[str, str, str]]:
    return {
        (edge["source"], edge["predicate"], edge["target"])
        for edge in target.get("binary_relations", [])
    }


def _partial_valid(pattern: Mapping[str, Any], target: Mapping[str, Any],
                   mapping: Mapping[str, str], edges: set,
                   hyperedges: set, mode: str) -> bool:
    for role, entity in mapping.items():
        if target["nodes"].get(entity) != pattern["role_types"][role]:
            return False
    values = list(mapping.values())
    if len(values) != len(set(values)):
        return False
    if mode == "type_only":
        return True

    for edge in pattern.get("binary_relations", []):
        left, right = edge["source"], edge["target"]
        if left in mapping and right in mapping:
            if (mapping[left], edge["predicate"], mapping[right]) not in edges:
                return False
    if mode == "path_only":
        return True

    for edge in pattern.get("forbidden_relations", []):
        left, right = edge["source"], edge["target"]
        if left in mapping and right in mapping:
            if (mapping[left], edge["predicate"], mapping[right]) in edges:
                return False
    for edge in pattern.get("hyperedges", []):
        roles = edge["roles"]
        if all(role in mapping for role in roles):
            key = (edge["predicate"], tuple(mapping[role] for role in roles))
            if key not in hyperedges:
                return False
    for group in pattern.get("all_different", []):
        assigned = [mapping[role] for role in group if role in mapping]
        if len(assigned) != len(set(assigned)):
            return False
    return True


def enumerate_mappings(case: Mapping[str, Any], *, mode: str = "full_constraints",
                       max_states: int = 250_000, max_solutions: int = 2) -> Dict[str, Any]:
    """Search role-to-entity mappings without consulting supplied candidates."""
    if mode not in MODES:
        raise ValueError("unknown_solver_mode")
    if max_states < 1 or max_solutions < 1:
        raise ValueError("search_limits_must_be_positive")
    pattern, target = case["pattern"], case["target_graph"]
    roles = list(pattern["roles"])
    edges = _edge_set(target)
    hyperedges = {
        (edge["predicate"], tuple(edge["nodes"]))
        for edge in target.get("hyperedges", [])
    }
    domains = {
        role: [entity for entity, typ in target["nodes"].items()
               if typ == pattern["role_types"][role]]
        for role in roles
    }
    if any(not domains[role] for role in roles):
        return {"status": "no_solution", "solutions": [], "states": 0}

    # Minimum-remaining-values first; relation degree breaks ties.
    degree = Counter()
    for edge in pattern.get("binary_relations", []):
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    order = sorted(roles, key=lambda role: (len(domains[role]), -degree[role], role))
    mapping: Dict[str, str] = {}
    solutions: List[Dict[str, str]] = []
    states = 0

    def visit(position: int) -> None:
        nonlocal states
        if len(solutions) >= max_solutions:
            return
        if position == len(order):
            if mode == "full_constraints":
                if check_mapping(pattern, target, mapping)["valid"]:
                    solutions.append(dict(mapping))
            else:
                solutions.append(dict(mapping))
            return
        role = order[position]
        for entity in domains[role]:
            states += 1
            if states > max_states:
                raise SearchBudgetExceeded("search_budget_exceeded")
            if entity in mapping.values():
                continue
            mapping[role] = entity
            if _partial_valid(pattern, target, mapping, edges, hyperedges, mode):
                visit(position + 1)
            del mapping[role]
            if len(solutions) >= max_solutions:
                return

    try:
        visit(0)
    except SearchBudgetExceeded:
        return {"status": "budget_exhausted", "solutions": [],
                "states": states, "mode": mode}
    status = "no_solution" if not solutions else (
        "unique" if len(solutions) == 1 else "ambiguous"
    )
    return {"status": status, "solutions": solutions, "states": states, "mode": mode}


def predict(case: Mapping[str, Any], *, mode: str = "full_constraints",
            max_states: int = 250_000) -> Dict[str, Any]:
    result = enumerate_mappings(case, mode=mode, max_states=max_states)
    mapping = result["solutions"][0] if result["status"] == "unique" else None
    return {"case_id": case["case_id"], "mapping": mapping,
            "status": result["status"], "states": result["states"], "mode": mode}


def evaluate_predictions(cases: Sequence[Mapping[str, Any]],
                         predictions: Sequence[Mapping[str, Any]],
                         evaluator_truth: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluator-only scoring; predictions are immutable model outputs."""
    by_id = {item["case_id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {c["case_id"] for c in cases}:
        raise ValueError("prediction_case_id_mismatch")
    if set(evaluator_truth) != {c["case_id"] for c in cases}:
        raise ValueError("evaluator_truth_case_id_mismatch")
    counts: Dict[str, Dict[str, int]] = {}
    exact = covered = 0
    for case in cases:
        case_id = case["case_id"]
        level = case["difficulty"]
        bucket = counts.setdefault(level, {"cases": 0, "exact": 0, "covered": 0})
        bucket["cases"] += 1
        predicted = by_id[case_id].get("mapping")
        expected_id = evaluator_truth[case_id]["correct_candidate_id"]
        expected_index = int(expected_id.split("-")[1])
        # M57 evaluator truth maps the candidate ID to its private mapping via
        # a private field populated by the caller, never the public case.
        expected = evaluator_truth[case_id]["_correct_mapping"]
        is_exact = predicted == expected
        if predicted is not None:
            covered += 1
            bucket["covered"] += 1
        if is_exact:
            exact += 1
            bucket["exact"] += 1
    return {
        "cases": len(cases), "exact": exact, "coverage": covered / len(cases) if cases else 0.0,
        "exact_accuracy": exact / len(cases) if cases else 0.0,
        "selective_accuracy": exact / covered if covered else 0.0,
        "per_difficulty": counts,
    }
