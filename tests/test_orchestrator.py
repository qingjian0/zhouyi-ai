import asyncio
import tempfile
import unittest
from pathlib import Path

from orchestrator.core.scheduler import Scheduler, TaskGraph, TaskSpec


class OrchestratorTests(unittest.TestCase):
    def test_plan_parallel_waves(self):
        graph = TaskGraph([
            TaskSpec("a", "record"), TaskSpec("b", "record"),
            TaskSpec("c", "record", ("a", "b")),
        ])
        self.assertEqual(graph.plan(), [["a", "b"], ["c"]])

    def test_cycle_rejected(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            TaskGraph([TaskSpec("a", "x", ("b",)), TaskSpec("b", "x", ("a",))])

    def test_unknown_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            TaskGraph([TaskSpec("a", "x", ("missing",))])

    def test_manifest_payload_must_be_json_serializable(self):
        with self.assertRaisesRegex(ValueError, "JSON-serializable"):
            TaskGraph([TaskSpec("a", "x", payload={"bad": object()})])

    def test_run_and_checkpoint(self):
        async def scenario():
            async def handler(payload):
                await asyncio.sleep(.005)
                return payload["n"]
            with tempfile.TemporaryDirectory() as directory:
                graph = TaskGraph([
                    TaskSpec("a", "work", payload={"n": 1}),
                    TaskSpec("b", "work", payload={"n": 2}),
                    TaskSpec("c", "work", ("a", "b"), {"n": 3}),
                ])
                checkpoint = Path(directory) / "state.json"
                state = await Scheduler(graph, {"work": handler}, checkpoint, 2).run()
                self.assertTrue(all(item["status"] == "succeeded" for item in state.values()))
                self.assertTrue(checkpoint.exists())
        asyncio.run(scenario())

    def test_retry(self):
        async def scenario():
            calls = {"n": 0}
            async def flaky(_):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("temporary")
                return "ok"
            with tempfile.TemporaryDirectory() as directory:
                checkpoint = Path(directory) / "state.json"
                state = await Scheduler(
                    TaskGraph([TaskSpec("a", "flaky", max_retries=1)]),
                    {"flaky": flaky}, checkpoint,
                ).run()
                self.assertEqual(state["a"]["status"], "succeeded")
                self.assertEqual(state["a"]["attempts"], 2)
        asyncio.run(scenario())

    def test_non_json_result_fails_task_instead_of_crashing_checkpoint(self):
        async def scenario():
            async def bad_result(_):
                return object()
            with tempfile.TemporaryDirectory() as directory:
                checkpoint = Path(directory) / "state.json"
                state = await Scheduler(
                    TaskGraph([TaskSpec("a", "bad")]), {"bad": bad_result}, checkpoint,
                ).run()
                self.assertEqual(state["a"]["status"], "failed")
                self.assertIn("TypeError", state["a"]["error"])
                self.assertTrue(checkpoint.exists())
        asyncio.run(scenario())

    def test_resume_rejects_corrupt_task_state(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                checkpoint = Path(directory) / "state.json"
                checkpoint.write_text(
                    '{"version":1,"tasks":{"a":{"status":"impossible","attempts":0}}}',
                    encoding="utf-8",
                )
                scheduler = Scheduler(
                    TaskGraph([TaskSpec("a", "work")]),
                    {"work": lambda _: asyncio.sleep(0)},
                    checkpoint,
                )
                with self.assertRaisesRegex(ValueError, "invalid state"):
                    await scheduler.run(resume=True)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
