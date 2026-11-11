import unittest
from dataclasses import replace

from prototype.e12a19_unified_structure_competition import Budget, Example, SplitManifest
from prototype.e12a19c_multi_rule_controls import JointBudget, run_joint
from tests.test_e12a19_unified_structure_competition import make_example


def fixture():
    train = tuple(make_example("train", i, "yes" if i % 2 == 0 else "no") for i in range(24))
    valid = tuple(make_example("validation", i, "yes" if i % 2 == 0 else "no") for i in range(8))
    manifest = SplitManifest(tuple(sorted(x.observation_id for x in train)),
                             tuple(sorted(x.observation_id for x in valid)),
                             tuple(f"locked-{i:02d}" for i in range(4)), ("no", "yes"))
    return train, valid, manifest


class MultiRuleControlTests(unittest.TestCase):
    def test_joint_model_is_deterministic(self):
        train, valid, manifest = fixture()
        cfg = JointBudget(max_candidates=100, max_rules=5, gradient_steps=80)
        a = run_joint(train, valid, manifest, budget=cfg)
        b = run_joint(tuple(reversed(train)), tuple(reversed(valid)), manifest, budget=cfg)
        self.assertEqual(a, b)

    def test_validation_label_mutation_does_not_change_fitted_parameters(self):
        train, valid, manifest = fixture()
        cfg = JointBudget(max_candidates=100, max_rules=5, gradient_steps=80)
        a = run_joint(train, valid, manifest, budget=cfg)
        mutated = tuple(replace(row, outcome="no" if row.outcome == "yes" else "yes") for row in valid)
        b = run_joint(train, mutated, manifest, budget=cfg)
        self.assertEqual(a.fitted_weights, b.fitted_weights)
        self.assertEqual(a.train_only_fit_digest, b.train_only_fit_digest)

    def test_multi_rule_model_and_null_control_are_reported(self):
        train, valid, manifest = fixture()
        result = run_joint(train, valid, manifest,
                           structure_budget=Budget(max_candidates_per_family=300),
                           budget=JointBudget(max_candidates=100, max_rules=6, gradient_steps=80))
        self.assertGreaterEqual(result.candidate_count, len(result.selected_rule_keys))
        self.assertGreaterEqual(len(result.selected_rule_keys), 1)
        self.assertTrue(0 <= result.joint_model.accuracy <= 1)
        self.assertTrue(0 <= result.randomized_control.accuracy <= 1)
        self.assertEqual(len(result.fitted_weights), 2)

    def test_candidate_and_rule_budgets_are_hard(self):
        train, valid, manifest = fixture()
        result = run_joint(train, valid, manifest,
                           budget=JointBudget(max_candidates=3, max_rules=2, gradient_steps=20))
        self.assertLessEqual(result.candidate_count, 3)
        self.assertLessEqual(len(result.selected_rule_keys), 2)

    def test_rejects_duplicate_or_locked_ids(self):
        train, valid, manifest = fixture()
        with self.assertRaises(ValueError):
            run_joint(train + (train[0],), valid, manifest)
        locked = replace(manifest, locked_test_ids=tuple(sorted(manifest.locked_test_ids + (train[0].observation_id,))))
        with self.assertRaises(ValueError):
            run_joint(train, valid, locked)


if __name__ == "__main__":
    unittest.main()
