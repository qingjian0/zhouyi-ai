import unittest

from prototype.yixiang_m64_instrumental_variable import generate_iv_cases
from prototype.yixiang_m65_invalid_iv_sensitivity import (
    bounded_exclusion_effect_set, infer_iv_exogeneity_and_relevance,
)


class M65InvalidIVSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.cases = generate_iv_cases()

    def test_bounded_exclusion_relaxes_exclusion_but_keeps_exogeneity(self):
        case = self.cases["exclusion_violation"]
        gate = infer_iv_exogeneity_and_relevance(case)
        self.assertTrue(gate["valid"])
        result = bounded_exclusion_effect_set(case, direct_effect_bound=0.0)
        self.assertEqual(result["status"], "bounded_effect_set_under_linear_moment_assumptions")
        self.assertAlmostEqual(result["identified_set"][0], result["identified_set"][1], places=10)

    def test_larger_direct_effect_bound_widens_effect_set(self):
        case = self.cases["exclusion_violation"]
        narrow = bounded_exclusion_effect_set(case, direct_effect_bound=0.05)
        wide = bounded_exclusion_effect_set(case, direct_effect_bound=0.20)
        self.assertTrue(wide["identified_set"][0] <= narrow["identified_set"][0])
        self.assertTrue(wide["identified_set"][1] >= narrow["identified_set"][1])
        self.assertGreater(
            wide["identified_set"][1] - wide["identified_set"][0],
            narrow["identified_set"][1] - narrow["identified_set"][0],
        )

    def test_instrument_confounding_blocks_sensitivity_claim(self):
        result = bounded_exclusion_effect_set(
            self.cases["instrument_confounding"], direct_effect_bound=0.2
        )
        self.assertEqual(result["status"], "not_identified_by_exogeneity_relevance_gate")
        self.assertIsNone(result["identified_set"])

    def test_negative_or_nonfinite_bound_is_rejected(self):
        case = self.cases["exclusion_violation"]
        for value in (-0.1, float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    bounded_exclusion_effect_set(case, direct_effect_bound=value)

