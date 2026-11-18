"""Independent exhaustive d-separation oracle checks for M61.

The reference oracle enumerates simple undirected paths and applies the
active-trail collider rule. It is intentionally independent of the production
ancestral-moralization implementation.
"""
import itertools
import unittest

from prototype.yixiang_m60_causal_transfer import (
    _d_separated,
    infer_backdoor_set,
)


def _reference_d_separated(nodes, edges, left, right, conditioned):
    edge_set = set(edges)
    conditioned = set(conditioned)
    if left in conditioned or right in conditioned:
        return False

    parents = {node: set() for node in nodes}
    adjacency = {node: set() for node in nodes}
    for source, target in edges:
        parents[target].add(source)
        adjacency[source].add(target)
        adjacency[target].add(source)

    ancestors_of_conditioned = set(conditioned)
    pending = list(conditioned)
    while pending:
        node = pending.pop()
        for parent in parents[node]:
            if parent not in ancestors_of_conditioned:
                ancestors_of_conditioned.add(parent)
                pending.append(parent)

    def path_is_active(path):
        for index in range(1, len(path) - 1):
            previous, current, following = path[index - 1:index + 2]
            collider = ((previous, current) in edge_set
                        and (following, current) in edge_set)
            if collider:
                if current not in ancestors_of_conditioned:
                    return False
            elif current in conditioned:
                return False
        return True

    def has_active_path(path):
        current = path[-1]
        if current == right:
            return path_is_active(path)
        for neighbor in adjacency[current]:
            if neighbor not in path and has_active_path(path + [neighbor]):
                return True
        return False

    return not has_active_path([left])


def _all_four_node_dags():
    nodes = ("A", "B", "C", "D")
    pairs = tuple(itertools.combinations(range(len(nodes)), 2))
    graphs = set()
    # Every DAG has at least one topological ordering. Enumerating every
    # ordering and every forward-edge subset therefore covers all labeled DAGs.
    for order in itertools.permutations(nodes):
        for mask in range(1 << len(pairs)):
            edges = tuple(sorted(
                (order[i], order[j])
                for bit, (i, j) in enumerate(pairs)
                if mask & (1 << bit)
            ))
            graphs.add(edges)
    return nodes, sorted(graphs)


class M61IndependentDSeparationTests(unittest.TestCase):
    def test_exhaustive_four_node_dags_match_active_trail_oracle(self):
        nodes, graphs = _all_four_node_dags()
        comparisons = 0
        for edges in graphs:
            for left, right in itertools.combinations(nodes, 2):
                remaining = [node for node in nodes if node not in (left, right)]
                for size in range(len(remaining) + 1):
                    for conditioned in itertools.combinations(remaining, size):
                        expected = _reference_d_separated(
                            nodes, edges, left, right, conditioned
                        )
                        actual = _d_separated(
                            nodes, edges, left, right, conditioned
                        )
                        self.assertEqual(
                            actual, expected,
                            msg=(f"nodes={nodes}, edges={edges}, "
                                 f"query=({left},{right}), Z={conditioned}"),
                        )
                        comparisons += 1
        self.assertGreaterEqual(len(graphs), 500)
        self.assertGreater(comparisons, 10000)

    def test_disconnected_treatment_and_outcome_need_empty_adjustment(self):
        case = {
            "dag": {"nodes": ["X", "Y", "U"], "edges": []},
            "observed_variables": ["X", "Y", "U"],
            "query": {"exposure": "X", "outcome": "Y"},
        }
        result = infer_backdoor_set(case)
        self.assertTrue(result["backdoor_identified"])
        self.assertEqual(result["adjustment_set"], [])

    def test_multiple_minimum_adjustment_sets_are_supported(self):
        case = {
            "dag": {
                "nodes": ["X", "Y", "U", "V", "A", "B"],
                "edges": [
                    ["U", "X"], ["U", "A"], ["A", "Y"],
                    ["V", "X"], ["V", "B"], ["B", "Y"],
                ],
            },
            "observed_variables": ["X", "Y", "U", "V", "A", "B"],
            "query": {"exposure": "X", "outcome": "Y"},
        }
        result = infer_backdoor_set(case)
        self.assertTrue(result["backdoor_identified"])
        self.assertEqual(len(result["adjustment_set"]), 2)
        self.assertIn(result["adjustment_set"], [
            ["U", "V"], ["U", "B"], ["A", "V"], ["A", "B"]
        ])

    def test_search_budget_boundary_is_explicit(self):
        def case_with_candidates(count):
            candidates = [f"C{i:02d}" for i in range(count)]
            nodes = ["X", "Y", *candidates]
            # Keep the within-budget graph disconnected so the empty set is
            # found immediately; the test checks the 18/19 cutoff, not the
            # worst-case 2^18 search runtime.
            return {
                "dag": {"nodes": nodes, "edges": []},
                "observed_variables": nodes,
                "query": {"exposure": "X", "outcome": "Y"},
            }

        within = infer_backdoor_set(case_with_candidates(18))
        over = infer_backdoor_set(case_with_candidates(19))
        self.assertTrue(within["backdoor_identified"])
        self.assertEqual(within["adjustment_set"], [])
        self.assertFalse(over["backdoor_identified"])
        self.assertEqual(over["reason"], "adjustment_search_budget_exceeded")


if __name__ == "__main__":
    unittest.main()
