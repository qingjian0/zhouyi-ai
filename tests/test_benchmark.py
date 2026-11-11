import asyncio
import unittest

from orchestrator.core.benchmark import run_serial_parallel_benchmark
from orchestrator.core.scheduler import TaskSpec


class SerialParallelBenchmarkTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_outputs_and_speedup_report(self):
        async def handler(payload):
            await asyncio.sleep(0.001)
            return {"value": payload["value"] * 2}

        tasks = [
            TaskSpec(f"t{i}", "double", payload={"value": i})
            for i in range(8)
        ]
        report = await run_serial_parallel_benchmark(
            tasks, {"double": handler}, parallelism=4, repeats=2
        )
        self.assertTrue(report["equivalent"])
        self.assertEqual(report["task_count"], 8)
        self.assertEqual(len(report["serial"]["runs"]), 2)
        self.assertEqual(len(report["parallel"]["runs"]), 2)
        self.assertGreater(report["speedup"], 0)

    async def test_rejects_invalid_parallelism_and_repeats(self):
        async def handler(payload):
            return payload

        tasks = [TaskSpec("t0", "identity")]
        with self.assertRaises(ValueError):
            await run_serial_parallel_benchmark(tasks, {"identity": handler}, parallelism=1)
        with self.assertRaises(ValueError):
            await run_serial_parallel_benchmark(tasks, {"identity": handler}, repeats=0)

    async def test_rejects_non_json_handler_output(self):
        async def handler(payload):
            return object()

        tasks = [TaskSpec("t0", "bad")]
        with self.assertRaises((TypeError, ValueError)):
            await run_serial_parallel_benchmark(tasks, {"bad": handler}, repeats=1)


if __name__ == "__main__":
    unittest.main()
