"""Agent collaboration contracts and provider interfaces."""
from .protocol import AgentArtifact, AgentRegistry, AgentRequest, AgentResult, EvidenceRef
from .provider import (
    AgentProvider,
    ProviderBudget,
    ProviderRequest,
    ProviderResponse,
    invoke_provider,
)

__all__ = [
    "AgentArtifact", "AgentRegistry", "AgentRequest", "AgentResult", "EvidenceRef",
    "AgentProvider", "ProviderBudget", "ProviderRequest", "ProviderResponse",
    "invoke_provider",
]
