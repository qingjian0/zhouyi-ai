import json
import subprocess
import sys
import time
import unittest

from prototype.memory_budget import (
    MIB,
    MemoryBudgetExceeded,
    MemoryPoolLedger,
    ProcessMemoryMeasurement,
    sample_process_memory,
)


class MemoryPoolLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = MemoryPoolLedger(16 * MIB)
        self.ledger.register_pool("state", 8 * MIB)
        self.ledger.register_pool("retrieval", 8 * MIB)

    def test_reserve_release_and_peak_are_tracked(self):
        self.ledger.reserve("state", 3 * MIB)
        self.ledger.reserve("state", 2 * MIB)
        self.ledger.release("state", MIB)
        state = next(row for row in self.ledger.snapshot() if row.name == "state")
        self.assertEqual(state.current_bytes, 4 * MIB)
        self.assertEqual(state.peak_bytes, 5 * MIB)
        self.assertEqual(state.reserve_count, 2)
        self.assertEqual(state.release_count, 1)

    def test_pool_limit_rejects_reservation_without_mutation(self):
        self.ledger.reserve("state", 8 * MIB)
        with self.assertRaises(MemoryBudgetExceeded):
            self.ledger.reserve("state", 1)
        self.assertEqual(self.ledger.current_bytes, 8 * MIB)

    def test_aggregate_limit_rejects_reservation(self):
        ledger = MemoryPoolLedger(16 * MIB)
        ledger.register_pool("state", 12 * MIB)
        ledger.register_pool("retrieval", 12 * MIB)
        ledger.reserve("state", 8 * MIB)
        ledger.reserve("retrieval", 8 * MIB)
        with self.assertRaises(MemoryBudgetExceeded):
            ledger.reserve("state", 1)
        self.assertEqual(ledger.current_bytes, 16 * MIB)
        self.assertEqual(ledger.peak_bytes, 16 * MIB)

    def test_release_underflow_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.release("state", 1)

    def test_eviction_updates_release_and_eviction_counters(self):
        self.ledger.reserve("retrieval", 4096)
        self.ledger.record_eviction("retrieval", 1024)
        row = next(x for x in self.ledger.snapshot() if x.name == "retrieval")
        self.assertEqual(row.current_bytes, 3072)
        self.assertEqual(row.eviction_count, 1)
        self.assertEqual(row.evicted_bytes, 1024)
        self.assertEqual(row.release_count, 1)

    def test_duplicate_pool_and_unknown_pool_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.register_pool("state", 1)
        with self.assertRaises(KeyError):
            self.ledger.reserve("missing", 1)

    def test_bool_is_not_accepted_as_a_byte_count(self):
        with self.assertRaises(ValueError):
            self.ledger.reserve("state", True)


class ProcessMemoryTests(unittest.TestCase):
    def test_process_sample_has_valid_units_and_source(self):
        sample = sample_process_memory()
        self.assertGreater(sample.timestamp_ns, 0)
        self.assertIn(sample.source, {"procfs", "windows-psapi", "psutil", "unavailable"})
        if sample.rss_bytes is not None:
            self.assertGreater(sample.rss_bytes, 0)
            self.assertGreaterEqual(sample.os_peak_rss_bytes, sample.rss_bytes)
            self.assertGreater(sample.rss_mib, 0)

    def test_measurement_context_records_a_report(self):
        with ProcessMemoryMeasurement(interval_seconds=0.005) as measurement:
            payload = bytearray(2 * MIB)
            for index in range(0, len(payload), 4096):
                payload[index] = 1
            time.sleep(0.025)
            self.assertEqual(payload[0], 1)
        self.assertIsNotNone(measurement.report)
        self.assertGreaterEqual(measurement.report.sample_count, 2)
        self.assertGreaterEqual(
            measurement.report.sampled_peak_rss_bytes,
            measurement.report.baseline_rss_bytes,
        )
        self.assertGreaterEqual(measurement.report.peak_increment_bytes, 0)
        self.assertGreaterEqual(measurement.report.final_increment_bytes, 0)

    def test_cli_json_is_parseable(self):
        completed = subprocess.run(
            [sys.executable, "-m", "prototype.memory_budget", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertIn(completed.returncode, (0, 2), completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIn("rss_bytes", result)
        self.assertEqual(result["unit"], "bytes; MiB fields use 1024*1024")


if __name__ == "__main__":
    unittest.main()
