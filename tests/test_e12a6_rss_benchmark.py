import tempfile
import unittest
from pathlib import Path

from prototype.e12a6_rss_benchmark import _parse_sizes, _restore_report, _write_fixture


class E12A6RSSBenchmarkTests(unittest.TestCase):
    def test_size_parser_sorts_deduplicates_and_rejects_nonpositive(self):
        self.assertEqual(_parse_sizes("10,2,10"), [2, 10])
        with self.assertRaises(Exception):
            _parse_sizes("0,2")

    def test_fixture_restore_reports_exact_event_and_candidate_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "benchmark.sqlite"
            count = _write_fixture(path, 7, "benchmark-scope", 3)
            report = _restore_report(path, "benchmark-scope")
        self.assertEqual(count, 7)
        self.assertEqual(report["last_sequence"], 7)
        self.assertEqual(report["restored_candidate_count"], 7)
        self.assertIsNotNone(report["peak_rss_bytes"])


if __name__ == "__main__":
    unittest.main()
