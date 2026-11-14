"""Tests for the N0.10 learnable role-conditioned SROK prototype."""
import random
import unittest

from prototype.n09_learnable_srok import (
    LearnableSROK, LearnableSROKError, Node, RoleSpec, TrainingExample,
)


def make_training(seed, count=48):
    rng = random.Random(seed)
    examples = []
    roles = ("r0", "r1", "r2")
    for sample in range(count):
        pools = []
        targets = []
        for role_index, role in enumerate(roles):
            candidates = []
            for candidate_index in range(4):
                values = [rng.uniform(-1.0, 1.0) for _ in range(3)]
                if candidate_index == 0:
                    values[role_index] = 2.5 + rng.random()
                node = Node(
                    node_id=f"{sample}-{role}-{candidate_index}",
                    node_type=role,
                    features=tuple(values),
                    tags=frozenset({"eligible"}),
                    evidence_ids=(f"ev-{sample}-{role}-{candidate_index}",),
                )
                candidates.append(node)
            pools.append(tuple(candidates))
            targets.append(candidates[0].node_id)
        examples.append(TrainingExample(tuple(pools), tuple(targets)))
    return examples


class LearnableSROKTests(unittest.TestCase):
    def setUp(self):
        self.roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
            for name in ("r0", "r1", "r2")
        )

    def test_learns_role_conditioned_retrieval_and_exact_structure(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        train = make_training(13, 64)
        history = model.fit(train, epochs=100, learning_rate=0.18)
        self.assertLess(history[-1], history[0])
        correct = 0
        for example in make_training(29, 24):
            nodes = tuple(node for pool in example.role_candidates for node in pool)
            prediction = model.predict(nodes, top_k_per_role=4, result_limit=2)
            self.assertFalse(prediction.abstained)
            got = tuple(node_id for _, node_id in prediction.candidates[0].role_bindings)
            correct += int(got == example.target_ids)
        self.assertGreaterEqual(correct / 24, 0.95)

    def test_hard_type_and_tag_constraints_are_not_learned_away(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node("wrong-type", "r1", (9.0, 9.0, 9.0), frozenset({"eligible"})),
            Node("wrong-tag", "r0", (9.0, 9.0, 9.0), frozenset()),
            Node("right", "r0", (0.0, 0.0, 0.0), frozenset({"eligible"})),
        ]
        retrieved = model.retrieve(0, nodes, top_k=5)
        self.assertEqual([node.node_id for node, _ in retrieved], ["right"])

    def test_third_order_features_are_explicit(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        assignment = (
            Node("a", "r0", (1.0, 2.0)),
            Node("b", "r1", (3.0, 4.0)),
            Node("c", "r2", (5.0, 6.0)),
        )
        features = model._assignment_features(assignment)
        self.assertEqual(len(features), 14)
        self.assertEqual(features[-2:], [15.0, 48.0])

    def test_abstains_when_margin_is_below_threshold(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (0.0, 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(2)
        ]
        result = model.predict(nodes, top_k_per_role=2, abstain_margin=0.01)
        self.assertTrue(result.abstained)
        self.assertEqual(result.reason, "LOW_SCORE_MARGIN")

    def test_exact_score_tie_abstains_at_zero_margin(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (0.0, 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(2)
        ]
        result = model.predict(nodes, top_k_per_role=2, result_limit=2)
        self.assertTrue(result.abstained)
        self.assertEqual(result.reason, "LOW_SCORE_MARGIN")

    def test_abstention_still_applies_when_result_limit_is_one(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (0.0, 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(2)
        ]
        result = model.predict(
            nodes, top_k_per_role=2, result_limit=1, abstain_margin=0.01
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.reason, "LOW_SCORE_MARGIN")

    def test_non_finite_interaction_feature_is_rejected(self):
        model = LearnableSROK(self.roles, feature_dim=1)
        assignment = (
            Node("a", "r0", (1e308,)),
            Node("b", "r1", (1e308,)),
            Node("c", "r2", (1e308,)),
        )
        with self.assertRaises(LearnableSROKError):
            model.score(assignment)

    def test_invalid_optimizer_and_prediction_budgets_are_rejected(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        with self.assertRaises(LearnableSROKError):
            model.fit(make_training(1, 2), epochs=True)
        with self.assertRaises(LearnableSROKError):
            model.fit(make_training(1, 2), learning_rate=float("nan"))
        with self.assertRaises(LearnableSROKError):
            model.predict((), top_k_per_role=1.5)

    def test_duplicate_assignments_consume_expansion_budget(self):
        model = LearnableSROK(
            (RoleSpec("left"), RoleSpec("right")), feature_dim=1
        )
        nodes = (
            Node("a", "x", (0.0,)),
            Node("b", "x", (0.0,)),
        )
        result = model.predict(
            nodes, top_k_per_role=2, max_expansions=2, result_limit=2
        )
        self.assertEqual(result.expanded_assignments, 2)
        self.assertTrue(result.budget_exhausted)

    def test_reports_budget_exhaustion(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (float(i), 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(3)
        ]
        result = model.predict(nodes, top_k_per_role=3, max_expansions=2)
        self.assertTrue(result.budget_exhausted)
        self.assertEqual(result.expanded_assignments, 2)

    def test_rejects_duplicate_ids_inside_training_role_pool(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        duplicate = Node(
            "same", "r0", (1.0, 0.0, 0.0), frozenset({"eligible"})
        )
        example = TrainingExample(
            role_candidates=(
                (duplicate, duplicate),
                (Node("b", "r1", (0.0, 1.0, 0.0), frozenset({"eligible"})),),
                (Node("c", "r2", (0.0, 0.0, 1.0), frozenset({"eligible"})),),
            ),
            target_ids=("same", "b", "c"),
        )
        with self.assertRaises(LearnableSROKError):
            model.fit([example], epochs=1)

    def test_rejects_duplicate_ids_and_invalid_training(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        duplicate = Node("same", "r0", (1.0, 0.0, 0.0))
        with self.assertRaises(LearnableSROKError):
            model.predict([duplicate, duplicate])
        with self.assertRaises(LearnableSROKError):
            model.fit([], epochs=1)


if __name__ == "__main__":
    unittest.main()
