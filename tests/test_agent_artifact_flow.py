import asyncio
import tempfile
import unittest

from orchestrator.agents import (
    AgentArtifact, AgentRegistry, AgentRequest, AgentResult,
    FileArtifactStore,
)


class AgentArtifactFlowTests(unittest.TestCase):
    def test_agent_result_artifacts_can_be_persisted_and_reloaded(self):
        async def scenario():
            registry = AgentRegistry()

            async def research_agent(request):
                return AgentResult(
                    request_id=request.request_id,
                    status="completed",
                    summary="Two independent hypotheses prepared.",
                    artifacts=(
                        AgentArtifact(
                            "hypothesis-set-1",
                            "hypotheses",
                            {"items": ["H1", "H2"], "selection_rule": "evidence-first"},
                        ),
                    ),
                )

            registry.register("research", research_agent)
            request = AgentRequest(
                request_id="research-001",
                role="research",
                objective="Generate falsifiable competing hypotheses",
                acceptance_criteria=("At least two hypotheses",),
            )
            result = await registry.dispatch(request)
            self.assertEqual(result.status, "completed")
            with tempfile.TemporaryDirectory() as temp:
                store = FileArtifactStore(temp)
                ref = store.put(result.artifacts[0])
                restored = store.get(ref)
                self.assertEqual(restored, result.artifacts[0])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
