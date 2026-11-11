import json
import unittest

from prototype.n4a_relation_discovery import (
    DiscoveryError, Edge, Node, RelationalCase, discover_relations,
)


def make_case(case_id, partition, outcome, domain="domain-a", rename=""):
    nodes = (
        Node(rename + "n1", "surface-source", ("initiator",)),
        Node(rename + "n2", "surface-middle", ("mediator",)),
        Node(rename + "n3", "surface-target", ("receiver",)),
        Node(rename + "n4", "noise", ("context",)),
    )
    if outcome:
        edges = (
            Edge(rename + "n1", rename + "n2", "influence"),
            Edge(rename + "n2", rename + "n3", "transforms"),
            Edge(rename + "n4", rename + "n1", "contextualizes"),
        )
    else:
        edges = (Edge(rename + "n4", rename + "n1", "contextualizes"),)
    return RelationalCase(
        case_id, domain, "causal-process", partition, outcome, nodes, edges
    )


def balanced_dataset():
    cases = []
    for i in range(4):
        cases.append(make_case(f"train-pos-{i}", "train", True,
                               "mechanical" if i % 2 else "ecological"))
        cases.append(make_case(f"train-neg-{i}", "train", False))
    for i in range(3):
        cases.append(make_case(f"valid-pos-{i}", "validation", True,
                               "economic" if i % 2 else "biological",
                               rename=f"v{i}-"))
        cases.append(make_case(f"valid-neg-{i}", "validation", False,
                               rename=f"n{i}-"))
    return cases


class N4ARelationDiscoveryTests(unittest.TestCase):
    def test_discovers_cross_domain_connected_motif_with_heldout_lift(self):
        result = discover_relations(
            balanced_dataset(), min_train_support=3,
            min_validation_support=2, min_validation_lift=0.2,
            max_nodes=3,
        )
        self.assertTrue(result.candidates)
        candidate = next(c for c in result.candidates if c.role_count == 3)
        self.assertEqual(len(candidate.support_case_ids), 4)
        self.assertEqual(len(candidate.validation_positive_ids), 3)
        self.assertEqual(len(candidate.validation_negative_ids), 0)
        self.assertEqual(candidate.validation_precision, 1.0)
        self.assertGreaterEqual(len(candidate.domains), 4)
        self.assertEqual(len(candidate.instances), 7)

    def test_surface_names_and_node_ids_do_not_change_motif_signature(self):
        a = make_case("a", "train", True, rename="left-")
        b = make_case("b", "train", True, domain="other", rename="right-")
        result = discover_relations(
            [a, b, make_case("c", "train", True),
             make_case("v1", "validation", True),
             make_case("v2", "validation", True),
             make_case("vn1", "validation", False),
             make_case("vn2", "validation", False)],
            min_train_support=2, min_validation_support=2,
            min_validation_lift=0.1, max_nodes=3,
        )
        three = [c for c in result.candidates if c.role_count == 3]
        target = [
            c for c in three
            if {tuple(role) for role in json.loads(c.signature)["roles"]} == {
                ("initiator",), ("mediator",), ("receiver",)
            }
        ]
        self.assertEqual(len(target), 1)

    def test_counterexamples_are_retained(self):
        cases = balanced_dataset()
        cases.append(make_case("train-false-motif", "train", True))
        # Flip the outcome while retaining the same structure to force a
        # structural counterexample; no candidate may discard it.
        original = cases[-1]
        cases[-1] = RelationalCase(
            original.case_id, original.domain, original.scope,
            original.partition, False, original.nodes, original.edges,
        )
        result = discover_relations(
            cases, min_train_support=3, min_validation_support=2,
            min_validation_lift=0.1, max_nodes=3,
        )
        candidate = next(c for c in result.candidates if c.role_count == 3)
        self.assertIn("train-false-motif", candidate.counterexample_case_ids)
        self.assertLess(candidate.train_precision, 1.0)

    def test_scope_prevents_unintended_cross_context_mining(self):
        cases = balanced_dataset()
        cases = [
            RelationalCase(c.case_id, c.domain, "different-scope",
                           c.partition, c.outcome, c.nodes, c.edges)
            if c.partition == "validation" else c
            for c in cases
        ]
        result = discover_relations(
            cases, min_train_support=3, min_validation_support=2,
            min_validation_lift=0.1, max_nodes=3,
        )
        self.assertFalse(result.candidates)

    def test_subset_budget_is_explicit_and_reported(self):
        result = discover_relations(
            balanced_dataset(), min_train_support=3,
            min_validation_support=2, max_nodes=4,
            max_subsets_per_case=1,
        )
        self.assertGreater(result.motifs_over_budget, 0)

    def test_rejects_duplicate_case_ids_and_invalid_partitions(self):
        case = make_case("dup", "train", True)
        with self.assertRaises(DiscoveryError):
            discover_relations([case, case])
        invalid = RelationalCase(
            "bad", "domain", "scope", "test", True,
            case.nodes, case.edges,
        )
        with self.assertRaises(DiscoveryError):
            discover_relations([invalid])

    def test_requires_explicit_abstract_role_features(self):
        case = make_case("bad-role", "train", True)
        bad_nodes = (Node("x", "thing", ()),) + case.nodes[1:]
        invalid = RelationalCase(
            case.case_id, case.domain, case.scope, case.partition,
            case.outcome, bad_nodes, case.edges,
        )
        with self.assertRaises(DiscoveryError):
            discover_relations([invalid])

    def test_rejects_unconnected_and_missing_endpoint_edges(self):
        case = make_case("bad-edge", "train", True)
        invalid = RelationalCase(
            case.case_id, case.domain, case.scope, case.partition,
            case.outcome, case.nodes,
            (Edge("missing", "n1", "relation"),),
        )
        with self.assertRaises(DiscoveryError):
            discover_relations([invalid])

    def test_symmetric_roles_report_ambiguous_mapping(self):
        def symmetric(case_id, partition, outcome, prefix=""):
            nodes = (
                Node(prefix + "a", "surface-a", ("same-role",)),
                Node(prefix + "b", "surface-b", ("same-role",)),
            )
            edges = (
                (
                    Edge(prefix + "a", prefix + "b", "mutual"),
                    Edge(prefix + "b", prefix + "a", "mutual"),
                ) if outcome else ()
            )
            return RelationalCase(
                case_id, "domain", "symmetry", partition, outcome, nodes, edges
            )
        cases = [
            symmetric("t1", "train", True),
            symmetric("t2", "train", True, "x"),
            symmetric("t3", "train", True, "y"),
            symmetric("v1", "validation", True),
            symmetric("v2", "validation", True, "x"),
            symmetric("vn1", "validation", False, "n"),
            symmetric("vn2", "validation", False, "m"),
        ]
        result = discover_relations(
            cases, min_train_support=2, min_validation_support=2,
            min_validation_lift=0.1, max_nodes=2,
        )
        self.assertTrue(result.candidates)
        self.assertTrue(all(i.mapping_ambiguous
                            for i in result.candidates[0].instances))

    def test_budget_truncation_discards_partial_case_motifs(self):
        result = discover_relations(
            balanced_dataset(), min_train_support=2,
            min_validation_support=2, min_validation_lift=0.0,
            max_nodes=3, max_subsets_per_case=1,
        )
        self.assertGreater(result.motifs_over_budget, 0)
        self.assertFalse(result.candidates)


if __name__ == "__main__":
    unittest.main()
