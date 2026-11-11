import unittest

from prototype.srok0_kernel import Node as SrokNode
from prototype.yixiang_analogy import Relation
from prototype.yixiang_role_transform import RoleTransform
from prototype.yixiang_srok_adapter import (
    compile_yixiang_operator,
    propose_yixiang_compositions,
)


class YixiangSrokAdapterTests(unittest.TestCase):
    def setUp(self):
        self.relation = Relation("causes", ("actor-a", "state-a"))
        self.transform = RoleTransform(
            "cause-effect-role-view",
            "1.0.0",
            "causes",
            "effect_of",
            (1, 0),
            scope_conditions=("domain:causal-relations",),
            evidence_refs=("evidence:transform-prior",),
        )
        self.nodes = (
            SrokNode("actor-a", "actor", evidence_ids=("obs:1",)),
            SrokNode("actor-b", "actor", evidence_ids=("obs:2",)),
            SrokNode("state-a", "state", evidence_ids=("obs:3",)),
            SrokNode("state-b", "state", evidence_ids=("obs:4",)),
        )

    def test_explicit_yixiang_permutation_compiles_to_typed_srok_roles(self):
        compiled = compile_yixiang_operator(self.relation, self.transform, self.nodes)
        self.assertEqual(compiled.operator_spec.relation_type, "effect_of")
        self.assertEqual(compiled.source_argument_positions, (1, 0))
        first, second = compiled.operator_spec.roles
        self.assertEqual(first.name, "target_arg_0_from_source_arg_1")
        self.assertEqual(first.allowed_types, frozenset({"state"}))
        self.assertEqual(second.name, "target_arg_1_from_source_arg_0")
        self.assertEqual(second.allowed_types, frozenset({"actor"}))
        self.assertEqual(compiled.semantic_status, "HYPOTHESIS_ONLY")

    def test_srok_candidates_preserve_declared_target_role_types(self):
        result = propose_yixiang_compositions(self.relation, self.transform, self.nodes, limit=10)
        self.assertEqual(result.application.transformed_relation, Relation("effect_of", ("state-a", "actor-a")))
        self.assertEqual(result.application.semantic_status, "HYPOTHESIS_ONLY")
        self.assertEqual(result.search.candidates[0].relation_type, "effect_of")
        type_by_id = {node.node_id: node.node_type for node in self.nodes}
        for candidate in result.search.candidates:
            bindings = dict(candidate.role_bindings)
            self.assertEqual(type_by_id[bindings["target_arg_0_from_source_arg_1"]], "state")
            self.assertEqual(type_by_id[bindings["target_arg_1_from_source_arg_0"]], "actor")

    def test_node_scores_change_ranking_without_changing_role_contract(self):
        result = propose_yixiang_compositions(
            self.relation, self.transform, self.nodes,
            node_scores={"actor-b": 10.0, "state-b": 8.0}, limit=4,
        )
        top = result.search.candidates[0]
        self.assertEqual(dict(top.role_bindings), {
            "target_arg_0_from_source_arg_1": "state-b",
            "target_arg_1_from_source_arg_0": "actor-b",
        })

    def test_unknown_node_score_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown workspace nodes"):
            propose_yixiang_compositions(
                self.relation, self.transform, self.nodes, node_scores={"missing": 1.0}
            )

    def test_missing_source_node_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing from workspace"):
            compile_yixiang_operator(self.relation, self.transform, (self.nodes[0], self.nodes[1], self.nodes[3]))

    def test_relation_type_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "source relation type"):
            compile_yixiang_operator(Relation("owns", ("actor-a", "state-a")), self.transform, self.nodes)

    def test_budget_exhaustion_is_reported_not_hidden(self):
        result = propose_yixiang_compositions(
            self.relation, self.transform, self.nodes, max_expansions=1, limit=10
        )
        self.assertTrue(result.search.budget_exhausted)


if __name__ == "__main__":
    unittest.main()
