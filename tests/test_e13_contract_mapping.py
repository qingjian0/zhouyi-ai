import unittest

from prototype.e13_contract import (
    ContractError,
    Entity,
    EvidenceEvent,
    EventKind,
    EvidenceStatus,
    RelationInstance,
    RelationSchema,
    RelationalGraph,
    RoleSemantics,
    canonical_digest,
    graph_to_dict,
    validate_observation_visibility,
)
from prototype.e13_mapping import enumerate_exact_mappings


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = RelationSchema(
            relation_type="supports",
            arity=2,
            argument_types=("claim", "evidence"),
            role_semantics=RoleSemantics.ORDERED_NAMED,
            role_names=("supported_claim", "supporting_evidence"),
            symmetry="ASYMMETRIC",
            context_keys=("domain",),
        )

    def graph(self, prefix="s", reverse=False):
        entities = (
            Entity(f"{prefix}c", "claim"),
            Entity(f"{prefix}e", "evidence"),
        )
        participants = (f"{prefix}e", f"{prefix}c") if reverse else (f"{prefix}c", f"{prefix}e")
        relation = RelationInstance(
            f"{prefix}r", "supports", participants,
            context=(("domain", "science"),),
            evidence_status=EvidenceStatus.SUPPORT,
            provenance_refs=("obs-1",),
        )
        return RelationalGraph(entities, (self.schema,), (relation,))

    def test_graph_round_trip_digest_is_stable(self):
        graph = self.graph()
        encoded = graph_to_dict(graph)
        self.assertEqual(encoded["schema_version"], "cpg-ei-experience/0.1")
        self.assertEqual(canonical_digest(encoded), canonical_digest(encoded))

    def test_rejects_missing_schema_and_wrong_arity(self):
        with self.assertRaises(ContractError):
            RelationalGraph((Entity("a", "claim"),), (), ())
        with self.assertRaises(ContractError):
            RelationalGraph(
                (Entity("a", "claim"),),
                (self.schema,),
                (RelationInstance("r", "supports", ("a",)),),
            )

    def test_named_roles_require_names_and_unique_roles(self):
        with self.assertRaises(ContractError):
            RelationSchema("r", 2, ("x", "x"), RoleSemantics.ORDERED_NAMED)
        with self.assertRaises(ContractError):
            RelationSchema("r", 2, ("x", "y"), RoleSemantics.ORDERED_NAMED, ("same", "same"))

    def test_unknown_role_semantics_is_not_upgraded(self):
        unknown = RelationSchema(
            "r", 2, ("node", "node"), RoleSemantics.UNKNOWN, symmetry="UNKNOWN"
        )
        self.assertEqual(unknown.role_semantics, RoleSemantics.UNKNOWN)

    def test_hidden_label_leak_is_rejected(self):
        with self.assertRaises(ContractError):
            validate_observation_visibility("QUERY", "LEARNER_VISIBLE", True)
        validate_observation_visibility("QUERY", "EVALUATOR_ONLY", True)

    def test_evidence_event_requires_integrity_fields(self):
        with self.assertRaises(ContractError):
            EvidenceEvent("", "ep", 0, EventKind.OBSERVATION_RECORDED, "E12", "digest", "LEARNER_VISIBLE")


class ExactMappingTests(ContractTests):
    def test_finds_unique_typed_mapping(self):
        result = enumerate_exact_mappings(self.graph("s"), self.graph("t"))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(dict(result.candidates[0].node_mapping), {"sc": "tc", "se": "te"})

    def test_rejects_type_invalid_role_reversal_at_contract_boundary(self):
        with self.assertRaises(ContractError):
            self.graph("t", reverse=True)

    def test_preserves_multiple_equivalent_mappings(self):
        schema = RelationSchema(
            "linked", 2, ("node", "node"), RoleSemantics.UNORDERED, symmetry="SYMMETRIC"
        )
        source = RelationalGraph(
            (Entity("sa", "node"), Entity("sb", "node")),
            (schema,),
            (RelationInstance("sr", "linked", ("sa", "sb")),),
        )
        target = RelationalGraph(
            (Entity("ta", "node"), Entity("tb", "node")),
            (schema,),
            (RelationInstance("tr", "linked", ("ta", "tb")),),
        )
        result = enumerate_exact_mappings(source, target)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.candidates), 2)


    def test_relation_correspondence_is_injective(self):
        schema = RelationSchema(
            "has", 1, ("node",), RoleSemantics.ORDERED_POSITIONAL
        )
        source = RelationalGraph(
            (Entity("s", "node"),),
            (schema,),
            (
                RelationInstance("sr1", "has", ("s",)),
                RelationInstance("sr2", "has", ("s",)),
            ),
        )
        target = RelationalGraph(
            (Entity("t", "node"),),
            (schema,),
            (RelationInstance("tr1", "has", ("t",)),),
        )
        result = enumerate_exact_mappings(source, target)
        self.assertEqual(result.status, "NO_MAPPING")

    def test_budget_exhaustion_never_returns_truncated_candidates(self):
        schema = RelationSchema("r", 1, ("node",), RoleSemantics.ORDERED_POSITIONAL)
        source = RelationalGraph((Entity("s", "node"),), (schema,), ())
        target = RelationalGraph(
            (Entity("t1", "node"), Entity("t2", "node")), (schema,), ()
        )
        result = enumerate_exact_mappings(source, target, candidate_budget=1)
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.candidates, ())


if __name__ == "__main__":
    unittest.main()
