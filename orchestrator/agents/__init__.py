"""Agent collaboration contracts, provider interfaces, and artifact storage."""
from .protocol import AgentArtifact, AgentRegistry, AgentRequest, AgentResult, EvidenceRef
from .provider import (
    AgentProvider,
    ProviderBudget,
    ProviderRequest,
    ProviderResponse,
    invoke_provider,
)
from .artifact_store import ArtifactRef, ArtifactStore, FileArtifactStore

__all__ = [
    "AgentArtifact", "AgentRegistry", "AgentRequest", "AgentResult", "EvidenceRef",
    "AgentProvider", "ProviderBudget", "ProviderRequest", "ProviderResponse",
    "invoke_provider", "ArtifactRef", "ArtifactStore", "FileArtifactStore",
]
