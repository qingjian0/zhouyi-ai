import unittest

from prototype.yixiang_pc_calibration_m54 import calibrate, _wilson_interval


class PCFisherZCalibrationTests(unittest.TestCase):
    def test_wilson_interval_contains_observed_rate(self):
        low, high = _wilson_interval(5, 100)
        self.assertLessEqual(low, 0.05)
        self.assertGreaterEqual(high, 0.05)

    def test_calibration_is_reproducible_and_reports_uncertainty(self):
        first = calibrate(repetitions=220, sample_sizes=(220,), seed=61014)
        second = calibrate(repetitions=220, sample_sizes=(220,), seed=61014)
        self.assertEqual(first, second)
        record = first["records"][0]
        self.assertIn("wilson_95", record["marginal_null_type_i"])
        self.assertIn("wilson_95", record["conditional_null_type_i"])
        self.assertLess(record["marginal_null_type_i"]["rate"], 0.13)
        self.assertLess(record["conditional_null_type_i"]["rate"], 0.15)
        self.assertGreater(record["marginal_power"]["0.4"]["rate"], 0.75)

    def test_rejects_too_few_repetitions(self):
        with self.assertRaisesRegex(ValueError, "repetitions_must_be_integer_at_least_50"):
            calibrate(repetitions=10)


if __name__ == "__main__":
    unittest.main()
