import tempfile
import unittest

from prototype.yixiang_m55_study import run_study, summarize, write_outputs


class M55StudyTests(unittest.TestCase):
    def test_small_complete_study_and_raw_predictions(self):
        records = run_study(seeds=(11, 13, 17), sample_sizes=(100,),
                            scenarios=("linear_gaussian", "latent_common_cause"))
        self.assertEqual(len(records), 2 * 1 * 3 * 3)
        self.assertTrue(all("predicted_parents" in row for row in records))
        self.assertTrue(all("true_parents" in row for row in records))
        report = summarize(records, bootstrap_repetitions=500)
        self.assertEqual(len(report["scenario_summaries"]), 2 * 3)
        self.assertEqual(len(report["paired_f1_contrasts"]), 2 * 2)

    def test_study_writes_machine_readable_artifacts(self):
        records = run_study(seeds=(2, 5), sample_sizes=(100,),
                            scenarios=("linear_gaussian",))
        report = summarize(records, bootstrap_repetitions=300)
        with tempfile.TemporaryDirectory() as directory:
            paths = write_outputs(records, report, directory)
            for path in paths.values():
                with open(path, encoding="utf-8") as handle:
                    self.assertTrue(handle.read())

    def test_rejects_invalid_design(self):
        with self.assertRaisesRegex(ValueError, "seeds_must_be_nonempty_and_unique"):
            run_study(seeds=(), sample_sizes=(100,), scenarios=("linear_gaussian",))


if __name__ == "__main__":
    unittest.main()
