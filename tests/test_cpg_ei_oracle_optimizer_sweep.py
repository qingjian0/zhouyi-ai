import math
import unittest

from prototype.cpg_ei_mvp import CpgEiTransitionModel, FEATURE_NAMES
from prototype.cpg_ei_oracle_optimizer_sweep import (
    REGULARIZERS,
    _mean_bce,
    run_optimizer_sweep,
)
from prototype.cpg_ei_selection_sweep import (
    RULE_FAMILIES,
    exact_support,
    make_examples,
    partition_states,
)


class TestOracleOptimizerSweep(unittest.TestCase):
    def test_small_sweep_reports_train_locked_and_full_domain_separately(self):
        report = run_optimizer_sweep(
            seeds=(11,), learning_rates=(0.1, 0.35), epochs=2
        )
        self.assertEqual(len(report["records"]), 3 * 2 * 2)
        self.assertEqual(len(report["summary"]), 4)
        self.assertEqual(report["train_examples"], 40)
        self.assertEqual(report["locked_test_examples"], 12)
        self.assertEqual(report["selection_metric"], "mean_final_train_bce_only")
        self.assertFalse(report["locked_and_full_metrics_used_for_selection"])
        self.assertIn("best_train_config", report)
        self.assertNotIn("best_locked_config", report)
        self.assertNotIn("best_full_64_state_config", report)
        for row in report["records"]:
            # Zero-initialized logits must produce exactly ln(2) before fitting.
            self.assertAlmostEqual(row["initial_train_bce"], math.log(2.0), places=12)
            self.assertEqual(row["support_source"], "oracle_known_support")
            self.assertEqual(row["gradient_data"], "train_40_only")
            for key in (
                "train_bit_accuracy", "locked_bit_accuracy",
                "full_64_state_bit_accuracy", "final_train_bce",
            ):
                self.assertTrue(math.isfinite(row[key]))

    def test_final_bce_is_recomputed_from_post_update_parameters(self):
        report = run_optimizer_sweep(
            seeds=(11,), learning_rates=(0.1,), epochs=2
        )
        train_states, _, _ = partition_states(11)
        family = next(iter(RULE_FAMILIES))
        triples = RULE_FAMILIES[family]
        train = make_examples(train_states, triples)
        support = {FEATURE_NAMES.index(name) for name in exact_support(triples)}
        model = CpgEiTransitionModel.create(active_relation_indices=support)
        model.train(
            train, epochs=2, learning_rate=0.1, **REGULARIZERS["default"]
        )
        expected = _mean_bce(model, train)
        matching = next(
            row for row in report["records"]
            if row["family"] == family and row["regularizer"] == "default"
            and row["learning_rate"] == 0.1
        )
        self.assertAlmostEqual(matching["final_train_bce"], expected, places=12)

    def test_mean_bce_uses_current_model_parameters(self):
        model = CpgEiTransitionModel.create(active_relation_indices=())
        rows = make_examples(((0, 0, 0, 0, 0, 0),), ())
        self.assertAlmostEqual(_mean_bce(model, rows), math.log(2.0), places=12)

    def test_rejects_invalid_schedules(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_optimizer_sweep(seeds=(), learning_rates=(0.1,), epochs=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            run_optimizer_sweep(seeds=(1,), learning_rates=(0.0,), epochs=1)
        with self.assertRaisesRegex(ValueError, "unique"):
            run_optimizer_sweep(seeds=(1,), learning_rates=(0.1, 0.1), epochs=1)


if __name__ == "__main__":
    unittest.main()
