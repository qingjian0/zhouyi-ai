"""Structural OOD task: recombine independently observed context constraints."""
from __future__ import annotations
import hashlib, json, random
from typing import Any

SCHEMA = "e10a-structural-ood-v1"


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _pool(seed: int, phase: str, role_values: tuple[str, ...], feature: str,
          instances: int) -> tuple[list[dict], list[str]]:
    seed_tag = hashlib.sha256(str(seed).encode()).hexdigest()[:8]
    prefix = f"{phase}-{seed_tag}"
    rng = random.Random(int.from_bytes(hashlib.sha256(f"{seed}:{phase}".encode()).digest()[:8], "big"))
    objects, role_ids = [], []
    for index, value in enumerate(role_values):
        for n in range(instances):
            oid = f"{prefix}-role-{index}-{n}"
            objects.append({"object_id": oid, "attributes": [[feature, value]]})
            role_ids.append(oid)
    nuisance = f"{prefix}-nuisance"
    objects.append({"object_id": nuisance, "attributes": [[feature, f"{phase}-other"]]})
    rng.shuffle(objects)
    return objects, role_ids + [nuisance]


def build_structural_ood_task(seed: int, *, instances_per_role: int = 4) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Support teaches two context conjuncts separately; Query recombines them."""
    if (not isinstance(seed, int) or isinstance(seed, bool)
            or not isinstance(instances_per_role, int) or isinstance(instances_per_role, bool)
            or instances_per_role < 2):
        raise ValueError("invalid seed or instances_per_role")
    feature, relation = "shape_class", "relates"
    roles = ("alpha", "beta", "gamma")
    context_requirements = (("phase", "active"), ("permission", "granted"))
    support_objects, support_ids = _pool(seed, "support", roles, feature, instances_per_role)
    query_objects, query_ids = _pool(seed, "query", roles, feature, instances_per_role)
    if {x["object_id"] for x in support_objects} & {x["object_id"] for x in query_objects}:
        raise ValueError("object identity leakage")

    def observations(ids: list[str], phase: str, support_mode: bool) -> tuple[list[dict], list[dict]]:
        by_role = []
        for role_index in range(len(roles)):
            seed_tag = hashlib.sha256(str(seed).encode()).hexdigest()[:8]
            by_role.append([oid for oid in ids if oid.startswith(f"{phase}-{seed_tag}-role-{role_index}-")])
        rows, truth = [], []
        serial = 0
        if support_mode:
            cases = [
                (context_requirements, roles, True, f"positive_{index}")
                for index in range(3)
            ] + [
                ((("phase", "inactive"), ("permission", "granted")), roles, False, "phase_only_violation"),
                ((("phase", "active"), ("permission", "denied")), roles, False, "permission_only_violation"),
                ((("phase", "inactive"), ("permission", "denied")), roles, False, "double_violation"),
            ]
        else:
            # Query tests every recombination, including combinations not shown as
            # a labelled Support row. Context values are known; their conjunction is not.
            cases = [
                ((("phase", p), ("permission", q)), roles, p == "active" and q == "granted", f"context_{p}_{q}")
                for p in ("active", "inactive") for q in ("granted", "denied")
            ]
            cases.append((context_requirements, ("alpha", "beta", "other"), False, "role_composition_near_miss"))
        for context, role_spec, valid, tag in cases:
            participants = []
            for value in role_spec:
                if value == "other":
                    participants.append(f"{phase}-{hashlib.sha256(str(seed).encode()).hexdigest()[:8]}-nuisance")
                else:
                    idx = roles.index(value)
                    participants.append(by_role[idx][serial % len(by_role[idx])])
            rng = random.Random(seed + serial + (0 if support_mode else 10000))
            rng.shuffle(participants)
            seed_tag = hashlib.sha256(str(seed).encode()).hexdigest()[:8]
            oid = f"{phase}-{seed_tag}-ood-{serial:04d}"
            row = {"observation_id": oid, "relation_symbol": relation,
                   "participants": participants, "context": [list(x) for x in context]}
            if support_mode:
                row["outcome"] = valid
            rows.append(row)
            truth.append({"observation_id": oid, "valid": valid, "case": tag})
            serial += 1
        return rows, truth

    support_rows, support_truth = observations(support_ids, "support", True)
    query_rows, query_truth = observations(query_ids, "query", False)
    support = {"schema_version": SCHEMA, "phase": "support",
               "objects": support_objects, "observations": support_rows}
    query = {"schema_version": SCHEMA, "phase": "query",
             "objects": query_objects, "observations": query_rows}
    evaluator = {"schema_version": SCHEMA,
                 "mechanism": {"relation_symbol": relation, "feature_key": feature,
                               "role_values": list(roles),
                               "context_requirements": [list(x) for x in context_requirements]},
                 "query_truth": query_truth, "support_truth": support_truth,
                 "audit": {"support_object_count": len(support_objects),
                           "query_object_count": len(query_objects),
                           "object_id_intersection": []}}
    return support, query, evaluator
