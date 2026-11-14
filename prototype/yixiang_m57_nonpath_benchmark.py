"""M57: executable benchmark for non-path relational and analogical transfer.

This is a controlled symbolic benchmark, not a learned model or a claim about
classical yixiang validity. Candidate mappings are public; the evaluator label
is isolated. The benchmark tests whether a system can select mappings that
satisfy conjunctions of binary, hyperedge, negative, injectivity, and global
cardinality constraints rather than relying on a single relation path.
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Mapping, Sequence, Tuple

SCHEMA_VERSION = "m57-nonpath-case-v0.1"
LEVELS = ("basic", "compositional", "nonpath")
SPLITS = ("train", "validation", "test")


def _split(i: int, n: int) -> str:
    if i < int(n * 0.70):
        return "train"
    if i < int(n * 0.85):
        return "validation"
    return "test"


def _edge_key(edge: Mapping[str, str]) -> Tuple[str, str, str]:
    return (edge["source"], edge["predicate"], edge["target"])


def validate_case(case: Mapping[str, Any]) -> None:
    if case.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported_schema_version")
    if "evaluator_truth" in case or "gold" in case or "correct_candidate_id" in case:
        raise ValueError("evaluator_truth_leakage")
    pattern = case.get("pattern")
    target = case.get("target_graph")
    candidates = case.get("candidate_mappings")
    if not isinstance(pattern, Mapping) or not isinstance(target, Mapping):
        raise ValueError("pattern_and_target_required")
    roles = pattern.get("roles")
    if not isinstance(roles, list) or len(roles) < 3 or len(set(roles)) != len(roles):
        raise ValueError("invalid_pattern_roles")
    nodes = target.get("nodes")
    if not isinstance(nodes, Mapping) or not nodes:
        raise ValueError("target_nodes_required")
    if not isinstance(candidates, list) or len(candidates) < 2:
        raise ValueError("candidate_mappings_required")
    node_ids = set(nodes)
    for mapping in candidates:
        if set(mapping) != set(roles):
            raise ValueError("candidate_role_set_mismatch")
        values = list(mapping.values())
        if len(set(values)) != len(values) or not set(values) <= node_ids:
            raise ValueError("candidate_mapping_not_injective_or_unknown")
    for edge in pattern.get("binary_relations", []):
        if edge["source"] not in roles or edge["target"] not in roles:
            raise ValueError("binary_relation_unknown_role")
    for edge in pattern.get("hyperedges", []):
        if len(edge["roles"]) < 3 or not set(edge["roles"]) <= set(roles):
            raise ValueError("invalid_hyperedge")
    for edge in target.get("binary_relations", []):
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise ValueError("target_relation_unknown_node")
    for edge in target.get("hyperedges", []):
        if len(edge["nodes"]) < 3 or not set(edge["nodes"]) <= node_ids:
            raise ValueError("target_hyperedge_unknown_node")


def check_mapping(pattern: Mapping[str, Any], target: Mapping[str, Any],
                  mapping: Mapping[str, str]) -> Dict[str, Any]:
    """Evaluate every declared constraint; no path-only shortcut is used."""
    violations: List[str] = []
    roles = pattern["roles"]
    if set(mapping) != set(roles):
        return {"valid": False, "violations": ["role_coverage"], "satisfied": 0,
                "required": 1, "score": 0.0}
    mapped = list(mapping.values())
    if len(set(mapped)) != len(mapped):
        violations.append("injectivity")
    node_types = target["nodes"]
    for role, expected_type in pattern["role_types"].items():
        if mapping.get(role) not in node_types or node_types[mapping[role]] != expected_type:
            violations.append("type:" + role)
    binary = {_edge_key(edge) for edge in target.get("binary_relations", [])}
    for index, edge in enumerate(pattern.get("binary_relations", [])):
        if (mapping[edge["source"]], edge["predicate"], mapping[edge["target"]]) not in binary:
            violations.append("binary:" + str(index))
    target_hyper = {
        (edge["predicate"], tuple(edge["nodes"]))
        for edge in target.get("hyperedges", [])
    }
    for index, edge in enumerate(pattern.get("hyperedges", [])):
        expected = (edge["predicate"], tuple(mapping[role] for role in edge["roles"]))
        if expected not in target_hyper:
            violations.append("hyperedge:" + str(index))
    for index, edge in enumerate(pattern.get("forbidden_relations", [])):
        if (mapping[edge["source"]], edge["predicate"], mapping[edge["target"]]) in binary:
            violations.append("forbidden:" + str(index))
    for index, group in enumerate(pattern.get("all_different", [])):
        values = [mapping[role] for role in group]
        if len(values) != len(set(values)):
            violations.append("all_different:" + str(index))
    for index, constraint in enumerate(pattern.get("global_counts", [])):
        scope = {mapping[role] for role in constraint["roles"]}
        count = sum(
            1 for source, predicate, dest in binary
            if predicate == constraint["predicate"] and source in scope and dest in scope
        )
        if not constraint["minimum"] <= count <= constraint["maximum"]:
            violations.append("global_count:" + str(index))
    required = (
        len(pattern.get("role_types", {}))
        + len(pattern.get("binary_relations", []))
        + len(pattern.get("hyperedges", []))
        + len(pattern.get("forbidden_relations", []))
        + len(pattern.get("all_different", []))
        + len(pattern.get("global_counts", []))
    )
    satisfied = max(0, required - len(violations))
    return {"valid": not violations, "violations": violations, "satisfied": satisfied,
            "required": required, "score": satisfied / required if required else 0.0}


def _build_pattern(level: str) -> Dict[str, Any]:
    if level == "basic":
        roles = ["r0", "r1", "r2", "r3"]
        binary = [
            {"source": "r0", "predicate": "supports", "target": "r1"},
            {"source": "r1", "predicate": "transmits", "target": "r2"},
            {"source": "r2", "predicate": "contains", "target": "r3"},
        ]
        hyperedges: List[Dict[str, Any]] = []
        forbidden: List[Dict[str, str]] = []
        all_different: List[List[str]] = []
        global_counts: List[Dict[str, Any]] = []
    elif level == "compositional":
        roles = ["r0", "r1", "r2", "r3", "r4"]
        binary = [
            {"source": "r0", "predicate": "supports", "target": "r1"},
            {"source": "r0", "predicate": "directs", "target": "r2"},
            {"source": "r3", "predicate": "contains", "target": "r4"},
        ]
        hyperedges = [{"predicate": "jointly_controls", "roles": ["r0", "r2", "r4"]}]
        forbidden = [{"source": "r1", "predicate": "blocks", "target": "r3"}]
        all_different = [roles]
        global_counts = []
    else:
        # Deliberately disconnected binary components plus hyperedges and
        # graph-wide constraints: no single path captures the full structure.
        roles = ["r0", "r1", "r2", "r3", "r4", "r5"]
        binary = [
            {"source": "r0", "predicate": "supports", "target": "r1"},
            {"source": "r0", "predicate": "directs", "target": "r2"},
            {"source": "r3", "predicate": "contains", "target": "r4"},
            {"source": "r4", "predicate": "signals", "target": "r5"},
        ]
        hyperedges = [
            {"predicate": "jointly_controls", "roles": ["r0", "r2", "r5"]},
            {"predicate": "co_regulates", "roles": ["r1", "r3", "r4"]},
        ]
        forbidden = [{"source": "r2", "predicate": "blocks", "target": "r4"}]
        all_different = [roles]
        global_counts = [{
            "predicate": "cross_link", "roles": roles, "minimum": 1, "maximum": 1
        }]
    return {
        "roles": roles,
        "role_types": {role: "type_" + str(i % 3) for i, role in enumerate(roles)},
        "binary_relations": binary,
        "hyperedges": hyperedges,
        "forbidden_relations": forbidden,
        "all_different": all_different,
        "global_counts": global_counts,
    }


def generate_dataset(*, count: int = 240, seed: int = 5701) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not isinstance(count, int) or isinstance(count, bool) or count < 30:
        raise ValueError("count_must_be_integer_at_least_30")
    rng = random.Random(seed)
    cases: List[Dict[str, Any]] = []
    truth: Dict[str, Any] = {}
    for index in range(count):
        level = LEVELS[index % len(LEVELS)]
        pattern = _build_pattern(level)
        roles = pattern["roles"]
        case_id = f"m57-{seed}-{index:05d}"
        nodes: Dict[str, str] = {}
        true_mapping: Dict[str, str] = {}
        for i, role in enumerate(roles):
            entity = f"{case_id}-true-{i}"
            true_mapping[role] = entity
            nodes[entity] = pattern["role_types"][role]
        # Same-type distractors make node typing insufficient by itself.
        distractors: Dict[str, str] = {}
        for i, role in enumerate(roles):
            entity = f"{case_id}-decoy-{i}"
            distractors[role] = entity
            nodes[entity] = pattern["role_types"][role]
        binary = [
            {"source": true_mapping[e["source"]], "predicate": e["predicate"],
             "target": true_mapping[e["target"]]}
            for e in pattern["binary_relations"]
        ]
        hyperedges = [
            {"predicate": edge["predicate"],
             "nodes": [true_mapping[role] for role in edge["roles"]]}
            for edge in pattern["hyperedges"]
        ]
        if level == "nonpath":
            binary.append({
                "source": true_mapping["r0"], "predicate": "cross_link",
                "target": true_mapping["r3"],
            })
        # Distractor noise is generated independently of the planted structure.
        predicates = ("supports", "directs", "contains", "signals", "blocks")  # keep cross_link reserved for the planted global-count constraint
        for _ in range(2 + 3 * LEVELS.index(level)):
            left, right = rng.sample(list(true_mapping.values()), 2)  # noise cannot accidentally validate a decoy entity
            binary.append({"source": left, "predicate": rng.choice(predicates), "target": right})
        for role in roles:
            if rng.random() < 0.5:
                left = true_mapping[role]
                right = distractors[role]
                binary.append({"source": left, "predicate": "incidental", "target": right})
        candidates = [dict(true_mapping)]
        for role in roles:
            decoy = dict(true_mapping)
            decoy[role] = distractors[role]
            candidates.append(decoy)
        rng.shuffle(candidates)
        target = {"nodes": nodes, "binary_relations": binary, "hyperedges": hyperedges}
        # The planted mapping is guaranteed to satisfy all constraints. The
        # evaluator retains the candidate ID, not a truth field in the case.
        valid_ids = [
            "candidate-" + str(i) for i, mapping in enumerate(candidates)
            if check_mapping(pattern, target, mapping)["valid"]
        ]
        if len(valid_ids) != 1:
            raise RuntimeError("generator_unique_solution_invariant_failed")
        public = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "difficulty": level,
            "pattern": pattern,
            "target_graph": target,
            "candidate_mappings": candidates,
        }
        validate_case(public)
        cases.append(public)
        truth[case_id] = {
            "split": _split(index, count),
            "correct_candidate_id": valid_ids[0],
            "valid_candidate_count": len(valid_ids),
            "difficulty": level,
        }
    return cases, truth


def evaluate_prediction(case: Mapping[str, Any], candidate_id: str) -> Dict[str, Any]:
    validate_case(case)
    index_by_id = {
        "candidate-" + str(i): mapping
        for i, mapping in enumerate(case["candidate_mappings"])
    }
    if candidate_id not in index_by_id:
        return {"accepted": False, "reason": "unknown_candidate_id"}
    result = check_mapping(case["pattern"], case["target_graph"], index_by_id[candidate_id])
    return {"accepted": result["valid"], "constraint_audit": result}


def audit_dataset(cases: Sequence[Mapping[str, Any]], truth: Mapping[str, Any]) -> Dict[str, Any]:
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)) or set(ids) != set(truth):
        raise ValueError("case_truth_id_mismatch")
    split_counts = {name: 0 for name in SPLITS}
    difficulty_counts = {name: 0 for name in LEVELS}
    for case in cases:
        validate_case(case)
        difficulty_counts[case["difficulty"]] += 1
        split_counts[truth[case["case_id"]]["split"]] += 1
    return {
        "cases": len(cases),
        "split_counts": split_counts,
        "difficulty_counts": difficulty_counts,
        "public_truth_leaks": 0,
        "unique_valid_mapping_per_case": all(
            truth[case["case_id"]]["valid_candidate_count"] == 1 for case in cases
        ),
    }


def write_dataset(cases: Sequence[Mapping[str, Any]], truth: Mapping[str, Any],
                  prefix: str) -> Dict[str, str]:
    agent_path = prefix + ".agent.jsonl"
    evaluator_path = prefix + ".evaluator.json"
    with open(agent_path, "w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    with open(evaluator_path, "w", encoding="utf-8") as handle:
        json.dump(truth, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return {"agent": agent_path, "evaluator": evaluator_path}
