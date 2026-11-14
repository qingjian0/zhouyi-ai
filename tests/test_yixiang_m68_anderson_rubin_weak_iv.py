import unittest

from prototype.yixiang_m68_anderson_rubin_weak_iv import (
    anderson_rubin_confidence_set,
    anderson_rubin_test,
)


def strong_iv_data():
    n = 32
    z1 = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    z2 = [1.0 if (i // 2) % 2 == 0 else -1.0 for i in range(n)]
    noise = [0.25 if (i // 4) % 2 == 0 else -0.25 for i in range(n)]
    x = [1.5 * z1[i] + 0.8 * z2[i] + 0.3 * noise[i] for i in range(n)]
    y = [2.0 * x[i] + noise[i] for i in range(n)]
    return {"x": x, "y": y, "z": [[z1[i], z2[i]] for i in range(n)]}


def no_first_stage_data():
    n = 32
    z1 = [1.0 if i % 2 == 0 else -1.0 for i in range(n)]
    z2 = [1.0 if (i // 2) % 2 == 0 else -1.0 for i in range(n)]
    x = [1.0 if (i // 4) % 2 == 0 else -1.0 for i in range(n)]
    noise = [0.25 if (i // 8) % 2 == 0 else -0.25 for i in range(n)]
    y = [2.0 * x[i] + noise[i] for i in range(n)]
    return {"x": x, "y": y, "z": [[z1[i], z2[i]] for i in range(n)]}


class M68AndersonRubinTests(unittest.TestCase):
    def test_ar_test_does_not_require_a_strong_first_stage(self):
        result = anderson_rubin_test(no_first_stage_data(), 2.0)
        self.assertFalse(result["reject"])
        self.assertAlmostEqual(result["p_value"], 1.0, places=8)
        self.assertTrue(result["weak_instrument_robust"])

    def test_weak_first_stage_can_produce_all_real_confidence_set(self):
        result = anderson_rubin_confidence_set(no_first_stage_data())
        self.assertEqual(result["set_shape"], "all_real")
        self.assertEqual(result["components"], [{"lower": None, "upper": None}])

    def test_strong_iv_set_is_bounded_and_contains_true_coefficient(self):
        result = anderson_rubin_confidence_set(strong_iv_data())
        self.assertEqual(result["set_shape"], "bounded_interval")
        interval = result["components"][0]
        self.assertLess(interval["lower"], 2.0)
        self.assertGreater(interval["upper"], 2.0)

    def test_ar_test_reports_finite_sample_degrees_of_freedom(self):
        result = anderson_rubin_test(strong_iv_data(), 2.0)
        self.assertEqual(result["degrees_of_freedom"], [2, 29])
        self.assertGreaterEqual(result["ar_f_statistic"], 0.0)
        self.assertGreaterEqual(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)
        self.assertGreater(result["critical_value"], 3.3)
        self.assertLess(result["critical_value"], 3.4)

    def test_strong_instrument_rejects_far_away_null(self):
        result = anderson_rubin_test(strong_iv_data(), 0.0)
        self.assertTrue(result["reject"])
        self.assertLess(result["p_value"], 0.05)

    def test_instrument_rank_deficiency_is_rejected(self):
        data = strong_iv_data()
        data["z"] = [[row[0], row[0]] for row in data["z"]]
        with self.assertRaisesRegex(ValueError, "rank_deficient_instruments"):
            anderson_rubin_test(data, 2.0)

    def test_invalid_sample_and_alpha_are_rejected(self):
        data = strong_iv_data()
        with self.assertRaises(ValueError):
            anderson_rubin_test(data, 2.0, alpha=1.0)
        data["y"] = data["y"][:-1]
        with self.assertRaisesRegex(ValueError, "sample_sizes_must_match"):
            anderson_rubin_test(data, 2.0)

    def test_controls_are_residualized_before_ar_test(self):
        data = strong_iv_data()
        data["controls"] = [[float(i % 3)] for i in range(32)]
        result = anderson_rubin_test(data, 2.0)
        self.assertEqual(result["degrees_of_freedom"], [2, 28])


if __name__ == "__main__":
    unittest.main()
