import unittest

from prototype.e09_context_transfer import run, run_sweep


class E09ContextTransferTests(unittest.TestCase):
    def test_novel_context_is_absent_from_initial_training(self):
        result = run(seed=83, support_size=6)
        audit = result["split_audit"]
        self.assertEqual(audit["initial_train_contexts"], [0, 1])
        self.assertEqual(audit["novel_context"], 2)
        self.assertEqual(audit["initial_train_rows"], 36)
        self.assertEqual(audit["adaptation_rows"], 6)

    def test_train_support_and_test_assignments_do_not_overlap(self):
        audit = run(seed=83)["split_audit"]
        self.assertTrue(audit["train_test_disjoint"])
        self.assertTrue(audit["support_test_disjoint"])
        self.assertEqual(len(audit["train_base_assignments"]), 18)
        self.assertEqual(len(audit["test_base_assignments"]), 9)

    def test_adapted_model_contains_novel_context_condition(self):
        result = run(seed=83)
        clauses = result["adapted_model"]["clauses"]
        self.assertTrue(any(clause["pattern"][3] == 2 for clause in clauses))
        self.assertEqual(result["adapted_model"]["report"]["gradient_updates"], 0)

    def test_all_phases_report_each_context_and_abstention(self):
        result = run(seed=83)
        for phase in ("zero_shot", "after_adaptation"):
            self.assertEqual(set(result[phase]), {"0", "1", "2"})
            for item in result[phase].values():
                self.assertIn("coverage", item)
                self.assertIn("abstentions", item)

    def test_sweep_is_reproducible_and_tracks_old_context_retention(self):
        first = run_sweep(seeds=2, start_seed=91, support_size=6)
        second = run_sweep(seeds=2, start_seed=91, support_size=6)
        self.assertEqual(first, second)
        self.assertIn("0", first["summary"]["after_adaptation"])
        self.assertIn("1", first["summary"]["after_adaptation"])
        self.assertIn("2", first["summary"]["after_adaptation"])


if __name__ == "__main__":
    unittest.main()
