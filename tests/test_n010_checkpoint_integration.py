"""Checkpoint integration regressions for the N0.10 relation learner."""
import json
import unittest

from prototype.n09_learnable_srok import (
    LearnableSROK, LearnableSROKError, Node, RelationClassificationExample, RoleSpec,
)


class N010CheckpointIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
            for name in ("r0", "r1", "r2")
        )
        self.nodes = tuple(
            Node(f"{role}-{index}", role, (float(index + 1), float(index == 0)),
                 frozenset({"eligible"}), (f"ev-{role}-{index}",))
            for role in ("r0", "r1", "r2") for index in range(2)
        )

    def test_checkpoint_round_trip_preserves_classifier_and_joint_prediction(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        examples = []
        for a in self.nodes[:2]:
            for b in self.nodes[2:4]:
                for c in self.nodes[4:6]:
                    label = 1 if (a.node_id.endswith("0") ^ b.node_id.endswith("0") ^ c.node_id.endswith("0")) else -1
                    examples.append(RelationClassificationExample((a, b, c), label))
        model.fit_relation_classifier(examples, epochs=12, learning_rate=0.08)
        query = (self.nodes[0], self.nodes[2], self.nodes[4])
        before_probability = model.predict_relation_probability(query)
        before_prediction = model.predict(
            self.nodes, retrieval_mode="joint", max_expansions=8, result_limit=4
        )
        raw = model.checkpoint_json()
        restored = LearnableSROK.from_checkpoint_json(raw)
        self.assertEqual(restored.roles, model.roles)
        self.assertEqual(restored.weights, model.weights)
        self.assertEqual(restored.training_steps, model.training_steps)
        self.assertEqual(restored.predict_relation_probability(query), before_probability)
        self.assertEqual(
            restored.predict(self.nodes, retrieval_mode="joint", max_expansions=8, result_limit=4),
            before_prediction,
        )
        self.assertEqual(restored.checkpoint_json(), raw)


    def test_joint_beam_search_uses_learned_unary_order_without_product_prefix_bias(self):
        roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
            for name in ("r0", "r1", "r2")
        )
        model = LearnableSROK(roles, feature_dim=1)
        model.weights = [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        pools = tuple(
            tuple(
                Node(f"{role}-{index}", role, (float(index),),
                     frozenset({"eligible"}), (f"e-{role}-{index}",))
                for index in range(4)
            )
            for role in ("r0", "r1", "r2")
        )
        nodes = tuple(node for pool in pools for node in pool)
        prediction = model.predict(
            nodes, retrieval_mode="joint", search_strategy="beam",
            beam_width=1, max_expansions=12, result_limit=1,
        )
        self.assertEqual(prediction.candidates[0].role_bindings, (
            ("r0", "r0-3"), ("r1", "r1-3"), ("r2", "r2-3")
        ))
        self.assertEqual(prediction.expanded_assignments, 12)
        self.assertFalse(prediction.budget_exhausted)
        self.assertTrue(prediction.abstained)
        self.assertEqual(prediction.reason, "BEAM_PRUNED")


    def test_joint_beam_search_reports_truncated_budget_without_partial_predictions(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        nodes = tuple(
            Node(f"{role}-{index}", role, (float(index), 1.0),
                 frozenset({"eligible"}))
            for role in ("r0", "r1", "r2") for index in range(4)
        )
        result = model.predict(
            nodes, retrieval_mode="joint", search_strategy="beam",
            beam_width=2, max_expansions=5, result_limit=3,
        )
        self.assertTrue(result.budget_exhausted)
        self.assertEqual(result.expanded_assignments, 5)
        self.assertEqual(result.candidates, ())
        self.assertTrue(result.abstained)

    def test_partial_score_matches_complete_score(self):
        assignment = (self.nodes[0], self.nodes[2], self.nodes[4])
        model = LearnableSROK(self.roles, feature_dim=2)
        model.weights = [float(index + 1) / 10 for index in range(len(model.weights))]
        self.assertAlmostEqual(
            model._partial_score(assignment), model.score(assignment), places=12
        )

    def test_checkpoint_rejects_tampering(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        envelope = json.loads(model.checkpoint_json())
        envelope["weights"][0] = 42.0
        with self.assertRaisesRegex(LearnableSROKError, "digest mismatch"):
            LearnableSROK.from_checkpoint_json(json.dumps(envelope))

    def test_checkpoint_rejects_unknown_fields(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        envelope = json.loads(model.checkpoint_json())
        envelope["unexpected"] = True
        with self.assertRaisesRegex(LearnableSROKError, "fields do not match"):
            LearnableSROK.from_checkpoint_json(json.dumps(envelope))

    def test_joint_search_budget_exhaustion_never_accepts_partial_ranking(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        prediction = model.predict(
            self.nodes,
            retrieval_mode="joint",
            max_expansions=1,
            result_limit=1,
        )
        self.assertTrue(prediction.abstained)
        self.assertEqual(prediction.reason, "SEARCH_BUDGET_EXHAUSTED")
        self.assertTrue(prediction.budget_exhausted)
        self.assertEqual(prediction.expanded_assignments, 1)
        self.assertEqual(len(prediction.candidates), 1)

    def test_joint_search_is_candidate_order_invariant_under_fixed_budget(self):
        model = LearnableSROK(self.roles, feature_dim=2)
        forward = model.predict(
            self.nodes, retrieval_mode="joint", max_expansions=5, result_limit=5
        )
        reverse = model.predict(
            tuple(reversed(self.nodes)),
            retrieval_mode="joint",
            max_expansions=5,
            result_limit=5,
        )
        self.assertEqual(forward, reverse)
        self.assertTrue(forward.abstained)
        self.assertEqual(forward.reason, "SEARCH_BUDGET_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
