"""Trusted, versioned E09 domain registry contract.

The registry is server-owned configuration. Remote callers never supply a
world-family/domain mapping; authority and verifier services resolve it by
scope and bind the immutable result into E09 event envelopes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class E09DomainRegistryError(ValueError):
    """A scope has no active trusted domain registration."""


@dataclass(frozen=True)
class E09DomainBinding:
    domain_id: str
    world_family: str
    registry_id: str
    registry_version: str
    active: bool = True

    def __post_init__(self) -> None:
        for field in ("domain_id", "world_family", "registry_id", "registry_version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        if not isinstance(self.active, bool):
            raise TypeError("active must be bool")


class E09DomainRegistry(Protocol):
    def resolve(self, scope: str) -> E09DomainBinding:
        """Return the current trusted binding for a scope or fail closed."""
        ...


class StaticE09DomainRegistry:
    """Immutable-by-default reference registry for tests and local deployments."""

    def __init__(self, bindings: Mapping[str, E09DomainBinding]) -> None:
        if not isinstance(bindings, Mapping) or not bindings:
            raise ValueError("domain registry requires a non-empty scope mapping")
        normalized = {}
        for scope, binding in bindings.items():
            if not isinstance(scope, str) or not scope.strip():
                raise ValueError("registry scopes must be non-empty strings")
            if not isinstance(binding, E09DomainBinding):
                raise TypeError("registry values must be E09DomainBinding")
            normalized[scope] = binding
        self._bindings = dict(normalized)

    def resolve(self, scope: str) -> E09DomainBinding:
        if not isinstance(scope, str) or not scope.strip():
            raise E09DomainRegistryError("scope must be a non-empty string")
        binding = self._bindings.get(scope)
        if binding is None:
            raise E09DomainRegistryError("scope has no trusted domain registration")
        if not binding.active:
            raise E09DomainRegistryError("trusted domain registration is revoked")
        return binding

    def revoke(self, scope: str) -> None:
        binding = self._bindings.get(scope)
        if binding is None:
            raise E09DomainRegistryError("scope has no trusted domain registration")
        self._bindings[scope] = E09DomainBinding(
            binding.domain_id, binding.world_family, binding.registry_id,
            binding.registry_version, active=False,
        )
