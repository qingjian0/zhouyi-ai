import unittest

from prototype.yijing_hypergraph_induction import (
    Entity, Hyperedge, HypergraphState, RoleBinding,
)
from prototype.yijing_hypergraph_role_induction import RelationSymmetry
from prototype.yijing_hypergraph_automorphism import (
    AutomorphismOracleError, exact_hypergraph_automorphism_audit,
)


def state(entities, edges):
    return HypergraphState(
        tuple(Entity(entity_id, entity_type) for entity_id, entity_type in entities),
        tuple(edges), (), 0, "snapshot", "synthetic", True,
    )


def edge(edge_id, relation, participants, roles=None, semantics_attrs=()):
    roles = roles or tuple(f"arg-{i}" for i in range(len(participants)))
    return Hyperedge(
        edge_id, relation,
        tuple(RoleBinding(role, entity) for role, entity in zip(roles, participants)),
        (f"evidence-{edge_id}",), attributes=semantics_attrs,
    )


class ExactHypergraphAutomorphismTests(unittest.TestCase):
    def test_single_unordered_nary_edge_has_full_symmetric_orbit(self):
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (edge("e", "joint", ("a", "b", "c")),),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("joint", "UNORDERED"),)
        )
        self.assertEqual(report.candidate_bijections, 6)
        self.assertEqual(report.automorphism_count, 6)
        self.assertEqual(report.exact_orbits, (("a", "b", "c"),))
        self.assertEqual(report.pairwise_false_merge, 0)
        self.assertEqual(report.pairwise_false_split, 0)

    def test_ordered_single_edge_distinguishes_argument_positions(self):
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (edge("e", "sequence", ("a", "b", "c")),),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("sequence", "ORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 1)
        self.assertEqual(report.exact_orbits, (("a",), ("b",), ("c",)))

    def test_directed_cycle_has_one_three_node_orbit(self):
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (
                edge("ab", "next", ("a", "b")),
                edge("bc", "next", ("b", "c")),
                edge("ca", "next", ("c", "a")),
            ),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("next", "ORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 3)
        self.assertEqual(report.exact_orbits, (("a", "b", "c"),))
        self.assertEqual(report.wl_pairwise_recall, 1.0)

    def test_undirected_path_has_two_partial_symmetry_orbits(self):
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node"), ("d", "node")),
            (
                edge("ab", "link", ("a", "b")),
                edge("bc", "link", ("b", "c")),
                edge("cd", "link", ("c", "d")),
            ),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("link", "UNORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 2)
        self.assertEqual(report.exact_orbits, (("a", "d"), ("b", "c")))

    def test_directed_path_has_three_singleton_orbits(self):
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (
                edge("ab", "next", ("a", "b")),
                edge("bc", "next", ("b", "c")),
            ),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("next", "ORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 1)
        self.assertEqual(report.exact_orbits, (("a",), ("b",), ("c",)))

    def test_role_names_and_entity_names_are_not_semantic(self):
        left = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (edge("e", "joint", ("a", "b", "c"), ("x", "y", "z")),),
        )
        right = state(
            (("u", "node"), ("v", "node"), ("w", "node")),
            (edge("other", "joint", ("u", "v", "w"), ("p", "q", "r")),),
        )
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        a = exact_hypergraph_automorphism_audit(left, policy)
        b = exact_hypergraph_automorphism_audit(right, policy)
        self.assertEqual(
            tuple(map(len, a.exact_orbits)),
            tuple(map(len, b.exact_orbits)),
        )

    def test_entity_types_constrain_automorphisms(self):
        graph = state(
            (("a", "agent"), ("b", "tool"), ("c", "agent")),
            (edge("e", "joint", ("a", "b", "c")),),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("joint", "UNORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 2)
        self.assertEqual(report.exact_orbits, (("a", "c"), ("b",)))

    def test_edge_context_and_attributes_are_preserved(self):
        left = edge("left", "joint", ("a", "b"), semantics_attrs=(("mode", "x"),))
        right = edge("right", "joint", ("b", "c"), semantics_attrs=(("mode", "y"),))
        graph = state(
            (("a", "node"), ("b", "node"), ("c", "node")),
            (left, right),
        )
        report = exact_hypergraph_automorphism_audit(
            graph, (RelationSymmetry("joint", "UNORDERED"),)
        )
        self.assertEqual(report.automorphism_count, 1)

    def test_missing_policy_fails_closed(self):
        graph = state(
            (("a", "node"), ("b", "node")),
            (edge("e", "joint", ("a", "b")),),
        )
        with self.assertRaises(AutomorphismOracleError):
            exact_hypergraph_automorphism_audit(graph, ())

    def test_exact_search_budget_fails_closed(self):
        graph = state(
            tuple((f"n{i}", "node") for i in range(7)),
            (),
        )
        with self.assertRaises(AutomorphismOracleError):
            exact_hypergraph_automorphism_audit(
                graph, (), max_candidate_bijections=1000
            )


if __name__ == "__main__":
    unittest.main()
