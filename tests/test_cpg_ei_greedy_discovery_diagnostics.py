import unittest

from prototype.cpg_ei_greedy_discovery_diagnostics import run_sweep


class TestGreedyDiscoveryDiagnostics(unittest.TestCase):
    def test_small_sweep_reports_fit_and_structure_metrics(self):
        report = run_sweep(
            seeds=(11,),
            mvp_configs=((2.1, 2),),
            structure_configs=((2.1, 0.003, False),),
            structure_epochs=2,
            structure_rounds=1,
            samples=64,
        )
        self.assertEqual(len(report["mvp"]["records"]), 1)
        self.assertEqual(len(report["structure_discovery"]["records"]), 1)
        for section in ("mvp", "structure_discovery"):
            row = section and report[section]["records"][0]
            self.assertGreaterEqual(row["bit_accuracy"], 0.0)
            self.assertLessEqual(row["bit_accuracy"], 1.0)
            self.assertGreaterEqual(row["support_recall"], 0.0)
            self.assertLessEqual(row["support_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
