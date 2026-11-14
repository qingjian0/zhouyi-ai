import unittest

from prototype.yixiang_fair_baselines_m54 import (
    AgentContext, BaselineProposal, EvaluatorTruth, correlation_screen_baseline,
    evaluator_only_oracle, random_baseline, run_fair_comparison,
)


def rows():
    return tuple({"unit_id": i, "x": float(i), "z": float((-1) ** i),
                  "y": float(2 * i)} for i in range(12))


class M54FairBaselineTests(unittest.TestCase):
    def call(self, baselines, **overrides):
        args = dict(rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
                    test_ids=range(9, 12), candidate_variables=("x", "z"), target="y",
                    evaluator_truth=EvaluatorTruth(("x",)), baselines=baselines)
        args.update(overrides)
        return run_fair_comparison(**args)

    def test_baselines_share_identical_train_only_context(self):
        seen = []
        def adapter(ctx):
            seen.append(ctx)
            self.assertEqual(tuple(r["unit_id"] for r in ctx.rows), (0, 1, 2, 3, 4, 5))
            return BaselineProposal(("x",), samples_used=2, total_cost=1.0)
        result = self.call((("a", adapter), ("b", adapter)), max_samples=5, max_cost=4.0)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(result.results[0].f1, 1.0)
        self.assertFalse(result.results[1].budget_violation)

    def test_held_out_rows_are_not_agent_visible(self):
        def adapter(ctx):
            ids = [r["unit_id"] for r in ctx.rows]
            self.assertNotIn(10, ids)
            self.assertNotIn(7, ids)
            return BaselineProposal(("x",))
        self.call((("hidden", adapter),))

    def test_rows_are_immutable(self):
        def adapter(ctx):
            with self.assertRaises(TypeError):
                ctx.rows[0]["x"] = 999
            return BaselineProposal(("x",))
        self.call((("immutable", adapter),))

    def test_overlap_and_partition_mismatch_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "split_overlap"):
            self.call((("random", random_baseline),), test_ids=range(8, 12))
        with self.assertRaisesRegex(ValueError, "split_partition_mismatch"):
            self.call((("random", random_baseline),), train_ids=range(5))

    def test_budget_and_permission_violations_are_reported(self):
        def over_budget(ctx):
            return BaselineProposal(("x",), ("x",), samples_used=99, total_cost=99)
        result = self.call((("bad", over_budget),), max_samples=2,
                           max_interventions=0, max_cost=1, interventions_allowed=False)
        self.assertTrue(result.results[0].budget_violation)
        self.assertTrue(result.results[0].invalid_proposal)

    def test_premature_commit_is_scored(self):
        result = self.call((("premature", lambda ctx: BaselineProposal(
            ("x",), committed=True, evidence_sufficient=False)),))
        self.assertTrue(result.results[0].premature_commit)

    def test_built_in_baselines_and_oracle(self):
        context = AgentContext(tuple(rows()[:6]), ("x", "z"), "y", 10, 0, 1.0, False)
        self.assertEqual(random_baseline(context, seed=7), random_baseline(context, seed=7))
        self.assertEqual(correlation_screen_baseline(context).predicted_parents, ("x",))
        self.assertEqual(evaluator_only_oracle(EvaluatorTruth(("x",))), ("x",))

    def test_truth_outside_candidate_universe_rejected(self):
        with self.assertRaisesRegex(ValueError, "truth_parent_outside_candidate_universe"):
            self.call((("random", random_baseline),), evaluator_truth=EvaluatorTruth(("hidden",)))

    def test_duplicate_baseline_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_or_duplicate_baseline_adapter"):
            self.call((("same", random_baseline), ("same", random_baseline)))

    def test_invalid_budgets_rejected(self):
        for kwargs in ({"max_samples": True}, {"max_interventions": -1}, {"max_cost": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, "invalid_budget"):
                self.call((("random", random_baseline),), **kwargs)

    def test_missing_training_features_fail_closed(self):
        incomplete = list(rows())
        incomplete[0] = {"unit_id": 0, "x": 0.0, "y": 0.0}
        with self.assertRaisesRegex(ValueError, "training_row_missing_candidate_or_target"):
            self.call((("random", random_baseline),), rows=incomplete)

    def test_truth_container_must_be_immutable_tuple(self):
        with self.assertRaisesRegex(ValueError, "truth_parents_must_be_tuple"):
            self.call((("random", random_baseline),), evaluator_truth=EvaluatorTruth(["x"]))


if __name__ == "__main__":
    unittest.main()
