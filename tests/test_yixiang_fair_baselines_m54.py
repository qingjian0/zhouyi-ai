import unittest

from prototype.yixiang_fair_baselines_m54 import (
    AgentContext, BaselineProposal, EvaluatorTruth, correlation_screen_baseline,
    evaluator_only_oracle, random_baseline, run_fair_comparison,
)


def rows():
    return tuple({"unit_id": i, "x": float(i), "z": float((-1) ** i),
                  "y": float(2 * i)} for i in range(12))


class M54FairBaselineTests(unittest.TestCase):
    def test_baselines_share_identical_train_only_context(self):
        seen = []
        def adapter(ctx):
            seen.append(ctx)
            self.assertEqual(tuple(r["unit_id"] for r in ctx.rows), (0, 1, 2, 3, 4, 5))
            return BaselineProposal(("x",), samples_used=2, total_cost=1.0)
        result = run_fair_comparison(
            rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
            test_ids=range(9, 12), candidate_variables=("x", "z"), target="y",
            evaluator_truth=EvaluatorTruth(("x",)),
            baselines=(("a", adapter), ("b", adapter)),
            max_samples=5, max_cost=4.0,
        )
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(result.results[0].f1, 1.0)
        self.assertEqual(result.results[1].budget_violation, False)

    def test_test_and_validation_rows_are_not_agent_visible(self):
        def adapter(ctx):
            self.assertNotIn(10, [r["unit_id"] for r in ctx.rows])
            self.assertNotIn(7, [r["unit_id"] for r in ctx.rows])
            return BaselineProposal(("x",))
        run_fair_comparison(
            rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
            test_ids=range(9, 12), candidate_variables=("x", "z"), target="y",
            evaluator_truth=EvaluatorTruth(("x",)), baselines=(("hidden", adapter),),
        )

    def test_overlap_and_partition_mismatch_fail_closed(self):
        args = dict(rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
                    test_ids=range(8, 12), candidate_variables=("x", "z"),
                    target="y", evaluator_truth=EvaluatorTruth(("x",)),
                    baselines=(("random", random_baseline),))
        with self.assertRaisesRegex(ValueError, "split_overlap"):
            run_fair_comparison(**args)
        args["test_ids"] = range(9, 12)
        args["train_ids"] = range(5)
        with self.assertRaisesRegex(ValueError, "split_partition_mismatch"):
            run_fair_comparison(**args)

    def test_budget_and_permission_violations_are_reported(self):
        def over_budget(ctx):
            return BaselineProposal(("x",), ("x",), samples_used=99, total_cost=99)
        result = run_fair_comparison(
            rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
            test_ids=range(9, 12), candidate_variables=("x", "z"), target="y",
            evaluator_truth=EvaluatorTruth(("x",)), baselines=(("bad", over_budget),),
            max_samples=2, max_interventions=0, max_cost=1,
            interventions_allowed=False,
        )
        self.assertTrue(result.results[0].budget_violation)
        self.assertTrue(result.results[0].invalid_proposal)

    def test_built_in_baselines_are_deterministic_and_oracle_is_separate(self):
        context = AgentContext(tuple(rows()[:6]), ("x", "z"), "y", 10, 0, 1.0, False)
        self.assertEqual(random_baseline(context, seed=7), random_baseline(context, seed=7))
        self.assertEqual(correlation_screen_baseline(context).predicted_parents, ("x",))
        self.assertEqual(evaluator_only_oracle(EvaluatorTruth(("x",))), ("x",))

    def test_truth_cannot_name_unknown_parent(self):
        with self.assertRaisesRegex(ValueError, "truth_parent_outside_candidate_universe"):
            run_fair_comparison(
                rows=rows(), train_ids=range(6), validation_ids=range(6, 9),
                test_ids=range(9, 12), candidate_variables=("x", "z"), target="y",
                evaluator_truth=EvaluatorTruth(("hidden",)),
                baselines=(("random", random_baseline),),
            )


if __name__ == "__main__":
    unittest.main()
