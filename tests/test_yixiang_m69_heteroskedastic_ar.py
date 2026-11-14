import unittest

from prototype.yixiang_m69_heteroskedastic_ar import heteroskedastic_ar_test


def heteroskedastic_data():
    n = 80
    z1 = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    z2 = [1.0 if (i // 2) % 2 == 0 else -1.0 for i in range(n)]
    x = [1.2 * z1[i] + 0.7 * z2[i] + 0.15 * (i % 3) for i in range(n)]
    errors = [0.04 * (i + 1) * (1.0 if i % 3 else -1.0) for i in range(n)]
    y = [1.75 * x[i] + errors[i] for i in range(n)]
    return {"x": x, "y": y, "z": [[z1[i], z2[i]] for i in range(n)]}


def no_first_stage_data():
    n = 80
    z1 = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    z2 = [1.0 if (i // 2) % 2 == 0 else -1.0 for i in range(n)]
    x = [1.0 if (i // 4) % 2 == 0 else -1.0 for i in range(n)]
    errors = [0.03 * (i + 1) * (1.0 if i % 3 else -1.0) for i in range(n)]
    y = [2.0 * x[i] + errors[i] for i in range(n)]
    return {"x": x, "y": y, "z": [[z1[i], z2[i]] for i in range(n)]}


class M69HeteroskedasticARTests(unittest.TestCase):
    def test_returns_hc0_asymptotic_test_and_explicit_scope(self):
        result = heteroskedastic_ar_test(heteroskedastic_data(), 1.75)
        self.assertEqual(result["covariance_estimator"], "HC0")
        self.assertEqual(result["reference_distribution"], "asymptotic_chi_square")
        self.assertFalse(result["finite_sample_exact"])
        self.assertTrue(result["weak_instrument_robust"])
        self.assertEqual(result["degrees_of_freedom"], 2)

    def test_does_not_require_strong_first_stage(self):
        result = heteroskedastic_ar_test(no_first_stage_data(), 2.0)
        self.assertTrue(result["weak_instrument_robust"])
        self.assertGreaterEqual(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)

    def test_rejects_rank_deficient_instruments(self):
        data = heteroskedastic_data()
        data["z"] = [[row[0], row[0]] for row in data["z"]]
        with self.assertRaisesRegex(ValueError, "rank_deficient_instruments"):
            heteroskedastic_ar_test(data, 1.75)

    def test_rejects_invalid_alpha_and_nonfinite_null(self):
        data = heteroskedastic_data()
        with self.assertRaises(ValueError):
            heteroskedastic_ar_test(data, 1.75, alpha=0.0)
        with self.assertRaises(ValueError):
            heteroskedastic_ar_test(data, float("nan"))

    def test_supports_covariate_adjustment(self):
        data = heteroskedastic_data()
        data["controls"] = [[float(i % 5)] for i in range(80)]
        result = heteroskedastic_ar_test(data, 1.75)
        self.assertEqual(result["degrees_of_freedom"], 2)
        self.assertEqual(result["covariance_estimator"], "HC0")


if __name__ == "__main__":
    unittest.main()
