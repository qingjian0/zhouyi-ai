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


    def test_beam_pruning_never_reports_a_global_acceptance(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (float(i), 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(3)
        ]
        result = model.predict(
            nodes, retrieval_mode="joint", search_strategy="beam",
            beam_width=1, max_expansions=100, result_limit=3,
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.reason, "BEAM_PRUNED")
        self.assertFalse(result.budget_exhausted)
        self.assertLess(result.expanded_assignments, 27)

    def test_beam_budget_exhaustion_is_distinct_from_pruning(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (float(i), 0.0, 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(3)
        ]
        result = model.predict(
            nodes, retrieval_mode="joint", search_strategy="beam",
            beam_width=2, max_expansions=2, result_limit=3,
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.reason, "SEARCH_BUDGET_EXHAUSTED")
        self.assertTrue(result.budget_exhausted)
        self.assertEqual(result.expanded_assignments, 2)

    def test_exact_product_vs_beam_recall_and_expansion_tradeoff(self):
        # Adversarial higher-order fixture: only the all-signal assignment
        # receives a positive third-order score. Prefixes have no unary or
        # pairwise signal, so a narrow beam has no admissible way to retain
        # the globally best branch. This measures the recall/cost tradeoff;
        # it is not a general-purpose performance claim.
        for pool_size in (3, 5, 8):
            model = LearnableSROK(self.roles, feature_dim=1)
            model.weights[6] = 1.0  # the sole third-order interaction weight
            nodes = []
            for role in ("r0", "r1", "r2"):
                nodes.extend(
                    Node(
                        f"a-{role}-decoy-{index}", role, (0.0,),
                        frozenset({"eligible"}),
                    )
                    for index in range(pool_size - 1)
                )
                nodes.append(
                    Node(f"z-{role}-signal", role, (1.0,), frozenset({"eligible"}))
                )

            exact = model.predict(
                nodes, retrieval_mode="joint", search_strategy="product",
                max_expansions=pool_size ** 3, result_limit=1,
            )
            beam = model.predict(
                nodes, retrieval_mode="joint", search_strategy="beam",
                beam_width=1, max_expansions=pool_size ** 3, result_limit=1,
            )

            self.assertFalse(exact.abstained)
            self.assertEqual(
                exact.candidates[0].role_bindings,
                (("r0", f"z-r0-signal"), ("r1", f"z-r1-signal"),
                 ("r2", f"z-r2-signal")),
            )
            self.assertTrue(beam.abstained)
            self.assertEqual(beam.reason, "BEAM_PRUNED")
            self.assertNotEqual(
                beam.candidates[0].role_bindings,
                exact.candidates[0].role_bindings,
            )
            self.assertEqual(exact.expanded_search_states, pool_size ** 3)
            self.assertEqual(beam.expanded_search_states, 3 * pool_size)
            # The legacy field remains available for compatibility.
            self.assertEqual(beam.expanded_assignments, beam.expanded_search_states)
            self.assertLess(
                beam.expanded_search_states, exact.expanded_search_states
            )

    def test_beam_search_is_deterministic_under_input_permutation(self):
        model = LearnableSROK(self.roles, feature_dim=3)
        nodes = [
            Node(f"{role}-{i}", role, (float(i), float(i % 2), 0.0), frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for i in range(3)
        ]
        first = model.predict(
            nodes, retrieval_mode="joint", search_strategy="beam",
            beam_width=3, max_expansions=100, result_limit=5,
        )
        second = model.predict(
            list(reversed(nodes)), retrieval_mode="joint", search_strategy="beam",
            beam_width=3, max_expansions=100, result_limit=5,
        )
        self.assertEqual(first.reason, second.reason)
        self.assertEqual(first.expanded_assignments, second.expanded_assignments)
        self.assertEqual(
            [candidate.role_bindings for candidate in first.candidates],
            [candidate.role_bindings for candidate in second.candidates],
        )


if __name__ == "__main__":
    unittest.main()
