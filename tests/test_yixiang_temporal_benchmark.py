import unittest

from prototype.yixiang_temporal_benchmark import (
    event_order_accuracy,
    generate_temporal_benchmark,
)


class TemporalBenchmarkTests(unittest.TestCase):
    def test_same_latent_phases_across_sampling_rates(self):
        coarse = generate_temporal_benchmark(sample_interval=2.0)
        fine = generate_temporal_benchmark(sample_interval=0.5)
        self.assertEqual(coarse.phases, fine.phases)
        self.assertGreater(len(fine.observations), len(coarse.observations))

    def test_missingness_changes_observations_not_ground_truth(self):
        complete = generate_temporal_benchmark(sample_interval=1.0)
        missing = generate_temporal_benchmark(sample_interval=1.0,
                                              missing_indices=(2, 3, 8))
        self.assertEqual(complete.phases, missing.phases)
        self.assertEqual(len(complete.observations) - 3, len(missing.observations))
        self.assertEqual(missing.missing_times, (2.0, 3.0, 8.0))

    def test_variable_phase_lengths_are_explicit(self):
        result = generate_temporal_benchmark(
            duration=24.0, phase_lengths=(5.0, 7.0, 12.0), sample_interval=1.0
        )
        self.assertEqual(
            [(p.start, p.end) for p in result.phases],
            [(0.0, 5.0), (5.0, 12.0), (12.0, 24.0)],
        )

    def test_invalid_phase_lengths_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_temporal_benchmark(duration=30, phase_lengths=(10, 10, 9))

    def test_missing_indices_are_validated(self):
        with self.assertRaises(ValueError):
            generate_temporal_benchmark(missing_indices=(-1,))
        with self.assertRaises(ValueError):
            generate_temporal_benchmark(missing_indices=(30,))

    def test_non_finite_time_values_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_temporal_benchmark(sample_interval=float("nan"))

    def test_delayed_signal_respects_configured_lag(self):
        result = generate_temporal_benchmark(sample_interval=1.0, delay=2.0)
        by_time = {item.time: item for item in result.observations}
        self.assertEqual(by_time[11.0].delayed_signal, 0.0)
        self.assertEqual(by_time[12.0].delayed_signal, 1.0)

    def test_pairwise_event_order_accuracy(self):
        self.assertEqual(event_order_accuracy(("a", "b", "c"), ("a", "b", "c")), 1.0)
        self.assertAlmostEqual(event_order_accuracy(("b", "a", "c"), ("a", "b", "c")), 2 / 3)

    def test_duplicate_event_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            event_order_accuracy(("a", "a"), ("a", "b"))


if __name__ == "__main__":
    unittest.main()
