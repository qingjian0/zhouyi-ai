import unittest

from prototype.e13_contract import (
    EvidenceStatus, RelationInstance, RelationSchema, RelationalGraph, RoleSemantics,
)
from prototype.yijing_hypergraph_e13_adapter import (
    E13HypergraphEnvelope, HypergraphMappingError, from_e13, to_e13,
)
from prototype.yijing_hypergraph_induction import (
    Entity, Hyperedge, HypergraphState, RoleBinding,
)


def sample_state():
    return HypergraphState(
        entities=(Entity("a", "agent"), Entity("b", "tool"), Entity("c", "result")),
        hyperedges=(
            Hyperedge(
                "h1", "joint_action",
                (RoleBinding("actor", "a"), RoleBinding("instrument", "b"),
                 RoleBinding("outcome", "c")),
                ("ev1", "ev2"), (("phase", "active"),), 2, 8,
                (("mode", "cooperative"),),
            ),
        ),
        context=(("world", "lab"),), step=4, evidence_id="snapshot-4",
        domain="synthetic", coverage_complete=True,
    )


class HypergraphE13AdapterTests(unittest.TestCase):
    def test_round_trip_preserves_nary_roles_context_time_and_evidence(self):
        state = sample_state()
        restored = from_e13(to_e13(state))
        self.assertEqual(restored, state)

    def test_schema_retains_arity_and_named_roles(self):
        envelope = to_e13(sample_state())
        schema = envelope.graph.schemas[0]
        self.assertEqual(schema.arity, 3)
        self.assertEqual(schema.role_semantics, RoleSemantics.ORDERED_NAMED)
        self.assertEqual(schema.role_names, ("actor", "instrument", "outcome"))

    def test_multiple_same_type_edges_require_same_schema(self):
        state = sample_state()
        second = Hyperedge(
            "h2", "joint_action",
            (RoleBinding("actor", "a"), RoleBinding("instrument", "b"),
             RoleBinding("outcome", "c")),
            ("ev3",),
        )
        self.assertEqual(len(to_e13(HypergraphState(
            state.entities, state.hyperedges + (second,), state.context,
            state.step, state.evidence_id, state.domain, state.coverage_complete,
        )).graph.relations), 2)

    def test_incompatible_role_signature_fails_closed(self):
        state = sample_state()
        changed = Hyperedge(
            "h2", "joint_action",
            (RoleBinding("source", "a"), RoleBinding("target", "b"),
             RoleBinding("outcome", "c")), ("ev3",),
        )
        with self.assertRaises(HypergraphMappingError):
            to_e13(HypergraphState(
                state.entities, state.hyperedges + (changed,), state.context,
                state.step, state.evidence_id, state.domain, state.coverage_complete,
            ))

    def test_unknown_evidence_status_fails_closed(self):
        envelope = to_e13(sample_state())
        relation = envelope.graph.relations[0]
        bad = RelationInstance(
            relation.relation_id, relation.relation_type, relation.participants,
            relation.context, EvidenceStatus.SUPPORT, relation.provenance_refs,
        )
        with self.assertRaises(HypergraphMappingError):
            from_e13(E13HypergraphEnvelope(
                RelationalGraph(envelope.graph.entities, envelope.graph.schemas, (bad,)),
                envelope.snapshot_context, envelope.step, envelope.evidence_id,
                envelope.domain, envelope.coverage_complete,
            ))

    def test_unmapped_context_field_fails_closed(self):
        envelope = to_e13(sample_state())
        relation = envelope.graph.relations[0]
        bad = RelationInstance(
            relation.relation_id, relation.relation_type, relation.participants,
            relation.context + (("foreign", "x"),), relation.evidence_status,
            relation.provenance_refs,
        )
        with self.assertRaises(Exception):
            from_e13(E13HypergraphEnvelope(
                RelationalGraph(envelope.graph.entities, envelope.graph.schemas, (bad,)),
                envelope.snapshot_context, envelope.step, envelope.evidence_id,
                envelope.domain, envelope.coverage_complete,
            ))

    def test_missing_provenance_is_rejected(self):
        envelope = to_e13(sample_state())
        relation = envelope.graph.relations[0]
        bad = RelationInstance(
            relation.relation_id, relation.relation_type, relation.participants,
            relation.context, relation.evidence_status, (),
        )
        with self.assertRaises(HypergraphMappingError):
            from_e13(E13HypergraphEnvelope(
                RelationalGraph(envelope.graph.entities, envelope.graph.schemas, (bad,)),
                envelope.snapshot_context, envelope.step, envelope.evidence_id,
                envelope.domain, envelope.coverage_complete,
            ))

    def test_wrong_adapter_version_is_rejected(self):
        envelope = to_e13(sample_state())
        with self.assertRaises(HypergraphMappingError):
            from_e13(E13HypergraphEnvelope(
                envelope.graph, envelope.snapshot_context, envelope.step,
                envelope.evidence_id, envelope.domain, envelope.coverage_complete,
                "old-version",
            ))

    def test_non_named_schema_is_rejected(self):
        envelope = to_e13(sample_state())
        schema = envelope.graph.schemas[0]
        bad_schema = RelationSchema(
            schema.relation_type, schema.arity, schema.argument_types,
            RoleSemantics.ORDERED_POSITIONAL, symmetry="ASYMMETRIC",
        )
        with self.assertRaises(HypergraphMappingError):
            from_e13(E13HypergraphEnvelope(
                RelationalGraph(envelope.graph.entities, (bad_schema,), envelope.graph.relations),
                envelope.snapshot_context, envelope.step, envelope.evidence_id,
                envelope.domain, envelope.coverage_complete,
            ))


if __name__ == "__main__":
    unittest.main()
