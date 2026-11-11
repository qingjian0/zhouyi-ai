import asyncio
import unittest

from orchestrator.agents.provider import (
    ProviderBudget, ProviderRequest, ProviderResponse, invoke_provider,
)


class FakeProvider:
    def __init__(self, response=None, delay=0):
        self.response = response
        self.delay = delay
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return self.response or ProviderResponse(
            request.request_id, request.model, "ok", 12, 3
        )


class ProviderContractTests(unittest.TestCase):
    def request(self, **budget):
        return ProviderRequest(
            "req-1", "mock-model", "system", "user",
            ProviderBudget(**budget),
        )

    def test_mock_provider_round_trip(self):
        async def scenario():
            provider = FakeProvider()
            response = await invoke_provider(provider, self.request())
            self.assertEqual(response.text, "ok")
            self.assertEqual(provider.calls, 1)
        asyncio.run(scenario())

    def test_prompt_budget_rejected_before_call(self):
        with self.assertRaisesRegex(ValueError, "max_prompt_chars"):
            ProviderRequest(
                "r", "m", "1234", "5678",
                ProviderBudget(max_prompt_chars=7),
            )

    def test_output_budget_enforced(self):
        async def scenario():
            provider = FakeProvider(ProviderResponse("req-1", "mock-model", "large", 1, 9))
            with self.assertRaisesRegex(ValueError, "max_output_tokens"):
                await invoke_provider(provider, self.request(max_output_tokens=8))
        asyncio.run(scenario())

    def test_request_correlation_enforced(self):
        async def scenario():
            provider = FakeProvider(ProviderResponse("wrong", "mock-model", "x", 1, 1))
            with self.assertRaisesRegex(ValueError, "does not match"):
                await invoke_provider(provider, self.request())
        asyncio.run(scenario())

    def test_timeout_is_enforced(self):
        async def scenario():
            provider = FakeProvider(delay=0.05)
            with self.assertRaises(asyncio.TimeoutError):
                await invoke_provider(
                    provider, self.request(timeout_seconds=0.001)
                )
        asyncio.run(scenario())

    def test_invalid_budget_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            ProviderBudget(max_output_tokens=0)


if __name__ == "__main__":
    unittest.main()
