"""Provider adapter contracts and guarded invocation helpers.

Concrete adapters may call hosted or local models. This module deliberately
contains no network client, credential loading, retries, or implicit provider.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def _non_empty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ProviderBudget:
    max_prompt_chars: int = 32_000
    max_output_tokens: int = 2_000
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        for name in ("max_prompt_chars", "max_output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ProviderRequest:
    request_id: str
    model: str
    system_prompt: str
    user_prompt: str
    budget: ProviderBudget = field(default_factory=ProviderBudget)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _non_empty(self.request_id, "request_id")
        _non_empty(self.model, "model")
        if not isinstance(self.system_prompt, str) or not isinstance(self.user_prompt, str):
            raise ValueError("prompts must be strings")
        if not isinstance(self.budget, ProviderBudget):
            raise ValueError("budget must be ProviderBudget")
        if len(self.system_prompt) + len(self.user_prompt) > self.budget.max_prompt_chars:
            raise ValueError("prompt exceeds max_prompt_chars")
        if not isinstance(self.metadata, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in self.metadata.items()
        ):
            raise ValueError("metadata must be a string-to-string object")
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON-serializable") from exc


@dataclass(frozen=True)
class ProviderResponse:
    request_id: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        _non_empty(self.request_id, "response request_id")
        _non_empty(self.model, "response model")
        if not isinstance(self.text, str):
            raise ValueError("response text must be a string")
        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _non_empty(self.finish_reason, "finish_reason")
        if self.provider_request_id is not None and not isinstance(
            self.provider_request_id, str
        ):
            raise ValueError("provider_request_id must be a string or null")


@runtime_checkable
class AgentProvider(Protocol):
    """Implementations adapt a concrete model API to this stable contract."""

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...


async def invoke_provider(
    provider: AgentProvider, request: ProviderRequest
) -> ProviderResponse:
    """Apply timeout and response-budget checks around one provider call.

    Retries belong to the task scheduler, not this adapter boundary. A timed-out
    request may still have completed remotely; callers must treat retries as
    potentially duplicate billable operations.
    """
    if not isinstance(request, ProviderRequest):
        raise TypeError("request must be ProviderRequest")
    response = await asyncio.wait_for(
        provider.generate(request), timeout=request.budget.timeout_seconds
    )
    if not isinstance(response, ProviderResponse):
        raise TypeError("provider must return ProviderResponse")
    if response.request_id != request.request_id:
        raise ValueError("provider response request_id does not match request")
    if response.output_tokens > request.budget.max_output_tokens:
        raise ValueError("provider response exceeded max_output_tokens")
    return response
