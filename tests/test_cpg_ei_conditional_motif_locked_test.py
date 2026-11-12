import unittest

from prototype.cpg_ei_conditional_motif_locked_test import (
    make_state_disjoint_splits,
    run_locked_test,
)


class TestConditionalMotifLockedTest(unittest.TestCase):
    def test_state_space_is_partitioned_without_overlap(self):
        train, dev, locked = make_state_disjoint_splits(11)
        train_states = {row.state for row in train}
        dev_states = {row.state for row in dev}
        locked_states = {row.state for row in locked}
        self.assertEqual((len(train_states), len(dev_states), len(locked_states)), (32, 16, 16))
        self.assertFalse(train_states & dev_states)
        self.assertFalse(train_states & locked_states)
        self.assertFalse(dev_states & locked_states)
        self.assertEqual(len(train_states | dev_states | locked_states), 64)

    def test_locked_split_is_used_only_after_dev_selection(self):
        report = run_locked_test(
            seeds=(11,),
            learning_rates=(0.35, 1.05),
            epoch_counts=(300,),
        )
        self.assertEqual(
            report["selection_policy"]["hyperparameter_selection"],
            "development states only",
        )
        self.assertEqual(
            report["selection_policy"]["locked_test_access"],
            "final evaluation only",
        )
        self.assertEqual(report["sample_counts"]["locked_test"], 16)
        self.assertEqual(len(report["development_sweep"]), 2)
        self.assertEqual(report["split_audit"][0]["train_dev_overlap"], 0)
        self.assertEqual(report["split_audit"][0]["train_locked_overlap"], 0)
        self.assertEqual(report["split_audit"][0]["dev_locked_overlap"], 0)
        row = report["locked_test_records"][0]
        self.assertTrue(row["finite_loss"])
        self.assertGreaterEqual(row["bit_accuracy"], 0.0)
        self.assertLessEqual(row["bit_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
