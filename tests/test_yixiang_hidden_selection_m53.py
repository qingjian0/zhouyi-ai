import unittest

from prototype.yixiang_hidden_selection_m53 import (
    audit_m53_dataset, collider_selection_dataset, hidden_confounding_dataset,
    mechanism_drift_dataset, measurement_error_dataset, paired_intervention_effect,
    selected_correlation,
)


def slope(rows):
    xs = [row.x_observed for row in rows]
    ys = [row.y_observed for row in rows]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator


class M53Tests(unittest.TestCase):
    def test_hidden_confounder_is_not_agent_visible(self):
        dataset = hidden_confounding_dataset(population_size=200)
        self.assertTrue(audit_m53_dataset(dataset)[0])
        self.assertFalse(hasattr(dataset.agent_rows[0], "latent_u"))
        self.assertFalse(hasattr(dataset.agent_rows[0], "x_true"))
        self.assertTrue(dataset.evaluator_truth.hidden_confounder_present)

    def test_hidden_confounding_biases_observational_slope(self):
        dataset = hidden_confounding_dataset(seed=17, population_size=5000)
        self.assertGreater(slope(dataset.agent_rows), 1.5)

    def test_paired_intervention_recovers_structural_effect(self):
        estimate = paired_intervention_effect(
            seed=3, population_size=100, treatment_effect=2.25
        )
        self.assertAlmostEqual(estimate, 2.25, places=12)

    def test_collider_selection_creates_spurious_association(self):
        dataset = collider_selection_dataset(
            seed=23, population_size=10000, selection_threshold=1.0,
            treatment_effect=0.0,
        )
        self.assertAlmostEqual(
            dataset.evaluator_truth.causal_effect_by_environment[0][1], 0.0
        )
        self.assertLess(selected_correlation(dataset), 0.0)

    def test_measurement_error_is_recorded_in_evaluator_truth(self):
        dataset = measurement_error_dataset(
            seed=31, population_size=200, treatment_effect=1.5,
            measurement_error_sd=0.8,
        )
        self.assertEqual(dataset.evaluator_truth.measurement_error_sd, 0.8)
        self.assertTrue(audit_m53_dataset(dataset)[0])

    def test_measurement_error_reduces_observed_regression_slope(self):
        clean = measurement_error_dataset(
            seed=31, population_size=5000, measurement_error_sd=0.0
        )
        noisy = measurement_error_dataset(
            seed=31, population_size=5000, measurement_error_sd=2.0
        )
        self.assertLess(slope(noisy.agent_rows), slope(clean.agent_rows))

    def test_mechanism_drift_has_environment_specific_truth(self):
        dataset = mechanism_drift_dataset(
            seed=43, population_size=900, effects=(1.0, 2.0, -0.5)
        )
        self.assertEqual(
            dataset.evaluator_truth.causal_effect_by_environment,
            (("env_0", 1.0), ("env_1", 2.0), ("env_2", -0.5)),
        )
        self.assertEqual({row.environment for row in dataset.agent_rows},
                         {"env_0", "env_1", "env_2"})

    def test_reproducible_generation(self):
        a = hidden_confounding_dataset(seed=71, population_size=100)
        b = hidden_confounding_dataset(seed=71, population_size=100)
        self.assertEqual(a, b)

    def test_invalid_population_rejected(self):
        with self.assertRaisesRegex(ValueError, "population_size"):
            hidden_confounding_dataset(population_size=10)

    def test_invalid_measurement_error_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_generator_parameter"):
            measurement_error_dataset(measurement_error_sd=-1.0)

    def test_agent_rows_are_immutable(self):
        dataset = hidden_confounding_dataset(population_size=20)
        with self.assertRaises(Exception):
            dataset.agent_rows[0].x_observed = 9.0

    def test_selected_correlation_is_not_causal_effect_api(self):
        dataset = collider_selection_dataset(population_size=100)
        self.assertIsInstance(selected_correlation(dataset), float)
        self.assertNotIn("causal_effect", selected_correlation.__name__)


if __name__ == "__main__":
    unittest.main()
