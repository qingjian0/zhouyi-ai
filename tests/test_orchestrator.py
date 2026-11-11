import asyncio, tempfile, unittest
from pathlib import Path
from orchestrator.core.scheduler import Scheduler, TaskGraph, TaskSpec

class OrchestratorTests(unittest.TestCase):
    def test_plan_parallel_waves(self):
        graph=TaskGraph([TaskSpec("a","record"),TaskSpec("b","record"),TaskSpec("c","record",("a","b"))])
        self.assertEqual(graph.plan(),[["a","b"],["c"]])
    def test_cycle_rejected(self):
        with self.assertRaisesRegex(ValueError,"cycle"): TaskGraph([TaskSpec("a","x",("b",)),TaskSpec("b","x",("a",))])
    def test_unknown_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError,"unknown dependencies"): TaskGraph([TaskSpec("a","x",("missing",))])
    def test_run_and_checkpoint(self):
        async def scenario():
            async def handler(payload): await asyncio.sleep(.005); return payload["n"]
            with tempfile.TemporaryDirectory() as d:
                graph=TaskGraph([TaskSpec("a","work",payload={"n":1}),TaskSpec("b","work",payload={"n":2}),TaskSpec("c","work",("a","b"),{"n":3})])
                state=await Scheduler(graph,{"work":handler},Path(d)/"state.json",2).run()
                self.assertTrue(all(x["status"]=="succeeded" for x in state.values()))
                self.assertTrue((Path(d)/"state.json").exists())
        asyncio.run(scenario())
    def test_retry(self):
        async def scenario():
            calls={"n":0}
            async def flaky(_):
                calls["n"]+=1
                if calls["n"]==1: raise RuntimeError("temporary")
                return "ok"
            with tempfile.TemporaryDirectory() as d:
                state=await Scheduler(TaskGraph([TaskSpec("a","flaky",max_retries=1)]),{"flaky":flaky},Path(d)/"state.json").run()
                self.assertEqual(state["a"]["status"],"succeeded"); self.assertEqual(state["a"]["attempts"],2)
        asyncio.run(scenario())

if __name__=="__main__": unittest.main()
