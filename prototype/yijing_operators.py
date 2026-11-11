"""YJ-01 executable reference operators.

Deterministic, typed research baseline. These operators do not assert that
traditional cosmological claims are empirical laws. Every interpretation is
scoped, versioned, and evidence-bearing; missing context yields UNKNOWN rather
than an invented result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Mapping, Sequence


class Status(str, Enum):
    APPLIED = "APPLIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEED_CONTEXT = "NEED_CONTEXT"
    NEED_EVIDENCE = "NEED_EVIDENCE"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.source.strip():
            raise ValueError("evidence_id and source are required")


@dataclass(frozen=True)
class OperatorResult:
    operator: str
    status: Status
    value: Any = None
    reasons: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    uncertainty: float = 1.0


@dataclass(frozen=True)
class OperatorContract:
    name: str
    family: str
    input_types: tuple[str, ...]
    output_type: str
    interpretation_version: str
    requires_context: tuple[str, ...] = ()
    requires_evidence: bool = True

    def __post_init__(self) -> None:
        if not all((self.name, self.family, self.output_type,
                    self.interpretation_version)):
            raise ValueError("operator contract fields cannot be empty")


@dataclass(frozen=True)
class Context:
    domain: str | None = None
    phase: str | None = None
    position: int | None = None
    environment: str | None = None
    valid_time: str | None = None
    observed_time: str | None = None

    def missing(self, names: Sequence[str]) -> tuple[str, ...]:
        return tuple(name for name in names if getattr(self, name, None) is None)


def _result(name: str, status: Status, value: Any = None,
            reasons: Sequence[str] = (), evidence: Sequence[Evidence] = (),
            uncertainty: float = 1.0) -> OperatorResult:
    ids = tuple(dict.fromkeys(e.evidence_id for e in evidence))
    return OperatorResult(name, status, value, tuple(reasons), ids, uncertainty)


@dataclass(frozen=True)
class DualAxis:
    axis_id: str
    domain: str
    left_label: str
    right_label: str
    interpretation_version: str

    def __post_init__(self) -> None:
        if not all((self.axis_id, self.domain, self.left_label,
                    self.right_label, self.interpretation_version)):
            raise ValueError("dual axis requires explicit labels, domain and version")
        if self.left_label == self.right_label:
            raise ValueError("dual-axis endpoints must be distinct")


@dataclass(frozen=True)
class DualState:
    object_id: str
    axis_id: str
    value: float
    evidence: tuple[Evidence, ...] = ()


def yin_yang_complement(
    axis: DualAxis, left: DualState, right: DualState,
    *, functional_constraint: str | None,
) -> OperatorResult:
    """Test a task-defined complementarity hypothesis, not mere opposition."""
    if left.axis_id != axis.axis_id or right.axis_id != axis.axis_id:
        return _result("YY_COMPLEMENT", Status.NOT_APPLICABLE,
                       reasons=("states are not bound to the same declared axis",))
    if not functional_constraint:
        return _result("YY_COMPLEMENT", Status.NEED_CONTEXT,
                       reasons=("functional_constraint is required",))
    if not all(isfinite(v) and 0.0 <= v <= 1.0 for v in (left.value, right.value)):
        return _result("YY_COMPLEMENT", Status.CONFLICT,
                       reasons=("axis values must be finite and within [0,1]",))
    evidence = left.evidence + right.evidence
    if not evidence:
        return _result("YY_COMPLEMENT", Status.NEED_EVIDENCE,
                       reasons=("no supporting evidence supplied",))
    # Complementarity is deliberately not inferred from x + y == 1.
    balance = 1.0 - abs(left.value - right.value)
    return _result(
        "YY_COMPLEMENT", Status.APPLIED,
        {"axis_id": axis.axis_id, "functional_constraint": functional_constraint,
         "balance_score": round(balance, 8),
         "interpretation": "candidate_only"},
        ("score is a task-local heuristic; it does not establish universal yin-yang semantics",),
        evidence, uncertainty=0.5,
    )


@dataclass(frozen=True)
class InfluenceEdge:
    source_phase: str
    target_phase: str
    relation: str
    strength: float
    conditions: Mapping[str, str] = field(default_factory=dict)
    interpretation_version: str = ""

    def __post_init__(self) -> None:
        if not self.source_phase or not self.target_phase or not self.relation:
            raise ValueError("influence edge endpoints and relation are required")
        if not isfinite(self.strength) or self.strength < 0:
            raise ValueError("strength must be finite and non-negative")
        if not self.interpretation_version:
            raise ValueError("interpretation_version is required")


def wuxing_influence(
    edge: InfluenceEdge, *, context: Context, source_value: float,
    evidence: Sequence[Evidence],
) -> OperatorResult:
    """Apply one explicitly declared, context-conditioned directed influence."""
    if not evidence:
        return _result("WX_INFLUENCE", Status.NEED_EVIDENCE,
                       reasons=("influence requires traceable evidence",))
    if not isfinite(source_value):
        return _result("WX_INFLUENCE", Status.CONFLICT,
                       reasons=("source_value must be finite",), evidence=evidence)
    missing = tuple(k for k in edge.conditions if getattr(context, k, None) is None)
    if missing:
        return _result("WX_INFLUENCE", Status.NEED_CONTEXT,
                       reasons=("missing condition fields: " + ", ".join(missing),),
                       evidence=evidence)
    mismatched = tuple(k for k, v in edge.conditions.items()
                       if getattr(context, k) != v)
    if mismatched:
        return _result("WX_INFLUENCE", Status.NOT_APPLICABLE,
                       reasons=("condition mismatch: " + ", ".join(mismatched),),
                       evidence=evidence)
    relation = edge.relation.upper()
    if relation not in {"PROMOTE", "RESTRAIN", "OVER_RESTRAIN",
                        "REVERSE_RESTRAINT"}:
        return _result("WX_INFLUENCE", Status.UNKNOWN,
                       reasons=("unsupported or ungrounded relation type",),
                       evidence=evidence)
    signed = -1.0 if relation in {"RESTRAIN", "OVER_RESTRAIN"} else 1.0
    magnitude = edge.strength * source_value
    return _result(
        "WX_INFLUENCE", Status.APPLIED,
        {"source": edge.source_phase, "target": edge.target_phase,
         "relation": relation, "directed_effect": signed * magnitude,
         "interpretation_version": edge.interpretation_version},
        ("direction and meaning come only from the supplied versioned edge; "
         "this is not a universal causal law",), evidence, uncertainty=0.5,
    )


@dataclass(frozen=True)
class YaoLine:
    line_id: str
    polarity: str
    position: int
    role: str
    interpretation_version: str
    evidence: tuple[Evidence, ...] = ()


def yao_bind_position(line: YaoLine, *, expected_position: int) -> OperatorResult:
    if line.polarity not in {"yin", "yang"} or not 1 <= line.position <= 6:
        return _result("YAO_BIND_POSITION", Status.CONFLICT,
                       reasons=("polarity must be yin/yang and position in 1..6",))
    if not line.role or not line.interpretation_version:
        return _result("YAO_BIND_POSITION", Status.NEED_CONTEXT,
                       reasons=("role and interpretation_version are required",))
    if not line.evidence:
        return _result("YAO_BIND_POSITION", Status.NEED_EVIDENCE,
                       reasons=("line binding requires evidence provenance",))
    return _result(
        "YAO_BIND_POSITION", Status.APPLIED,
        {"line_id": line.line_id, "position": line.position, "role": line.role,
         "expected_position": expected_position,
         "position_match": line.position == expected_position,
         "polarity": line.polarity,
         "interpretation_version": line.interpretation_version},
        ("position_match is a structural check, not a divinatory judgment",),
        line.evidence, uncertainty=0.0,
    )


@dataclass(frozen=True)
class BianState:
    bits: tuple[int, ...]
    interpretation_version: str
    evidence: tuple[Evidence, ...] = ()


def bian_bit_flip(state: BianState, *, positions: Sequence[int],
                  trigger: str | None) -> OperatorResult:
    """Explicitly limited bit-flip baseline; not a complete account of 卦变."""
    if not trigger:
        return _result("BIAN_BIT_FLIP_BASELINE", Status.NEED_CONTEXT,
                       reasons=("an explicit transition trigger is required",))
    if not state.evidence:
        return _result("BIAN_BIT_FLIP_BASELINE", Status.NEED_EVIDENCE,
                       reasons=("transition requires source-state evidence",))
    if not state.bits or any(bit not in (0, 1) for bit in state.bits):
        return _result("BIAN_BIT_FLIP_BASELINE", Status.CONFLICT,
                       reasons=("state must be a non-empty binary tuple",),
                       evidence=state.evidence)
    if len(set(positions)) != len(positions) or any(
        p < 1 or p > len(state.bits) for p in positions
    ):
        return _result("BIAN_BIT_FLIP_BASELINE", Status.CONFLICT,
                       reasons=("positions must be unique and within state bounds",),
                       evidence=state.evidence)
    changed = list(state.bits)
    for position in positions:
        changed[position - 1] ^= 1
    return _result(
        "BIAN_BIT_FLIP_BASELINE", Status.APPLIED,
        {"before": state.bits, "after": tuple(changed),
         "changed_positions": tuple(positions), "trigger": trigger,
         "interpretation_version": state.interpretation_version,
         "operator_scope": "limited_bit_flip_baseline"},
        ("does not implement all traditional change rules or interpretive schools",),
        state.evidence, uncertainty=0.5,
    )


def shiwei_condition(
    *, context: Context, required_fields: Sequence[str],
    evidence: Sequence[Evidence],
) -> OperatorResult:
    if not evidence:
        return _result("SHIWEI_CONDITION", Status.NEED_EVIDENCE,
                       reasons=("context binding requires evidence",))
    missing = context.missing(required_fields)
    if missing:
        return _result("SHIWEI_CONDITION", Status.NEED_CONTEXT,
                       reasons=("missing context: " + ", ".join(missing),),
                       evidence=evidence)
    return _result("SHIWEI_CONDITION", Status.APPLIED,
                   {"context": context, "scope": tuple(required_fields)},
                   evidence=evidence, uncertainty=0.0)


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    relation_type: str
    directed: bool = True


@dataclass(frozen=True)
class XiangMapping:
    source_to_target: Mapping[str, str]
    type_compatible: bool
    role_compatible: bool
    evidence: tuple[Evidence, ...] = ()


def xiang_partial_mapping(
    source_relations: Sequence[Relation], target_relations: Sequence[Relation],
    mapping: XiangMapping,
) -> OperatorResult:
    """Score relation preservation for an explicit partial cross-domain map."""
    if not mapping.evidence:
        return _result("XIANG_MAP", Status.NEED_EVIDENCE,
                       reasons=("analogy mapping requires target-domain evidence",))
    if not mapping.type_compatible or not mapping.role_compatible:
        return _result("XIANG_MAP", Status.NOT_APPLICABLE,
                       reasons=("type or role compatibility failed",),
                       evidence=mapping.evidence)
    target_set = {(r.source, r.target, r.relation_type, r.directed)
                  for r in target_relations}
    mapped, unmapped = 0, 0
    conflicts: list[tuple[str, str, str]] = []
    for rel in source_relations:
        if rel.source not in mapping.source_to_target or rel.target not in mapping.source_to_target:
            unmapped += 1
            continue
        candidate = (mapping.source_to_target[rel.source],
                     mapping.source_to_target[rel.target],
                     rel.relation_type, rel.directed)
        if candidate in target_set:
            mapped += 1
        else:
            conflicts.append((rel.source, rel.target, rel.relation_type))
    total = len(source_relations)
    coverage = (mapped + len(conflicts)) / total if total else 0.0
    preservation = mapped / total if total else 0.0
    return _result(
        "XIANG_MAP", Status.APPLIED,
        {"mapped_relations": mapped, "conflicts": tuple(conflicts),
         "unmapped_relations": unmapped, "coverage": coverage,
         "structure_preservation": preservation,
         "mapping": dict(mapping.source_to_target)},
        ("partial analogy hypothesis only; no entity facts transfer across domains",),
        mapping.evidence, uncertainty=1.0 - preservation,
    )


OPERATOR_REGISTRY: Mapping[str, OperatorContract] = {
    contract.name: contract for contract in (
        OperatorContract("YY_COMPLEMENT", "yin_yang",
                         ("DualAxis", "DualState", "DualState"), "candidate",
                         "yy-v0", ("domain",)),
        OperatorContract("WX_INFLUENCE", "wuxing",
                         ("InfluenceEdge", "Context", "float"), "directed_effect",
                         "wx-v0", ("domain",)),
        OperatorContract("YAO_BIND_POSITION", "yao_position",
                         ("YaoLine", "int"), "position_binding", "yao-v0"),
        OperatorContract("BIAN_BIT_FLIP_BASELINE", "bian_transition",
                         ("BianState", "positions", "trigger"), "state_delta",
                         "bian-bitflip-v0"),
        OperatorContract("SHIWEI_CONDITION", "shiwei",
                         ("Context", "required_fields"), "scoped_context",
                         "shiwei-v0"),
        OperatorContract("XIANG_MAP", "xiang_analogy",
                         ("source_relations", "target_relations", "XiangMapping"),
                         "partial_structure_mapping", "xiang-v0"),
    )
}
