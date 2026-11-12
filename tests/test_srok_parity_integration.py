"""Integration tests: parity labels trained through LearnableSROK scoring.

This composition-only suite deliberately bypasses role-wise retrieval.
"""
from itertools import product
import random
import unittest

from prototype.n09_learnable_srok import (
    LearnableSROK,
    Node,
    RelationClassificationExample,
    RoleSpec,
)


class LearnableSROKParityIntegrationTests(unittest.TestCase):
    def _roles(self):
        return tuple(RoleSpec(f"r{i}", frozenset({f"r{i}"})) for i in range(3))

    def _examples(self, seed=0, permute_roles=False):
        rng = random.Random(seed)
        rows = []
        for bits in product((-1, 1), repeat=3):
            order = list(range(3))
            if permute_roles:
                rng.shuffle(order)
            assignment = tuple(
                Node(
                    node_id=f"s{seed}-role{role}-bit{bits[role]}",
                    node_type=f"r{position}",
                    features=(float(bits[role]),),
                )
                for position, role in enumerate(order)
            )
            # Each position's type matches its role; the parity is invariant
            # under a simultaneous permutation of the role-feature pairs.
            rows.append(RelationClassificationExample(assignment, bits[0] * bits[1] * bits[2]))
        rng.shuffle(rows)
        return rows

    def _evaluate(self, model, rows, interaction_order):
        correct = 0
        for row in rows:
            probability = model.predict_relation_probability(
                row.assignment, interaction_order=interaction_order
            )
            predicted = 1 if probability >= 0.5 else -1
            correct += int(predicted == row.label)
        return correct / len(rows)

    def test_unary_and_pairwise_ablations_are_chance_third_order_learns_parity(self):
        for order in (1, 2, 3):
            model = LearnableSROK(self._roles(), feature_dim=1)
            train = self._examples(seed=11)
            history = model.fit_relation_classifier(
                train, epochs=700, learning_rate=0.12,
                interaction_order=order,
            )
            accuracy = self._evaluate(model, self._examples(seed=29), order)
            if order < 3:
                # Parity is orthogonal to all unary/pairwise features: a
                # stationary chance-level loss is the expected control.
                self.assertAlmostEqual(history[-1], history[0], places=12)
                self.assertAlmostEqual(accuracy, 0.5, places=6)
            else:
                self.assertLess(history[-1], history[0])
                self.assertEqual(accuracy, 1.0)

    def test_randomized_example_order_and_role_permutation_preserve_parity(self):
        model = LearnableSROK(self._roles(), feature_dim=1)
        train = self._examples(seed=7)
        model.fit_relation_classifier(train, epochs=700, learning_rate=0.12)
        permuted = self._examples(seed=31, permute_roles=True)
        self.assertEqual(self._evaluate(model, permuted, 3), 1.0)

    def test_learned_parity_does_not_transfer_to_a_different_pairwise_rule(self):
        model = LearnableSROK(self._roles(), feature_dim=1)
        parity_rows = self._examples(seed=43)
        model.fit_relation_classifier(
            parity_rows, epochs=700, learning_rate=0.12,
        )
        pairwise_correct = 0
        for bits in product((-1, 1), repeat=3):
            assignment = tuple(
                Node(f"held-{i}-{bits[i]}", f"r{i}", (float(bits[i]),))
                for i in range(3)
            )
            expected_pairwise = bits[0] * bits[1]
            probability = model.predict_relation_probability(assignment)
            predicted = 1 if probability >= 0.5 else -1
            pairwise_correct += int(predicted == expected_pairwise)
        self.assertEqual(pairwise_correct / 8, 0.5)


    def test_balanced_parity_training_does_not_create_unary_retrieval_signal(self):
        """Composition learning must not be mistaken for candidate retrieval learning."""
        model = LearnableSROK(self._roles(), feature_dim=1)
        model.fit_relation_classifier(
            self._examples(seed=59), epochs=700, learning_rate=0.12,
        )
        candidates = (
            Node("a-negative", "r0", (-1.0,)),
            Node("z-positive", "r0", (1.0,)),
        )
        ranked = model.retrieve(0, candidates, top_k=2)
        self.assertEqual(len(ranked), 2)
        self.assertAlmostEqual(ranked[0][1], ranked[1][1], places=10)
        # Retrieval has no parity-relevant unary evidence. Tiny floating-point
        # residuals may change the ordering, so assert score neutrality rather
        # than pinning a particular candidate ID as the winner.
        self.assertLess(abs(ranked[0][1]), 1e-10)
        self.assertLess(abs(ranked[1][1]), 1e-10)

    def test_joint_predict_uses_relations_before_unary_top_k_truncation(self):
        model = LearnableSROK(self._roles(), feature_dim=1)
        model.fit_relation_classifier(
            self._examples(seed=61), epochs=700, learning_rate=0.12,
        )
        nodes = tuple(
            Node(f"{prefix}-{role}", f"r{role}", (value,))
            for role in range(3)
            for prefix, value in (("a-negative", -1.0), ("z-positive", 1.0))
        )
        unary = model.predict(nodes, top_k_per_role=1, result_limit=1)
        joint = model.predict(
            nodes, top_k_per_role=1, max_expansions=8,
            result_limit=8, retrieval_mode="joint",
        )
        self.assertEqual(unary.role_pool_sizes, (("r0", 1), ("r1", 1), ("r2", 1)))
        self.assertEqual(joint.role_pool_sizes, (("r0", 2), ("r1", 2), ("r2", 2)))
        self.assertEqual(joint.expanded_assignments, 8)
        self.assertFalse(joint.budget_exhausted)
        self.assertTrue(joint.candidates)
        best = joint.candidates[0]
        selected = dict(best.role_bindings)
        selected_nodes = [next(node for node in nodes if node.node_id == selected[f"r{i}"]) for i in range(3)]
        parity = selected_nodes[0].features[0] * selected_nodes[1].features[0] * selected_nodes[2].features[0]
        self.assertEqual(parity, 1.0)
        self.assertGreater(best.score, unary.candidates[0].score)

    def test_joint_predict_rejects_unknown_retrieval_mode(self):
        model = LearnableSROK(self._roles(), feature_dim=1)
        with self.assertRaises(ValueError):
            model.predict((), retrieval_mode="oracle")

    def test_invalid_labels_and_incomplete_assignments_are_rejected(self):
        model = LearnableSROK(self._roles(), feature_dim=1)
        node = Node("a", "r0", (1.0,))
        with self.assertRaises(ValueError):
            model.fit_relation_classifier(
                [RelationClassificationExample((node,), 1)], epochs=1
            )
        with self.assertRaises(ValueError):
            model.fit_relation_classifier(
                [RelationClassificationExample(
                    (node, Node("b", "r1", (1.0,)), Node("c", "r2", (1.0,))), 0
                )], epochs=1
            )


if __name__ == "__main__":
    unittest.main()
