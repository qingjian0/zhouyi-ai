import json
import unittest

from prototype.n09_learnable_srok import Node, RelationClassificationExample, RoleSpec, LearnableSROKError
from prototype.n010_xiang_operator import LearnableXiangOperator, XiangConfig


class LearnableXiangOperatorTests(unittest.TestCase):
    def setUp(self):
        self.roles = tuple(RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
                           for name in ("r0", "r1", "r2"))

    def assignment(self, signs):
        return tuple(Node(f"{role}-{i}", role, (float(sign), float(i + 1)),
                          frozenset({"candidate"}))
                     for i, (role, sign) in enumerate(zip(("r0", "r1", "r2"), signs)))

    def test_score_probability_and_checkpoint_roundtrip(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(5, "learnable", 7))
        assignment = self.assignment((1, -1, -1))
        p = model.predict_probability(assignment)
        restored = LearnableXiangOperator.from_checkpoint_json(model.checkpoint_json())
        self.assertAlmostEqual(restored.predict_probability(assignment), p)
        self.assertEqual(restored.training_steps, 0)

    def test_fixed_basis_does_not_change_during_fit(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "fixed_random", 3))
        before = [row[:] for row in model.basis]
        rows = [RelationClassificationExample(self.assignment((a, b, c)), 1 if a*b*c == 1 else -1)
                for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
        model.fit(rows, epochs=3)
        self.assertEqual(model.basis, before)
        self.assertEqual(model.training_steps, 3)

    def test_learnable_basis_receives_updates(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "learnable", 11))
        before = [row[:] for row in model.basis]
        rows = [RelationClassificationExample(self.assignment((a, b, c)), 1 if a*b*c == 1 else -1)
                for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
        model.fit(rows, epochs=2)
        self.assertNotEqual(model.basis, before)

    def test_two_epoch_fit_matches_two_sequential_one_epoch_fits(self):
        rows = [RelationClassificationExample(self.assignment((a, b, c)),
                    1 if a*b*c == 1 else -1)
                for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
        together = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "learnable", 29))
        sequential = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "learnable", 29))
        together.fit(rows, epochs=2, learning_rate=0.05)
        sequential.fit(rows, epochs=1, learning_rate=0.05)
        sequential.fit(rows, epochs=1, learning_rate=0.05)
        self.assertEqual(together.basis, sequential.basis)
        self.assertEqual(together.bias, sequential.bias)
        self.assertEqual(together.readout, sequential.readout)
        self.assertEqual(together.training_steps, sequential.training_steps)

    @staticmethod
    def _binary_loss(model, rows):
        total = 0.0
        for row in rows:
            p = min(max(model.predict_probability(row.assignment), 1e-15), 1 - 1e-15)
            target = 1.0 if row.label == 1 else 0.0
            import math
            total -= target * math.log(p) + (1 - target) * math.log(1 - p)
        return total / len(rows)

    def test_analytic_readout_and_basis_gradients_match_finite_difference(self):
        import copy
        rows = [
            RelationClassificationExample(self.assignment((1, -1, 1)), 1),
            RelationClassificationExample(self.assignment((-1, 1, -1)), -1),
        ]
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(3, "learnable", 17))
        eps = 1e-5
        baseline = copy.deepcopy(model)
        baseline.readout = [0.07 * (i + 1) for i in range(len(baseline.readout))]
        model.readout = baseline.readout[:]
        numeric = {}
        for name, index in (("readout", 0), ("basis", (0, 0))):
            plus, minus = copy.deepcopy(baseline), copy.deepcopy(baseline)
            if name == "readout":
                plus.readout[index] += eps
                minus.readout[index] -= eps
            else:
                plus.basis[index[0]][index[1]] += eps
                minus.basis[index[0]][index[1]] -= eps
            numeric[name] = (self._binary_loss(plus, rows) -
                             self._binary_loss(minus, rows)) / (2 * eps)
        lr = 1e-6
        model.fit(rows, epochs=1, learning_rate=lr, l2=0.0)
        inferred_readout = (baseline.readout[0] - model.readout[0]) / lr
        inferred_basis = (baseline.basis[0][0] - model.basis[0][0]) / lr
        self.assertAlmostEqual(inferred_readout, numeric["readout"], delta=2e-5)
        self.assertAlmostEqual(inferred_basis, numeric["basis"], delta=2e-5)

    def test_initialization_and_training_are_seed_deterministic(self):
        rows = [RelationClassificationExample(self.assignment((a, b, c)),
                    1 if a*b*c == 1 else -1)
                for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
        left = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "learnable", 31))
        right = LearnableXiangOperator(self.roles, 2, XiangConfig(4, "learnable", 31))
        left.fit(rows, epochs=4, learning_rate=0.05)
        right.fit(rows, epochs=4, learning_rate=0.05)
        self.assertEqual(left.checkpoint_json(), right.checkpoint_json())

    def test_checkpoint_rejects_malformed_shapes_and_non_object(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(3))
        payload = json.loads(model.checkpoint_json())
        payload["basis"] = []
        canonical = {k: v for k, v in payload.items() if k != "sha256"}
        import hashlib
        payload["sha256"] = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        with self.assertRaises(LearnableSROKError):
            LearnableXiangOperator.from_checkpoint_json(json.dumps(payload))
        with self.assertRaises(LearnableSROKError):
            LearnableXiangOperator.from_checkpoint_json("[]")

    def test_rejects_tampered_checkpoint(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(3))
        payload = json.loads(model.checkpoint_json())
        payload["bias"][0] = 12
        with self.assertRaises(LearnableSROKError):
            LearnableXiangOperator.from_checkpoint_json(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
