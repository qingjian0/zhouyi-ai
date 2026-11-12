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

    def test_rejects_tampered_checkpoint(self):
        model = LearnableXiangOperator(self.roles, 2, XiangConfig(3))
        payload = json.loads(model.checkpoint_json())
        payload["bias"][0] = 12
        with self.assertRaises(LearnableSROKError):
            LearnableXiangOperator.from_checkpoint_json(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
