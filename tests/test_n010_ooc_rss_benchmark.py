import unittest

from benchmarks.benchmark_n010_ooc_rss import _ru_maxrss_kib, _throughput_rates


class TestN010OocRssBenchmark(unittest.TestCase):
    def test_linux_ru_maxrss_is_already_kib(self):
        self.assertEqual(_ru_maxrss_kib(12345, "linux"), 12345)

    def test_macos_ru_maxrss_bytes_are_converted_to_kib(self):
        self.assertEqual(_ru_maxrss_kib(1024 * 123, "darwin"), 123)
        self.assertEqual(_ru_maxrss_kib(1025, "darwin"), 2)

    def test_throughput_rates_are_explicitly_end_to_end(self):
        self.assertEqual(
            _throughput_rates(100, 200, 10.0),
            {
                "train_rows_per_second_end_to_end": 10.0,
                "total_rows_per_second_end_to_end": 20.0,
            },
        )

    def test_throughput_rejects_nonpositive_elapsed_time(self):
        with self.assertRaises(ValueError):
            _throughput_rates(100, 200, 0.0)


if __name__ == "__main__":
    unittest.main()
