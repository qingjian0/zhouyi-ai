import unittest
from prototype.yixiang_scm_families_m51 import (
    FamilyEnvironment, FamilySpec, FamilyNode, FamilyValidationError,
    binary_confounded_family, nonlinear_interaction_family,
    evaluate_family, run_family_suite,
)


class M51Tests(unittest.TestCase):
    def test_binary_family_recovers_direct_parents(self):
        result = evaluate_family(binary_confounded_family(), "y", ("a", "b", "c"), 2)
        self.assertEqual(set(result["selected"]), {"a", "b"})
        self.assertEqual(result["f1"], 1.0)

    def test_binary_confounder_has_zero_paired_causal_effect(self):
        result = evaluate_family(binary_confounded_family(), "y", ("a", "b", "c"), 2)
        self.assertAlmostEqual(result["effects"]["c"], 0.0, places=12)

    def test_nonlinear_interaction_recovers_both_causes(self):
        result = evaluate_family(nonlinear_interaction_family(), "y", ("x", "z", "w"), 2)
        self.assertEqual(set(result["selected"]), {"x", "z"})
        self.assertEqual(result["f1"], 1.0)

    def test_nonlinear_interaction_requires_joint_parent_context(self):
        env = FamilyEnvironment(nonlinear_interaction_family(population_size=8))
        units = tuple(range(8))
        baseline = env.sample(units, {"x": 0, "z": 0})
        joint = env.sample(units, {"x": 1, "z": 1})
        self.assertAlmostEqual(
            sum(dict(r.values)["y"] for r in joint) / 8 -
            sum(dict(r.values)["y"] for r in baseline) / 8, 2.0, places=10
        )

    def test_repeated_samples_are_persistent(self):
        env = FamilyEnvironment(binary_confounded_family(population_size=20))
        self.assertEqual(env.sample((0, 1)), env.sample((0, 1)))

    def test_same_seed_same_population(self):
        a = FamilyEnvironment(binary_confounded_family(seed=9, population_size=20))
        b = FamilyEnvironment(binary_confounded_family(seed=9, population_size=20))
        self.assertEqual(a.sample((0, 1)), b.sample((0, 1)))

    def test_different_seed_changes_exogenous_noise(self):
        a = FamilyEnvironment(binary_confounded_family(seed=9, population_size=20))
        b = FamilyEnvironment(binary_confounded_family(seed=10, population_size=20))
        self.assertNotEqual(a.sample((0, 1)), b.sample((0, 1)))

    def test_binary_intervention_requires_zero_or_one(self):
        env = FamilyEnvironment(binary_confounded_family(population_size=8))
        with self.assertRaisesRegex(FamilyValidationError, "binary_intervention_must_be_zero_or_one"):
            env.sample((0,), {"a": 0.5})

    def test_unknown_mechanism_rejected(self):
        spec = FamilySpec("bad", (FamilyNode("x", (), (), "mystery"),), 1, 4)
        with self.assertRaisesRegex(FamilyValidationError, "unsupported_mechanism"):
            FamilyEnvironment(spec)

    def test_cycle_rejected(self):
        spec = FamilySpec("cycle", (
            FamilyNode("x", ("y",), (1.0,)),
            FamilyNode("y", ("x",), (1.0,)),
        ), 1, 4)
        with self.assertRaisesRegex(FamilyValidationError, "cyclic_graph"):
            FamilyEnvironment(spec)

    def test_invalid_population_rejected(self):
        spec = FamilySpec("empty", (FamilyNode("x", (), ()),), 1, 0)
        with self.assertRaisesRegex(FamilyValidationError, "invalid_family_or_population"):
            FamilyEnvironment(spec)

    def test_oracle_is_explicitly_evaluator_only(self):
        env = FamilyEnvironment(binary_confounded_family(population_size=16))
        self.assertTrue(env.oracle("y")["ground_truth_available_to_evaluator_only"])

    def test_suite_reports_scope_limitations(self):
        result = run_family_suite()
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(any("not_a_general" in x for x in result["limitations"]))

    def test_suite_seed_reproducible(self):
        a = run_family_suite(seed=31, population_size=128)
        b = run_family_suite(seed=31, population_size=128)
        self.assertEqual(a["results"], b["results"])

    def test_binary_direct_parent_not_confounded_ancestor(self):
        env = FamilyEnvironment(binary_confounded_family())
        self.assertEqual(set(env.direct_parents("y")), {"a", "b"})
        self.assertEqual(set(env.ancestors("y")), {"a", "b", "q"})

    def test_intervention_effects_share_population(self):
        result = evaluate_family(binary_confounded_family(population_size=64),
                                 "y", ("a", "b", "c"), 2)
        self.assertEqual(len(result["paired_unit_ids"]), 64)

    def test_linear_gaussian_family_mechanism(self):
        spec = FamilySpec("linear", (
            FamilyNode("x", (), (), "linear_gaussian", noise_scale=0.0),
            FamilyNode("y", ("x",), (3.0,), "linear_gaussian", intercept=1.0, noise_scale=0.0),
        ), 1, 4)
        env = FamilyEnvironment(spec)
        self.assertEqual(dict(env.sample((0,), {"x": 2})[0].values)["y"], 7.0)

    def test_binary_noise_configuration_validated(self):
        spec = FamilySpec("bad-binary", (
            FamilyNode("x", (), (), "binary_logistic", noise_scale=1.0),
        ), 1, 4)
        with self.assertRaisesRegex(FamilyValidationError, "binary_logistic_noise_scale_must_be_zero"):
            FamilyEnvironment(spec)


if __name__ == "__main__":
    unittest.main()
