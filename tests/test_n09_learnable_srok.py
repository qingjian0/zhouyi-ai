"""Tests for the N0.10 learnable role-conditioned SROK prototype."""
import random
import unittest
from itertools import product

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

    def test_seeded_mixed_interaction_beam_recall_sweep(self):
        # Deterministic synthetic sweep across seeds, candidate-pool sizes,
        # and beam widths. Exact Cartesian search is the top-k reference.
        # Randomized unary/pairwise/third-order weights create mixed signals;
        # this is a controlled retrieval benchmark, not a natural-language
        # or real-world generalization claim.
        seeds = (11, 23, 47, 89, 131)
        pool_sizes = (3, 5, 8)
        beam_widths = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
        recalls = []
        top1_hits = []
        expansion_ratios = []
        abstentions = 0
        complete_searches = 0
        complete_recalls = []
        complete_top1_hits = []
        comparisons = 0

        for seed in seeds:
            rng = random.Random(seed)
            for pool_size in pool_sizes:
                model = LearnableSROK(self.roles, feature_dim=2)
                model.weights = [
                    rng.uniform(-0.8, 0.8) for _ in model.weights
                ]
                nodes = []
                for role in ("r0", "r1", "r2"):
                    for index in range(pool_size):
                        features = (
                            rng.gauss(0.0, 1.0),
                            rng.gauss(0.0, 1.0),
                        )
                        nodes.append(Node(
                            f"{role}-{index}", role, features,
                            frozenset({"eligible"}),
                        ))

                exact = model.predict(
                    nodes, retrieval_mode="joint", search_strategy="product",
                    max_expansions=pool_size ** 3, result_limit=5,
                )
                self.assertEqual(exact.expanded_search_states, pool_size ** 3)
                exact_top_k = {
                    candidate.role_bindings for candidate in exact.candidates
                }
                self.assertTrue(exact_top_k)

                for beam_width in beam_widths:
                    beam = model.predict(
                        nodes, retrieval_mode="joint", search_strategy="beam",
                        beam_width=beam_width, max_expansions=10_000,
                        result_limit=5,
                    )
                    reversed_beam = model.predict(
                        list(reversed(nodes)), retrieval_mode="joint",
                        search_strategy="beam", beam_width=beam_width,
                        max_expansions=10_000, result_limit=5,
                    )
                    beam_top_k = {
                        candidate.role_bindings for candidate in beam.candidates
                    }
                    recall = len(exact_top_k & beam_top_k) / len(exact_top_k)
                    top1 = int(
                        bool(beam.candidates)
                        and beam.candidates[0].role_bindings
                        == exact.candidates[0].role_bindings
                    )
                    self.assertGreaterEqual(recall, 0.0)
                    self.assertLessEqual(recall, 1.0)
                    self.assertLessEqual(
                        beam.expanded_search_states, 10_000
                    )
                    self.assertEqual(beam.reason, reversed_beam.reason)
                    self.assertEqual(
                        beam.expanded_search_states,
                        reversed_beam.expanded_search_states,
                    )
                    self.assertEqual(
                        [item.role_bindings for item in beam.candidates],
                        [item.role_bindings for item in reversed_beam.candidates],
                    )
                    if beam_width >= pool_size ** 3:
                        # A width at least as large as the complete product
                        # retains every prefix and must match exact ranking.
                        self.assertEqual(beam.abstained, exact.abstained)
                        self.assertEqual(beam.reason, exact.reason)
                        self.assertEqual(
                            [item.role_bindings for item in beam.candidates],
                            [item.role_bindings for item in exact.candidates],
                        )
                        self.assertEqual(recall, 1.0)
                        self.assertEqual(top1, 1)
                        complete_searches += 1
                        complete_recalls.append(recall)
                        complete_top1_hits.append(top1)

                    recalls.append(recall)
                    top1_hits.append(top1)
                    expansion_ratios.append(
                        beam.expanded_search_states / exact.expanded_search_states
                    )
                    abstentions += int(beam.abstained)
                    comparisons += 1

        mean_recall = sum(recalls) / comparisons
        mean_top1 = sum(top1_hits) / comparisons
        mean_expansion_ratio = sum(expansion_ratios) / comparisons
        abstention_rate = abstentions / comparisons
        print(
            "CPG_EI_SEEDED_SWEEP "
            f"comparisons={comparisons} "
            f"recall_at_5={mean_recall:.4f} "
            f"top1_hit={mean_top1:.4f} "
            f"expansion_ratio={mean_expansion_ratio:.4f} "
            f"abstention_rate={abstention_rate:.4f} "
            f"complete_search_rate={complete_searches / comparisons:.4f} "
            f"complete_recall_at_5={(sum(complete_recalls) / len(complete_recalls)) if complete_recalls else 0.0:.4f} "
            f"complete_top1_hit={(sum(complete_top1_hits) / len(complete_top1_hits)) if complete_top1_hits else 0.0:.4f}"
        )
        self.assertEqual(comparisons, 150)
        self.assertEqual(complete_searches, 45)

    def test_partial_upper_bound_dominates_every_completion(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        rng = random.Random(731)
        model.weights = [
            rng.uniform(-1.5, 1.5) for _ in model.weights
        ]
        pools = tuple(
            tuple(
                Node(
                    f"{role}-{index}", role,
                    (rng.uniform(-2.0, 2.0), rng.uniform(-2.0, 2.0)),
                    frozenset({"eligible"}),
                )
                for index in range(3)
            )
            for role in ("r0", "r1", "r2")
        )

        for prefix_size in range(len(self.roles) + 1):
            for prefix in product(*pools[:prefix_size]):
                bound = model._assignment_upper_bound(prefix, pools)
                completion_scores = [
                    model.score(prefix + suffix)
                    for suffix in product(*pools[prefix_size:])
                ]
                self.assertTrue(completion_scores)
                self.assertGreaterEqual(
                    bound + 1e-9, max(completion_scores)
                )

    def test_branch_bound_matches_exact_product_across_seeded_pools(self):
        seeds = (11, 23, 47, 89, 131)
        pool_sizes = (3, 5, 8)
        comparisons = 0
        expansion_ratios = []

        for seed in seeds:
            rng = random.Random(seed)
            for pool_size in pool_sizes:
                model = LearnableSROK(self.roles, feature_dim=2)
                model.weights = [
                    rng.uniform(-0.8, 0.8) for _ in model.weights
                ]
                nodes = [
                    Node(
                        f"{role}-{index}", role,
                        (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)),
                        frozenset({"eligible"}),
                    )
                    for role in ("r0", "r1", "r2")
                    for index in range(pool_size)
                ]
                exact = model.predict(
                    nodes, retrieval_mode="joint", search_strategy="product",
                    max_expansions=pool_size ** 3, result_limit=5,
                )
                bounded = model.predict(
                    nodes, retrieval_mode="joint", search_strategy="branch_bound",
                    max_expansions=10_000, result_limit=5,
                )
                self.assertEqual(bounded.abstained, exact.abstained)
                self.assertEqual(bounded.reason, exact.reason)
                self.assertEqual(
                    [item.role_bindings for item in bounded.candidates],
                    [item.role_bindings for item in exact.candidates],
                )
                self.assertEqual(bounded.role_pool_sizes, exact.role_pool_sizes)
                expansion_ratios.append(
                    bounded.expanded_search_states / exact.expanded_search_states
                )
                comparisons += 1

        print(
            "CPG_EI_BRANCH_BOUND_SWEEP "
            f"comparisons={comparisons} "
            f"mean_expansion_ratio={sum(expansion_ratios) / comparisons:.4f} "
            f"min_expansion_ratio={min(expansion_ratios):.4f} "
            f"max_expansion_ratio={max(expansion_ratios):.4f}"
        )
        self.assertEqual(comparisons, 15)

    def test_branch_bound_preserves_third_order_global_optimum(self):
        model = LearnableSROK(self.roles, feature_dim=1)
        model.weights[6] = 1.0
        nodes = []
        for role in ("r0", "r1", "r2"):
            nodes.extend(
                Node(
                    f"a-{role}-decoy-{index}", role, (0.0,),
                    frozenset({"eligible"}),
                )
                for index in range(2)
            )
            nodes.append(
                Node(f"z-{role}-signal", role, (1.0,), frozenset({"eligible"}))
            )

        exact = model.predict(
            nodes, retrieval_mode="joint", search_strategy="product",
            max_expansions=27, result_limit=1,
        )
        bounded = model.predict(
            nodes, retrieval_mode="joint", search_strategy="branch_bound",
            max_expansions=1_000, result_limit=1,
        )
        self.assertFalse(bounded.abstained)
        self.assertEqual(bounded.reason, exact.reason)
        self.assertEqual(
            [item.role_bindings for item in bounded.candidates],
            [item.role_bindings for item in exact.candidates],
        )
        self.assertEqual(
            bounded.candidates[0].role_bindings,
            (("r0", "z-r0-signal"), ("r1", "z-r1-signal"),
             ("r2", "z-r2-signal")),
        )

    def test_branch_bound_budget_exhaustion_fails_closed(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        nodes = [
            Node(
                f"{role}-{index}", role, (float(index), float(index % 2)),
                frozenset({"eligible"}),
            )
            for role in ("r0", "r1", "r2") for index in range(3)
        ]
        result = model.predict(
            nodes, retrieval_mode="joint", search_strategy="branch_bound",
            max_expansions=1, result_limit=3,
        )
        self.assertTrue(result.abstained)
        self.assertTrue(result.budget_exhausted)
        self.assertEqual(result.reason, "SEARCH_BUDGET_EXHAUSTED")
        self.assertEqual(result.expanded_search_states, 1)

    def test_branch_bound_keeps_ties_for_deterministic_abstention(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        nodes = [
            Node(
                f"{role}-{index}", role, (0.0, 0.0),
                frozenset({"eligible"}),
            )
            for role in ("r0", "r1", "r2") for index in range(2)
        ]
        exact = model.predict(
            nodes, retrieval_mode="joint", search_strategy="product",
            max_expansions=8, result_limit=1,
        )
        bounded = model.predict(
            list(reversed(nodes)), retrieval_mode="joint",
            search_strategy="branch_bound", max_expansions=100,
            result_limit=1,
        )
        self.assertTrue(bounded.abstained)
        self.assertEqual(bounded.reason, "LOW_SCORE_MARGIN")
        self.assertEqual(bounded.reason, exact.reason)
        self.assertEqual(
            [item.role_bindings for item in bounded.candidates],
            [item.role_bindings for item in exact.candidates],
        )

    def test_branch_bound_prunes_equal_score_branches_by_lexicographic_bound(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        nodes = [
            Node(
                f"{role}-{index:04d}", role, (0.0, 0.0),
                frozenset({"eligible"}),
            )
            for role in ("r0", "r1", "r2") for index in range(8)
        ]
        exact = model.predict(
            nodes, retrieval_mode="joint", search_strategy="product",
            max_expansions=8 ** 3, result_limit=5,
        )
        bounded = model.predict(
            nodes, retrieval_mode="joint", search_strategy="branch_bound",
            max_expansions=8 ** 3, result_limit=5,
        )
        self.assertTrue(exact.abstained)
        self.assertEqual(exact.reason, "LOW_SCORE_MARGIN")
        self.assertEqual(bounded.reason, exact.reason)
        self.assertEqual(
            [item.role_bindings for item in bounded.candidates],
            [item.role_bindings for item in exact.candidates],
        )
        self.assertLess(bounded.expanded_search_states, 8 ** 3)

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


    def test_seeded_feature_noise_search_robustness(self):
        # Separate two effects:
        # 1) exact-ranking stability under perturbed input features;
        # 2) beam retrieval quality relative to exact search on the same
        #    perturbed inputs. This does not treat exact as semantic ground truth.
        seeds = tuple(range(11, 36))
        pool_sizes = (3, 5, 8)
        noise_levels = (0.0, 0.1, 0.25, 0.5, 1.0)
        beam_widths = (2, 8, 32, 128, 512)
        comparisons = 0
        complete_searches = 0
        exact_top1_stability = {sigma: [] for sigma in noise_levels}
        beam_recalls = []
        beam_top1_hits = []
        beam_expansion_ratios = []
        beam_abstentions = 0
        complete_recalls = []
        complete_top1_hits = []

        for seed in seeds:
            weight_rng = random.Random(seed)
            for pool_size in pool_sizes:
                model = LearnableSROK(self.roles, feature_dim=2)
                model.weights = [
                    weight_rng.uniform(-0.8, 0.8) for _ in model.weights
                ]
                clean_nodes = []
                for role in ("r0", "r1", "r2"):
                    for index in range(pool_size):
                        features = (
                            weight_rng.gauss(0.0, 1.0),
                            weight_rng.gauss(0.0, 1.0),
                        )
                        clean_nodes.append(Node(
                            f"{role}-{index}", role, features,
                            frozenset({"eligible"}),
                        ))

                exact_clean = model.predict(
                    clean_nodes, retrieval_mode="joint",
                    search_strategy="product",
                    max_expansions=pool_size ** 3, result_limit=5,
                )
                self.assertTrue(exact_clean.candidates)
                clean_top1 = exact_clean.candidates[0].role_bindings

                for sigma in noise_levels:
                    noise_rng = random.Random(
                        seed * 1_000_003 + pool_size * 10_007
                        + int(sigma * 1_000)
                    )
                    noisy_nodes = [
                        Node(
                            node.node_id,
                            node.node_type,
                            tuple(
                                value + noise_rng.gauss(0.0, sigma)
                                for value in node.features
                            ),
                            node.tags,
                            node.evidence_ids,
                        )
                        for node in clean_nodes
                    ]
                    exact_noisy = model.predict(
                        noisy_nodes, retrieval_mode="joint",
                        search_strategy="product",
                        max_expansions=pool_size ** 3, result_limit=5,
                    )
                    self.assertTrue(exact_noisy.candidates)
                    exact_top_k = {
                        candidate.role_bindings
                        for candidate in exact_noisy.candidates
                    }
                    exact_top1 = exact_noisy.candidates[0].role_bindings
                    stability = int(exact_top1 == clean_top1)
                    exact_top1_stability[sigma].append(stability)

                    for beam_width in beam_widths:
                        beam = model.predict(
                            noisy_nodes, retrieval_mode="joint",
                            search_strategy="beam", beam_width=beam_width,
                            max_expansions=10_000, result_limit=5,
                        )
                        reversed_beam = model.predict(
                            list(reversed(noisy_nodes)), retrieval_mode="joint",
                            search_strategy="beam", beam_width=beam_width,
                            max_expansions=10_000, result_limit=5,
                        )
                        beam_top_k = {
                            candidate.role_bindings
                            for candidate in beam.candidates
                        }
                        recall = (
                            len(exact_top_k & beam_top_k) / len(exact_top_k)
                        )
                        top1 = int(
                            bool(beam.candidates)
                            and beam.candidates[0].role_bindings == exact_top1
                        )
                        self.assertGreaterEqual(recall, 0.0)
                        self.assertLessEqual(recall, 1.0)
                        self.assertEqual(beam.reason, reversed_beam.reason)
                        self.assertEqual(
                            beam.expanded_search_states,
                            reversed_beam.expanded_search_states,
                        )
                        self.assertEqual(
                            [item.role_bindings for item in beam.candidates],
                            [item.role_bindings for item in reversed_beam.candidates],
                        )
                        self.assertLessEqual(beam.expanded_search_states, 10_000)

                        if beam_width >= pool_size ** 3:
                            self.assertEqual(beam.abstained, exact_noisy.abstained)
                            self.assertEqual(beam.reason, exact_noisy.reason)
                            self.assertEqual(
                                [item.role_bindings for item in beam.candidates],
                                [item.role_bindings for item in exact_noisy.candidates],
                            )
                            self.assertEqual(recall, 1.0)
                            self.assertEqual(top1, 1)
                            complete_searches += 1
                            complete_recalls.append(recall)
                            complete_top1_hits.append(top1)

                        beam_recalls.append(recall)
                        beam_top1_hits.append(top1)
                        beam_expansion_ratios.append(
                            beam.expanded_search_states
                            / exact_noisy.expanded_search_states
                        )
                        beam_abstentions += int(beam.abstained)
                        comparisons += 1

        stability_summary = {
            str(sigma): sum(values) / len(values)
            for sigma, values in exact_top1_stability.items()
        }
        print(
            "CPG_EI_FEATURE_NOISE_SWEEP "
            f"comparisons={comparisons} "
            f"noise_levels={stability_summary} "
            f"beam_recall_at_5={sum(beam_recalls) / comparisons:.4f} "
            f"beam_top1_hit={sum(beam_top1_hits) / comparisons:.4f} "
            f"beam_expansion_ratio={sum(beam_expansion_ratios) / comparisons:.4f} "
            f"beam_abstention_rate={beam_abstentions / comparisons:.4f} "
            f"complete_search_rate={complete_searches / comparisons:.4f} "
            f"complete_recall_at_5={sum(complete_recalls) / len(complete_recalls):.4f} "
            f"complete_top1_hit={sum(complete_top1_hits) / len(complete_top1_hits):.4f}"
        )
        self.assertEqual(comparisons, 1875)
        self.assertEqual(complete_searches, 750)
        self.assertEqual(exact_top1_stability[0.0], [1] * 75)
        self.assertTrue(all(value == 1.0 for value in complete_recalls))
        self.assertTrue(all(value == 1 for value in complete_top1_hits))


if __name__ == "__main__":
    unittest.main()
