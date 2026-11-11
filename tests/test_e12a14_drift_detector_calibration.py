import unittest
from prototype.e12a14_drift_detector_calibration import (
    DetectorConfig, Scenario, _binomial_two_sided_pvalue, _generate, run_benchmark)

class DriftCalibrationTests(unittest.TestCase):
    def test_exact_binomial_is_bounded_and_symmetric(self):
        self.assertGreaterEqual(_binomial_two_sided_pvalue(10,20,0.5),0)
        self.assertLessEqual(_binomial_two_sided_pvalue(10,20,0.5),1)
        self.assertAlmostEqual(_binomial_two_sided_pvalue(2,20,0.2),
                               _binomial_two_sided_pvalue(18,20,0.8),places=8)

    def test_generator_is_reproducible(self):
        self.assertEqual(_generate(17,Scenario.ABRUPT,100,40),
                         _generate(17,Scenario.ABRUPT,100,40))

    def test_benchmark_reproducible_and_complete(self):
        first=run_benchmark(seeds=3,start_seed=9)
        second=run_benchmark(seeds=3,start_seed=9)
        self.assertEqual(first,second)
        self.assertEqual(len(first["summary"]),len(Scenario)*5)
        self.assertEqual(first["summary"]["stable:tv"]["episodes"],3)

    def test_small_benchmark_reports_all_scenarios_and_methods(self):
        result=run_benchmark(seeds=2,start_seed=1,horizon=80,change_at=30,
                             config=DetectorConfig(window=20,min_samples=10))
        for scenario in Scenario:
            for detector in ("tv","pearson","exact_binomial","cusum","change_point"):
                self.assertIn(f"{scenario.value}:{detector}",result["summary"])

    def test_invalid_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            run_benchmark(seeds=0)

if __name__=="__main__":
    unittest.main()
