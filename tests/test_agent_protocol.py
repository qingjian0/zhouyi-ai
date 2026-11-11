import asyncio
import unittest

from orchestrator.agents.protocol import (
    AgentArtifact, AgentRegistry, AgentRequest, AgentResult, EvidenceRef
)


class AgentProtocolTests(unittest.TestCase):
    def test_dispatch_returns_structured_artifacts_and_evidence(self):
        async def scenario():
            registry = AgentRegistry()
            async def researcher(request):
                return AgentResult(
                    request_id=request.request_id,
                    status="completed",
                    summary="Compared candidate hypotheses.",
                    artifacts=(AgentArtifact("a1", "research_note", {"hypotheses": 3}),),
                    evidence=(EvidenceRef("paper:example", "Reports a ternary encoding result."),),
                    metrics={"sources_reviewed": 4},
                )
            registry.register("research", researcher)
            result = await registry.dispatch(AgentRequest(
                "req-1", "research", "Assess ternary-state representations."
            ))
            self.assertEqual(result.artifacts[0].artifact_id, "a1")
            self.assertEqual(result.evidence[0].source, "paper:example")
        asyncio.run(scenario())

    def test_rejects_unknown_role(self):
        with self.assertRaisesRegex(ValueError, "unsupported agent role"):
            AgentRequest("r", "general", "Do research")

    def test_rejects_non_json_artifact(self):
        with self.assertRaisesRegex(ValueError, "JSON-serializable"):
            AgentArtifact("a1", "note", object())

    def test_needs_input_requires_blocker(self):
        with self.assertRaisesRegex(ValueError, "blocker"):
            AgentResult("r", "needs_input", "Need clarification")

    def test_rejects_result_for_different_request(self):
        async def scenario():
            registry = AgentRegistry()
            async def wrong_request(_):
                return AgentResult("other", "completed", "wrong correlation")
            registry.register("review", wrong_request)
            with self.assertRaisesRegex(ValueError, "does not match"):
                await registry.dispatch(AgentRequest("expected", "review", "Review artifact"))
        asyncio.run(scenario())

    def test_role_cannot_be_registered_twice(self):
        async def handler(_):
            return AgentResult("r", "completed", "ok")
        registry = AgentRegistry()
        registry.register("research", handler)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register("research", handler)


if __name__ == "__main__":
    unittest.main()
