import unittest

from prototype.e09_context_discovery import run, run_sweep


class E09ContextDiscoveryTests(unittest.TestCase):
    def test_contextual_and_blind_arms_share_base_split(self):
        result = run(seed=41)
        audit = result["split_audit"]
        self.assertEqual(len(audit["train_base_assignments"]), 18)
        self.assertEqual(len(audit["test_base_assignments"]), 9)
        self.assertTrue(
            set(map(tuple, audit["train_base_assignments"])).isdisjoint(
                set(map(tuple, audit["test_base_assignments"]))
            )
        )

    def test_contextual_learner_receives_environment_variable(self):
        result = run(seed=41)
        self.assertEqual(result["contextual"]["learner_snapshot"]["report"]["gradient_updates"], 0)
        clauses = result["contextual"]["learner_snapshot"]["clauses"]
        self.assertTrue(any(clause["pattern"][3] is not None for clause in clauses))

    def test_context_blind_ledger_quarantines_environment_conflicts(self):
        result = run(seed=41)
        audit = result["split_audit"]
        self.assertGreater(audit["context_blind_contested_inputs"], 0)
        self.assertLess(
            audit["context_blind_unique_train_rows"],
            audit["contextual_train_rows"],
        )

    def test_contextual_model_can_represent_different_environment_rules(self):
        result = run(seed=41)
        contextual = result["contextual"]["metrics_by_environment"]
        self.assertGreater(contextual["0"]["coverage"], 0.0)
        self.assertGreater(contextual["1"]["coverage"], 0.0)

    def test_sweep_is_reproducible_and_reports_each_environment(self):
        first = run_sweep(seeds=2, start_seed=51)
        second = run_sweep(seeds=2, start_seed=51)
        self.assertEqual(first, second)
        self.assertIn("0", first["summary"]["contextual"])
        self.assertIn("1", first["summary"]["context_blind"])


if __name__ == "__main__":
    unittest.main()
