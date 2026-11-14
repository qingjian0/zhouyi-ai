import unittest

from prototype.yixiang_m64_instrumental_variable import (
    estimate_wald_iv, generate_iv_cases, infer_iv_instrument,
)


class M64InstrumentalVariableTests(unittest.TestCase):
    def setUp(self):
        self.cases = generate_iv_cases()

    def test_valid_instrument_identifies_complier_late_under_monotonicity(self):
        case = self.cases["valid_latent_confounding"]
        result = infer_iv_instrument(case)
        self.assertTrue(result["iv_identified"])
        self.assertEqual(result["candidate"], "Z")
        estimate = estimate_wald_iv(case)
        self.assertEqual(estimate["status"], "identified_late_under_declared_assumptions")
        self.assertEqual(estimate["estimand"], "LATE_for_compliers_not_population_ATE")
        self.assertAlmostEqual(estimate["estimate"], 0.4, places=10)

    def test_valid_iv_graph_does_not_claim_population_ate(self):
        case = self.cases["valid_latent_confounding"]
        result = estimate_wald_iv(case)
        self.assertNotEqual(result["estimand"], "population_ATE")

    def test_exclusion_violation_is_rejected(self):
        result = infer_iv_instrument(self.cases["exclusion_violation"])
        self.assertFalse(result["iv_identified"])
        self.assertFalse(result["candidates"][0]["exclusion_restriction_graphically_supported"])

    def test_instrument_confounding_is_rejected(self):
        result = infer_iv_instrument(self.cases["instrument_confounding"])
        self.assertFalse(result["iv_identified"])
        self.assertFalse(result["candidates"][0]["no_open_backdoor_path_to_outcome"])

    def test_weak_first_stage_is_not_called_valid(self):
        case = self.cases["weak_instrument"]
        result = infer_iv_instrument(case, min_abs_first_stage=0.01)
        self.assertFalse(result["iv_identified"])
        self.assertEqual(result["candidates"][0]["status"], "irrelevant_instrument")

    def test_missing_monotonicity_keeps_wald_ratio_labelled(self):
        case = dict(self.cases["valid_latent_confounding"])
        case["assumptions"] = {}
        result = estimate_wald_iv(case)
        self.assertEqual(result["status"], "wald_ratio_monotonicity_unasserted")
        self.assertEqual(result["estimand"], "Wald_ratio_not_automatically_LATE_or_ATE")

    def test_invalid_dag_is_rejected(self):
        case = dict(self.cases["valid_latent_confounding"])
        case["dag"] = {"nodes": ["Z", "X", "Y"], "edges": [["Z", "X"], ["X", "Y"], ["Y", "Z"]]}
        with self.assertRaises(ValueError):
            infer_iv_instrument(case)

