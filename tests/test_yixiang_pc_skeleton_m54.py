import random
import unittest
from types import MappingProxyType

from prototype.yixiang_fair_baselines_m54 import AgentContext
from prototype.yixiang_pc_skeleton_m54 import (
    _partial_correlation_pvalue, pc_skeleton_baseline,
)


def context(rows, candidates=("x", "z"), target="y"):
    frozen = tuple(MappingProxyType(dict(row)) for row in rows)
    return AgentContext(frozen, candidates, target, 1000, 0, 0.0, False)


class PCStyleSkeletonTests(unittest.TestCase):
    def test_keeps_direct_linear_parent_and_prunes_independent_variable(self):
        rng = random.Random(812)
        rows = []
        for i in range(500):
            x = rng.gauss(0, 1)
            z = rng.gauss(0, 1)
            noise = rng.gauss(0, 0.25)
            rows.append({"x": x, "z": z, "y": 2.5 * x + noise})
        proposal = pc_skeleton_baseline(context(rows), alpha=0.01, max_conditioning_size=1)
        self.assertEqual(proposal.predicted_parents, ("x",))

    def test_conditional_independence_prunes_spurious_association(self):
        rng = random.Random(917)
        rows = []
        for _ in range(700):
            common = rng.gauss(0, 1)
            x = common + rng.gauss(0, 0.35)
            y = 2.0 * common + rng.gauss(0, 0.35)
            z = common
            rows.append({"x": x, "z": z, "y": y})
        p_marginal = _partial_correlation_pvalue(
            [r["x"] for r in rows], [r["y"] for r in rows], [])
        p_conditional = _partial_correlation_pvalue(
            [r["x"] for r in rows], [r["y"] for r in rows],
            [[r["z"] for r in rows]])
        self.assertLess(p_marginal, 0.001)
        self.assertGreater(p_conditional, 0.01)

    def test_insufficient_degrees_of_freedom_fails_conservatively(self):
        self.assertEqual(_partial_correlation_pvalue([1, 2, 3, 4],
                         [2, 4, 6, 8], [[0, 1, 0, 1]]), 0.0)

    def test_rejects_invalid_alpha_and_depth(self):
        rows = [{"x": float(i), "z": float(i % 2), "y": float(2 * i)}
                for i in range(20)]
        with self.assertRaisesRegex(ValueError, "alpha_must_be_between_zero_and_one"):
            pc_skeleton_baseline(context(rows), alpha=1.0)
        with self.assertRaisesRegex(ValueError, "invalid_max_conditioning_size"):
            pc_skeleton_baseline(context(rows), max_conditioning_size=True)

    def test_rejects_non_numeric_or_non_finite_data(self):
        with self.assertRaisesRegex(ValueError, "invalid_numeric_training_data"):
            pc_skeleton_baseline(context([{"x": "bad", "z": 0, "y": 1}] * 5))

    def test_deterministic_output(self):
        rng = random.Random(19)
        rows = [{"x": rng.gauss(0, 1), "z": rng.gauss(0, 1)}
                for _ in range(120)]
        rows = [{"x": row["x"], "z": row["z"],
                 "y": 1.8 * row["x"] + rng.gauss(0, 0.2)} for row in rows]
        ctx = context(rows)
        self.assertEqual(pc_skeleton_baseline(ctx), pc_skeleton_baseline(ctx))


if __name__ == "__main__":
    unittest.main()
