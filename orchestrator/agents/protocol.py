"""Provider-neutral contracts for auditable R&D agents.

This module defines a boundary, not an LLM integration. Agents return deliverables,
evidence references and metrics; private chain-of-thought is neither requested nor stored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

AGENT_ROLES = {"research", "architecture", "implementation", "experiment", "review"}
RESULT_STATUSES = {"completed", "needs_input", "failed"}


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_json(value: Any, field_name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-serializable") from exc


@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    role: str
    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: tuple[str, ...] = ()
    budget: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.objective, "objective")
        if self.role not in AGENT_ROLES:
            raise ValueError(f"unsupported agent role: {self.role}")
        if not isinstance(self.context, dict):
            raise ValueError("context must be an object")
        _require_json(self.context, "context")
        if not isinstance(self.acceptance_criteria, tuple) or not all(
            isinstance(item, str) and item.strip() for item in self.acceptance_criteria
        ):
            raise ValueError("acceptance_criteria must be a tuple of non-empty strings")
        if not isinstance(self.budget, dict):
            raise ValueError("budget must be an object")
        for key, value in self.budget.items():
            _require_text(key, "budget key")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"budget[{key}] must be a non-negative integer")
        _require_json(self.budget, "budget")


@dataclass(frozen=True)
class AgentArtifact:
    artifact_id: str
    kind: str
    content: Any

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.kind, "artifact kind")
        _require_json(self.content, "artifact content")


@dataclass(frozen=True)
class EvidenceRef:
    source: str
    claim: str
    locator: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.source, "evidence source")
        _require_text(self.claim, "evidence claim")
        if self.locator is not None and not isinstance(self.locator, str):
            raise ValueError("evidence locator must be a string or null")


@dataclass(frozen=True)
class AgentResult:
    request_id: str
    status: str
    summary: str
    artifacts: tuple[AgentArtifact, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.request_id, "result request_id")
        _require_text(self.summary, "result summary")
        if self.status not in RESULT_STATUSES:
            raise ValueError(f"unsupported result status: {self.status}")
        if not isinstance(self.artifacts, tuple) or not all(
            isinstance(item, AgentArtifact) for item in self.artifacts
        ):
            raise ValueError("artifacts must be a tuple of AgentArtifact")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(item, EvidenceRef) for item in self.evidence
        ):
            raise ValueError("evidence must be a tuple of EvidenceRef")
        if not isinstance(self.metrics, dict):
            raise ValueError("metrics must be an object")
        _require_json(self.metrics, "metrics")
        if not isinstance(self.blockers, tuple) or not all(
            isinstance(item, str) and item.strip() for item in self.blockers
        ):
            raise ValueError("blockers must be a tuple of non-empty strings")
        if self.status == "needs_input" and not self.blockers:
            raise ValueError("needs_input results must describe at least one blocker")


AgentHandler = Callable[[AgentRequest], Awaitable[AgentResult]]


class AgentRegistry:
    """Explicit role-to-handler registry; no dynamic imports or implicit permissions."""

    def __init__(self) -> None:
        self._handlers: dict[str, AgentHandler] = {}

    def register(self, role: str, handler: AgentHandler) -> None:
        if role not in AGENT_ROLES:
            raise ValueError(f"unsupported agent role: {role}")
        if role in self._handlers:
            raise ValueError(f"agent role already registered: {role}")
        if not callable(handler):
            raise ValueError("agent handler must be callable")
        self._handlers[role] = handler

    async def dispatch(self, request: AgentRequest) -> AgentResult:
        handler = self._handlers.get(request.role)
        if handler is None:
            raise ValueError(f"no agent registered for role: {request.role}")
        result = await handler(request)
        if not isinstance(result, AgentResult):
            raise TypeError("agent handler must return AgentResult")
        if result.request_id != request.request_id:
            raise ValueError("agent result request_id does not match request")
        # Ensure results can be persisted by the orchestrator checkpoint/artifact layer.
        _require_json({
            "request_id": result.request_id,
            "status": result.status,
            "summary": result.summary,
            "artifacts": [
                {"artifact_id": a.artifact_id, "kind": a.kind, "content": a.content}
                for a in result.artifacts
            ],
            "evidence": [
                {"source": e.source, "claim": e.claim, "locator": e.locator}
                for e in result.evidence
            ],
            "metrics": result.metrics,
            "blockers": list(result.blockers),
        }, "agent result")
        return result
