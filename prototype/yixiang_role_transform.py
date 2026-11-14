"""Versioned, explicit relation-role transforms for XSL-3.

A transform is a hypothesis about how argument positions are re-expressed.
Applying it never establishes semantic equivalence or relation symmetry.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from prototype.yixiang_analogy import Relation


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
        raise ValueError(f"{field} must be a sorted, unique tuple")
    for value in values:
        _nonempty(value, field)


@dataclass(frozen=True)
class RoleTransform:
    transform_id: str
    version: str
    source_relation_type: str
    target_relation_type: str
    argument_permutation: tuple[int, ...]
    scope_conditions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("transform_id", "version", "source_relation_type", "target_relation_type"):
            _nonempty(getattr(self, field), field)
        permutation = self.argument_permutation
        if not isinstance(permutation, tuple) or not permutation:
            raise ValueError("argument_permutation must be a non-empty tuple")
        if any(isinstance(i, bool) or not isinstance(i, int) for i in permutation):
            raise ValueError("argument_permutation entries must be integers, not booleans")
        if tuple(sorted(permutation)) != tuple(range(len(permutation))):
            raise ValueError("argument_permutation must be a permutation of 0..arity-1")
        _sorted_unique(self.scope_conditions, "scope_conditions")
        _sorted_unique(self.evidence_refs, "evidence_refs")

    @property
    def arity(self) -> int:
        return len(self.argument_permutation)


@dataclass(frozen=True)
class TransformApplication:
    source_relation: Relation
    transformed_relation: Relation
    transform_id: str
    transform_version: str
    semantic_status: str
    application_digest: str


def apply_role_transform(
    relation: Relation,
    transform: RoleTransform,
) -> TransformApplication:
    """Apply only the declared argument permutation; return a hypothesis record."""
    if not isinstance(relation, Relation):
        raise ValueError("relation must be a Relation")
    if not isinstance(transform, RoleTransform):
        raise ValueError("transform must be a RoleTransform")
    if relation.relation_type != transform.source_relation_type:
        raise ValueError("source relation type does not match transform")
    if len(relation.arguments) != transform.arity:
        raise ValueError("relation arity does not match transform")
    transformed = Relation(
        transform.target_relation_type,
        tuple(relation.arguments[index] for index in transform.argument_permutation),
    )
    payload = {
        "source": [relation.relation_type, list(relation.arguments)],
        "target": [transformed.relation_type, list(transformed.arguments)],
        "transform_id": transform.transform_id,
        "transform_version": transform.version,
        "argument_permutation": list(transform.argument_permutation),
        "scope_conditions": list(transform.scope_conditions),
        "evidence_refs": list(transform.evidence_refs),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return TransformApplication(
        source_relation=relation,
        transformed_relation=transformed,
        transform_id=transform.transform_id,
        transform_version=transform.version,
        semantic_status="HYPOTHESIS_ONLY",
        application_digest=hashlib.sha256(encoded).hexdigest(),
    )


def compose_argument_permutations(
    first: tuple[int, ...],
    second: tuple[int, ...],
) -> tuple[int, ...]:
    """Compose position maps: apply first, then second.

    Each tuple describes output-position -> input-position. Composition is
    therefore first[second[j]] for each output position j.
    """
    for name, permutation in (("first", first), ("second", second)):
        if not isinstance(permutation, tuple) or not permutation:
            raise ValueError(f"{name} permutation must be a non-empty tuple")
        if any(isinstance(i, bool) or not isinstance(i, int) for i in permutation):
            raise ValueError(f"{name} permutation entries must be integers")
        if tuple(sorted(permutation)) != tuple(range(len(permutation))):
            raise ValueError(f"{name} must be a permutation of 0..arity-1")
    if len(first) != len(second):
        raise ValueError("permutations must have the same arity")
    return tuple(first[index] for index in second)
