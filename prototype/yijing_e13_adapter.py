"""YJ-06: strict adapter between YJ-04 relational states and E13 graph contracts.

The adapter preserves YJ-04's global context in an envelope and maps relation
attributes through a reserved namespace. Ambiguous relation schemas fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.e13_contract import (
    Entity,
    EvidenceStatus,
    RelationInstance,
    RelationSchema,
    RelationalGraph,
    RoleSemantics,
)
from prototype.yijing_operator_induction import (
    Node,
    Relation,
    RelationalState,
)


class RelationalMappingError(ValueError):
    """Raised when a state cannot be represented without semantic loss."""


ADAPTER_VERSION = "yj-e13-relational/0.1"
_ROLE_KEY = "yj_role"
_ATTRIBUTE_PREFIX = "yj_attr:"


@dataclass(frozen=True)
class E13Envelope:
    graph: RelationalGraph
    state_context: tuple[tuple[str, str], ...]
    adapter_version: str = ADAPTER_VERSION


def to_e13(state: RelationalState) -> E13Envelope:
    """Map a YJ-04 state to E13; reject relation-type signature ambiguity."""
    if any(
        not all(isinstance(value, str) and value for value in (
            node.entity_id, node.entity_type, node.role
        ))
        for node in state.nodes
    ):
        raise RelationalMappingError("node IDs, types and roles must be non-empty strings")
    if len({key for key, _ in state.context}) != len(state.context):
        raise RelationalMappingError("global state context keys must be unique")
    entities = tuple(
        Entity(node.entity_id, node.entity_type, ((_ROLE_KEY, node.role),))
        for node in state.nodes
    )
    node_by_id = {node.entity_id: node for node in state.nodes}

    signatures: dict[str, tuple[str, str]] = {}
    attribute_keys: dict[str, set[str]] = {}
    for relation in state.relations:
        attribute_names = [key for key, _ in relation.attributes]
        if (
            any(not isinstance(key, str) or not key for key in attribute_names)
            or any(not isinstance(value, str) for _, value in relation.attributes)
            or len(attribute_names) != len(set(attribute_names))
        ):
            raise RelationalMappingError("relation attributes must have unique non-empty string keys and string values")
        source = node_by_id[relation.source]
        target = node_by_id[relation.target]
        signature = (source.entity_type, target.entity_type)
        prior = signatures.get(relation.relation_type)
        if prior is not None and prior != signature:
            raise RelationalMappingError(
                "one relation_type has multiple ordered endpoint type signatures"
            )
        signatures[relation.relation_type] = signature
        attribute_keys.setdefault(relation.relation_type, set()).update(
            key for key, _ in relation.attributes
        )

    schemas = tuple(
        RelationSchema(
            relation_type=relation_type,
            arity=2,
            argument_types=signature,
            role_semantics=RoleSemantics.ORDERED_NAMED,
            role_names=("source", "target"),
            symmetry="ASYMMETRIC",
            context_keys=tuple(sorted(
                _ATTRIBUTE_PREFIX + key
                for key in attribute_keys.get(relation_type, set())
            )),
        )
        for relation_type, signature in sorted(signatures.items())
    )
    instances = tuple(
        RelationInstance(
            relation_id=f"yj-rel-{index:06d}",
            relation_type=relation.relation_type,
            participants=(relation.source, relation.target),
            context=tuple(sorted(
                (_ATTRIBUTE_PREFIX + key, value)
                for key, value in relation.attributes
            )),
            evidence_status=EvidenceStatus.UNKNOWN,
            provenance_refs=(),
        )
        for index, relation in enumerate(state.relations)
    )
    graph = RelationalGraph(entities, schemas, instances)
    if any(
        not isinstance(key, str) or not key or not isinstance(value, str)
        for key, value in state.context
    ):
        raise RelationalMappingError("global state context must use non-empty string keys and string values")
    return E13Envelope(graph=graph, state_context=state.context)


def from_e13(envelope: E13Envelope) -> RelationalState:
    """Reconstruct YJ-04 state only when the E13 graph is losslessly mappable."""
    if envelope.adapter_version != ADAPTER_VERSION:
        raise RelationalMappingError("unsupported adapter version")
    graph = envelope.graph
    nodes = []
    for entity in graph.entities:
        attributes = dict(entity.attributes)
        if len(entity.attributes) != 1 or set(attributes) != {_ROLE_KEY}:
            raise RelationalMappingError(
                "entity attributes must contain exactly one preserved YJ role"
            )
        role = attributes[_ROLE_KEY]
        if not role:
            raise RelationalMappingError("YJ role cannot be empty")
        nodes.append(Node(entity.entity_id, entity.entity_type, role))

    schema_map = {schema.relation_type: schema for schema in graph.schemas}
    used_relation_types = {instance.relation_type for instance in graph.relations}
    if used_relation_types != set(schema_map):
        raise RelationalMappingError(
            "schemas without instances or instances without schemas cannot be losslessly mapped"
        )
    for schema in graph.schemas:
        if (
            schema.arity != 2
            or schema.role_semantics != RoleSemantics.ORDERED_NAMED
            or schema.role_names != ("source", "target")
            or schema.symmetry != "ASYMMETRIC"
        ):
            raise RelationalMappingError(
                "only ordered asymmetric binary relation schemas are supported"
            )

    relations = []
    observed_attribute_keys: dict[str, set[str]] = {}
    for instance in graph.relations:
        if instance.evidence_status != EvidenceStatus.UNKNOWN or instance.provenance_refs:
            raise RelationalMappingError(
                "YJ-04 has no equivalent relation evidence-status or provenance fields"
            )
        schema = schema_map.get(instance.relation_type)
        if schema is None or len(instance.participants) != 2:
            raise RelationalMappingError("missing or unsupported relation schema")
        attributes = []
        for key, value in instance.context:
            if not key.startswith(_ATTRIBUTE_PREFIX):
                raise RelationalMappingError(
                    "relation context contains fields outside the YJ attribute namespace"
                )
            attribute_key = key[len(_ATTRIBUTE_PREFIX):]
            if not attribute_key:
                raise RelationalMappingError("empty relation attribute key")
            attributes.append((attribute_key, value))
        observed_attribute_keys.setdefault(instance.relation_type, set()).update(
            key for key, _ in attributes
        )
        relations.append(Relation(
            source=instance.participants[0],
            target=instance.participants[1],
            relation_type=instance.relation_type,
            attributes=tuple(sorted(attributes)),
        ))

    for relation_type, schema in schema_map.items():
        expected = set(schema.context_keys)
        observed = {
            _ATTRIBUTE_PREFIX + key
            for key in observed_attribute_keys.get(relation_type, set())
        }
        if expected != observed:
            raise RelationalMappingError(
                "schema declares relation attributes not represented by instances"
            )
    if tuple(sorted(envelope.state_context)) != envelope.state_context:
        raise RelationalMappingError("global state context must be canonically sorted")
    if len({key for key, _ in envelope.state_context}) != len(envelope.state_context):
        raise RelationalMappingError("global state context keys must be unique")
    if any(
        not isinstance(key, str) or not key or not isinstance(value, str)
        for key, value in envelope.state_context
    ):
        raise RelationalMappingError("global state context must use non-empty string keys and string values")
    try:
        return RelationalState(
            nodes=tuple(sorted(nodes)),
            relations=tuple(sorted(relations)),
            context=tuple(sorted(envelope.state_context)),
        )
    except ValueError as exc:
        raise RelationalMappingError(str(exc)) from exc
