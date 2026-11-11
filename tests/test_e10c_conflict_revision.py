import unittest

from prototype.e10c_conflict_revision import run


class E10CConflictRevisionTests(unittest.TestCase):
    def test_opposite_reveal_for_identical_input_empties_exact_version_space(self):
        result = run(seed=2802, instances_per_template=4)
        self.assertTrue(result["conflict_has_identical_relation_participants_context"])
        self.assertTrue(result["conflict_label_is_opposite"])
        self.assertTrue(result["checks"]["incremental_and_batch_both_empty"])
        self.assertTrue(result["checks"]["incremental_equals_batch"])
        self.assertTrue(result["checks"]["incremental_abstains_inconsistent"])
        self.assertTrue(result["checks"]["batch_abstains_inconsistent"])
        self.assertTrue(result["checks"]["frozen_retains_prior_structure"])

    def test_repeated_run_is_deterministic(self):
        self.assertEqual(
            run(seed=2803, instances_per_template=4),
            run(seed=2803, instances_per_template=4),
        )


if __name__ == "__main__":
    unittest.main()
