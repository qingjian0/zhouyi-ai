import unittest
from dataclasses import replace

from prototype.e13_contract import (
    Entity, EvidenceStatus, RelationInstance, RelationSchema, RelationalGraph,
    RoleSemantics,
)
from prototype.yijing_operator_induction import Node, Relation, RelationalState
from prototype.yijing_e13_adapter import (
    E13Envelope, RelationalMappingError, from_e13, to_e13,
)


def sample_state():
    return RelationalState(
        nodes=(
            Node("a", "agent", "actor"),
            Node("b", "resource", "target"),
            Node("c", "environment", "context"),
        ),
        relations=(
            Relation("a", "b", "supports", (("weight", "0.7"),)),
            Relation("b", "c", "constrains", (("mode", "seasonal"),)),
        ),
        context=(("domain", "ecology"), ("phase", "growth")),
    )


class E13AdapterTests(unittest.TestCase):
    def test_round_trip_preserves_roles_relations_attributes_and_context(self):
        original = sample_state()
        mapped = to_e13(original)
        restored = from_e13(mapped)
        self.assertEqual(restored, original)

    def test_empty_relation_graph_preserves_nodes_and_global_context(self):
        original = RelationalState(
            nodes=(Node("a", "agent", "actor"),),
            relations=(),
            context=(("phase", "rest"),),
        )
        self.assertEqual(from_e13(to_e13(original)), original)

    def test_relation_type_with_conflicting_endpoint_types_fails_closed(self):
        state = RelationalState(
            nodes=(
                Node("a", "agent", "actor"),
                Node("b", "resource", "target"),
                Node("c", "place", "location"),
            ),
            relations=(
                Relation("a", "b", "connects"),
                Relation("a", "c", "connects"),
            ),
            context=(),
        )
        with self.assertRaises(RelationalMappingError):
            to_e13(state)

    def test_reverse_mapping_rejects_lost_role_metadata(self):
        graph = to_e13(sample_state()).graph
        entities = tuple(
            replace(entity, attributes=()) if entity.entity_id == "a" else entity
            for entity in graph.entities
        )
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(replace(graph, entities=entities), (("phase", "growth"), ("domain", "ecology"))))

    def test_reverse_mapping_rejects_non_yijing_entity_attributes(self):
        graph = to_e13(sample_state()).graph
        entities = tuple(
            replace(entity, attributes=entity.attributes + (("extra", "x"),))
            if entity.entity_id == "a" else entity
            for entity in graph.entities
        )
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(replace(graph, entities=entities), sample_state().context))

    def test_reverse_mapping_rejects_non_binary_or_unordered_schema(self):
        graph = to_e13(sample_state()).graph
        schema = graph.schemas[0]
        bad = replace(
            schema,
            role_semantics=RoleSemantics.UNORDERED,
            role_names=(),
            symmetry="UNKNOWN",
        )
        schemas = tuple(bad if item.relation_type == schema.relation_type else item for item in graph.schemas)
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(replace(graph, schemas=schemas), sample_state().context))

    def test_relation_context_namespace_is_enforced(self):
        graph = to_e13(sample_state()).graph
        instance = graph.relations[0]
        changed = replace(instance, context=instance.context + (("phase", "growth"),))
        relations = tuple(changed if item.relation_id == instance.relation_id else item for item in graph.relations)
        # The E13 graph contract rejects undeclared context keys before adapter decoding.
        with self.assertRaises(ValueError):
            RelationalGraph(graph.entities, graph.schemas, relations)

    def test_adapter_version_is_checked(self):
        with self.assertRaises(RelationalMappingError):
            from_e13(replace(to_e13(sample_state()), adapter_version="future/9"))

    def test_duplicate_relation_attribute_keys_are_rejected(self):
        state = RelationalState(
            nodes=(Node("a", "agent", "actor"), Node("b", "resource", "target")),
            relations=(Relation("a", "b", "supports", (("x", "1"), ("x", "2"))),),
            context=(),
        )
        with self.assertRaises(RelationalMappingError):
            to_e13(state)

    def test_reverse_mapping_rejects_unmapped_evidence_metadata(self):
        graph = to_e13(sample_state()).graph
        instance = graph.relations[0]
        changed = replace(instance, evidence_status=EvidenceStatus.SUPPORT)
        relations = tuple(
            changed if item.relation_id == instance.relation_id else item
            for item in graph.relations
        )
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(replace(graph, relations=relations), sample_state().context))

    def test_duplicate_role_metadata_is_rejected(self):
        graph = to_e13(sample_state()).graph
        entities = tuple(
            replace(entity, attributes=entity.attributes + (("yj_role", "duplicate"),))
            if entity.entity_id == "a" else entity
            for entity in graph.entities
        )
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(replace(graph, entities=entities), sample_state().context))

    def test_unused_schema_is_rejected_as_unrepresentable(self):
        graph = to_e13(sample_state()).graph
        unused = RelationSchema(
            relation_type="unused",
            arity=2,
            argument_types=("agent", "resource"),
            role_semantics=RoleSemantics.ORDERED_NAMED,
            role_names=("source", "target"),
            symmetry="ASYMMETRIC",
        )
        with self.assertRaises(RelationalMappingError):
            from_e13(E13Envelope(
                replace(graph, schemas=graph.schemas + (unused,)),
                sample_state().context,
            ))

    def test_duplicate_global_context_keys_are_rejected(self):
        envelope = to_e13(sample_state())
        duplicated = envelope.state_context + (("phase", "decline"),)
        with self.assertRaises(RelationalMappingError):
            from_e13(replace(envelope, state_context=tuple(sorted(duplicated))))


if __name__ == "__main__":
    unittest.main()
