"""YJ-09 <-> E13 strict adapter for typed n-ary hypergraphs.

The adapter preserves role order, arity, entity types, edge context/attributes,
validity bounds, evidence references, and snapshot metadata. Unsupported E13
fields fail closed rather than being silently discarded.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.e13_contract import (
    Entity as E13Entity,
    EvidenceStatus,
    RelationInstance,
    RelationSchema,
    RelationalGraph,
    RoleSemantics,
)
from prototype.yijing_hypergraph_induction import (
    Entity,
    Hyperedge,
    HypergraphState,
    RoleBinding,
)


ADAPTER_VERSION = "yj-e13-hypergraph/0.1"
_CONTEXT_PREFIX = "yj_hctx:"
_ATTRIBUTE_PREFIX = "yj_hattr:"
_VALID_FROM = "yj_valid_from"
_VALID_UNTIL = "yj_valid_until"


class HypergraphMappingError(ValueError):
    """Raised when an E13 graph cannot be mapped without semantic loss."""


@dataclass(frozen=True)
class E13HypergraphEnvelope:
    graph: RelationalGraph
    snapshot_context: tuple[tuple[str, str], ...]
    step: int
    evidence_id: str
    domain: str
    coverage_complete: bool
    adapter_version: str = ADAPTER_VERSION


def to_e13(state: HypergraphState) -> E13HypergraphEnvelope:
    entities = tuple(E13Entity(item.entity_id, item.entity_type) for item in state.entities)
    entity_types = state.entity_types()
    schema_signatures: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    context_keys: dict[str, set[str]] = {}
    for edge in state.hyperedges:
        roles = tuple(binding.role for binding in edge.bindings)
        types = tuple(entity_types[binding.entity_id] for binding in edge.bindings)
        signature = (roles, types)
        previous = schema_signatures.get(edge.relation_type)
        if previous is not None and previous != signature:
            raise HypergraphMappingError(
                "one relation_type has incompatible ordered role/type signatures"
            )
        schema_signatures[edge.relation_type] = signature
        keys = context_keys.setdefault(edge.relation_type, set())
        keys.update(_CONTEXT_PREFIX + key for key, _ in edge.context)
        keys.update(_ATTRIBUTE_PREFIX + key for key, _ in edge.attributes)
        if edge.valid_from is not None:
            keys.add(_VALID_FROM)
        if edge.valid_until is not None:
            keys.add(_VALID_UNTIL)

    schemas = tuple(
        RelationSchema(
            relation_type=relation_type,
            arity=len(roles),
            argument_types=types,
            role_semantics=RoleSemantics.ORDERED_NAMED,
            role_names=roles,
            symmetry="ASYMMETRIC",
            context_keys=tuple(sorted(context_keys[relation_type])),
        )
        for relation_type, (roles, types) in sorted(schema_signatures.items())
    )
    relations = []
    for edge in state.hyperedges:
        context = [(_CONTEXT_PREFIX + key, value) for key, value in edge.context]
        context.extend((_ATTRIBUTE_PREFIX + key, value) for key, value in edge.attributes)
        if edge.valid_from is not None:
            context.append((_VALID_FROM, str(edge.valid_from)))
        if edge.valid_until is not None:
            context.append((_VALID_UNTIL, str(edge.valid_until)))
        relations.append(RelationInstance(
            relation_id=edge.edge_id,
            relation_type=edge.relation_type,
            participants=tuple(binding.entity_id for binding in edge.bindings),
            context=tuple(sorted(context)),
            evidence_status=EvidenceStatus.UNKNOWN,
            provenance_refs=edge.evidence_ids,
        ))
    graph = RelationalGraph(entities, schemas, tuple(relations))
    return E13HypergraphEnvelope(
        graph=graph,
        snapshot_context=state.context,
        step=state.step,
        evidence_id=state.evidence_id,
        domain=state.domain,
        coverage_complete=state.coverage_complete,
    )


def from_e13(envelope: E13HypergraphEnvelope) -> HypergraphState:
    if envelope.adapter_version != ADAPTER_VERSION:
        raise HypergraphMappingError("unsupported adapter version")
    graph = envelope.graph
    if any(item.attributes for item in graph.entities):
        raise HypergraphMappingError("YJ-09 entity attributes are not represented by this adapter")
    entities = tuple(Entity(item.entity_id, item.entity_type) for item in graph.entities)
    entity_ids = {item.entity_id for item in entities}
    schema_map = {item.relation_type: item for item in graph.schemas}
    used_types = {item.relation_type for item in graph.relations}
    if used_types != set(schema_map):
        raise HypergraphMappingError("unused or missing relation schemas cannot be round-tripped")

    for schema in graph.schemas:
        if (
            schema.role_semantics != RoleSemantics.ORDERED_NAMED
            or schema.symmetry != "ASYMMETRIC"
            or schema.arity < 2
            or len(schema.role_names) != schema.arity
        ):
            raise HypergraphMappingError("only ordered named asymmetric n-ary schemas are supported")

    edges = []
    observed_keys: dict[str, set[str]] = {}
    for relation in graph.relations:
        schema = schema_map[relation.relation_type]
        if relation.evidence_status != EvidenceStatus.UNKNOWN:
            raise HypergraphMappingError("E13 evidence status has no YJ-09 equivalent")
        if not relation.provenance_refs:
            raise HypergraphMappingError("hyperedge evidence references cannot be empty")
        if len(set(relation.provenance_refs)) != len(relation.provenance_refs):
            raise HypergraphMappingError("duplicate evidence references are not allowed")
        if len(relation.participants) != schema.arity:
            raise HypergraphMappingError("relation participant count does not match schema arity")
        if any(item not in entity_ids for item in relation.participants):
            raise HypergraphMappingError("relation references an unknown entity")
        values = dict(relation.context)
        if len(values) != len(relation.context):
            raise HypergraphMappingError("duplicate relation context keys are not allowed")
        context = []
        attributes = []
        valid_from = None
        valid_until = None
        for key, value in relation.context:
            if key.startswith(_CONTEXT_PREFIX):
                name = key[len(_CONTEXT_PREFIX):]
                if not name:
                    raise HypergraphMappingError("empty context key")
                context.append((name, value))
            elif key.startswith(_ATTRIBUTE_PREFIX):
                name = key[len(_ATTRIBUTE_PREFIX):]
                if not name:
                    raise HypergraphMappingError("empty attribute key")
                attributes.append((name, value))
            elif key == _VALID_FROM:
                try:
                    valid_from = int(value)
                except ValueError as exc:
                    raise HypergraphMappingError("valid_from must be an integer") from exc
            elif key == _VALID_UNTIL:
                try:
                    valid_until = int(value)
                except ValueError as exc:
                    raise HypergraphMappingError("valid_until must be an integer") from exc
            else:
                raise HypergraphMappingError("relation context contains an unmapped field")
        observed_keys.setdefault(relation.relation_type, set()).update(values)
        bindings = tuple(
            RoleBinding(role, entity_id)
            for role, entity_id in zip(schema.role_names, relation.participants)
        )
        edges.append(Hyperedge(
            edge_id=relation.relation_id,
            relation_type=relation.relation_type,
            bindings=bindings,
            evidence_ids=relation.provenance_refs,
            context=tuple(sorted(context)),
            valid_from=valid_from,
            valid_until=valid_until,
            attributes=tuple(sorted(attributes)),
        ))

    for relation_type, schema in schema_map.items():
        if set(schema.context_keys) != observed_keys.get(relation_type, set()):
            raise HypergraphMappingError("schema context keys do not match represented instance fields")
    try:
        return HypergraphState(
            entities=entities,
            hyperedges=tuple(edges),
            context=envelope.snapshot_context,
            step=envelope.step,
            evidence_id=envelope.evidence_id,
            domain=envelope.domain,
            coverage_complete=envelope.coverage_complete,
        )
    except (ValueError, TypeError) as exc:
        raise HypergraphMappingError(str(exc)) from exc
