"""High-order relation-learning controls for the actual LearnableSROK score path.

The balanced parity truth table isolates third-order signal: every unary and
pairwise correlation is zero, while the three-role product determines the label.
Synthetic results validate this implementation and do not imply real-world
semantic generalization.
"""
from __future__ import annotations

import itertools
import random
import unittest

from prototype.n09_learnable_srok import (
    LearnableSROK,
    Node,
    RelationClassificationExample,
    RoleSpec,
)


ROLES = tuple(RoleSpec(f"r{i}", frozenset({f"r{i}"})) for i in range(3))


def parity_rows():
    rows = []
    for bits in itertools.product((-1.0, 1.0), repeat=3):
        assignment = tuple(
            Node(f"{role.name}-{int(value)}", role.name, (value,))
            for role, value in zip(ROLES, bits)
        )
        label = 1 if bits[0] * bits[1] * bits[2] > 0 else -1
        rows.append(RelationClassificationExample(assignment, label))
    random.Random(17).shuffle(rows)
    return tuple(rows)


def random_parity_rows(count: int, seed: int):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        values = tuple(rng.uniform(-1.0, 1.0) for _ in range(3))
        assignment = tuple(
            Node(f"sample-{index}-{role.name}", role.name, (value,))
            for role, value in zip(ROLES, values)
        )
        label = 1 if values[0] * values[1] * values[2] > 0 else -1
        rows.append(RelationClassificationExample(assignment, label))
    return tuple(rows)


def accuracy(model, rows):
    hits = 0
    for row in rows:
        probability = model.predict_relation_probability(row.assignment)
        predicted = 1 if probability >= 0.5 else -1
        hits += predicted == row.label
    return hits / len(rows)


class LearnableSROKHighOrderParityTests(unittest.TestCase):
    def test_balanced_parity_requires_third_order_interaction(self):
        rows = parity_rows()
        ablated = {}
        for order in (1, 2):
            model = LearnableSROK(ROLES, feature_dim=1)
            model.fit_relation_classifier(
                rows, epochs=300, learning_rate=0.1,
                l2=1e-4, interaction_order=order,
            )
            probabilities = [
                model.predict_relation_probability(row.assignment,
                                                   interaction_order=order)
                for row in rows
            ]
            ablated[order] = sum(
                abs(value - 0.5) for value in probabilities
            ) / len(probabilities)
            self.assertAlmostEqual(accuracy_with_order(model, rows, order), 0.5, places=6)

        self.assertLess(ablated[1], 1e-8)
        self.assertLess(ablated[2], 1e-8)

        third_order = LearnableSROK(ROLES, feature_dim=1)
        history = third_order.fit_relation_classifier(
            rows, epochs=300, learning_rate=0.1,
            l2=1e-4, interaction_order=3,
        )
        self.assertLess(history[-1], history[0])
        self.assertEqual(accuracy(third_order, rows), 1.0)
        self.assertGreater(abs(third_order.weights[-1]), 0.5)

    def test_role_permutation_preserves_symmetric_parity_probability(self):
        rows = parity_rows()
        model = LearnableSROK(ROLES, feature_dim=1)
        model.fit_relation_classifier(rows, epochs=300, learning_rate=0.1)
        assignment = rows[-1].assignment
        expected = model.predict_relation_probability(assignment)
        for permutation in itertools.permutations(assignment):
            actual = model.predict_relation_probability(permutation)
            self.assertAlmostEqual(actual, expected, places=10)

    def test_relation_score_ranks_joint_candidate_retrieval(self):
        rows = parity_rows()
        model = LearnableSROK(ROLES, feature_dim=1)
        model.fit_relation_classifier(rows, epochs=300, learning_rate=0.1)
        candidates = tuple(
            Node(f"{role.name}-{value:+.0f}", role.name, (value,),
                 evidence_ids=(f"evidence-{role.name}-{value:+.0f}",))
            for role in ROLES for value in (-1.0, 1.0)
        )
        randomized_candidates = list(candidates)
        random.Random(23).shuffle(randomized_candidates)
        prediction = model.predict(
            randomized_candidates, retrieval_mode="joint", search_strategy="product",
            max_expansions=8, result_limit=3,
        )
        self.assertFalse(prediction.abstained)
        self.assertEqual(prediction.reason, "ACCEPTED")
        self.assertEqual(
            prediction.candidates[0].role_bindings,
            (("r0", "r0-+1"), ("r1", "r1-+1"), ("r2", "r2-+1")),
        )
        self.assertTrue(prediction.candidates[0].evidence_ids)

    def test_shuffled_relation_labels_destroy_held_out_parity_gain(self):
        train = random_parity_rows(1536, seed=123)
        held_out = random_parity_rows(512, seed=999)

        true_model = LearnableSROK(ROLES, feature_dim=1)
        true_model.fit_relation_classifier(
            train, epochs=1200, learning_rate=0.2, l2=1e-4,
        )
        true_accuracy = accuracy(true_model, held_out)

        shuffled_labels = [row.label for row in train]
        random.Random(321).shuffle(shuffled_labels)
        shuffled = tuple(
            RelationClassificationExample(row.assignment, label)
            for row, label in zip(train, shuffled_labels)
        )
        shuffled_model = LearnableSROK(ROLES, feature_dim=1)
        shuffled_model.fit_relation_classifier(
            shuffled, epochs=1200, learning_rate=0.2, l2=1e-4,
        )
        shuffled_accuracy = accuracy(shuffled_model, held_out)

        self.assertGreaterEqual(true_accuracy, 0.88)
        self.assertLessEqual(shuffled_accuracy, 0.65)
        self.assertGreaterEqual(true_accuracy - shuffled_accuracy, 0.2)


def accuracy_with_order(model, rows, order):
    hits = 0
    for row in rows:
        probability = model.predict_relation_probability(
            row.assignment, interaction_order=order
        )
        hits += (1 if probability >= 0.5 else -1) == row.label
    return hits / len(rows)


if __name__ == "__main__":
    unittest.main()
