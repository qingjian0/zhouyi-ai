"""Public task-manifest validation and evidence provenance for XRA-P1."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

FORBIDDEN_LEARNER_KEYS = frozenset({
    "latent_state", "latent_states", "true_partition", "oracle_partition",
    "generator_id", "generator_family", "generator_seed", "true_k",
    "hidden_transition_table", "hidden_outcome_table", "transition_table",
})

@dataclass(frozen=True)
class TaskManifest:
    task_id: str
    episode_id: str
    actions: tuple[str, ...]
    observation_schema_version: str
    representation_version: str
    split: str
    action_costs: tuple[tuple[str, float], ...]
    horizon: int
    challenge_protocol: str
    missingness_semantics: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TaskManifest":
        required = {"task_id", "episode_id", "actions", "observation_schema_version",
                    "representation_version", "split", "action_costs", "horizon",
                    "challenge_protocol", "missingness_semantics"}
        if not isinstance(raw, Mapping):
            raise ValueError("manifest must be a mapping")
        if set(raw) != required:
            raise ValueError("manifest keys mismatch")
        def string(key):
            value = raw[key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(key + " must be a non-empty string")
            return value
        task_id, episode_id = string("task_id"), string("episode_id")
        schema, representation = string("observation_schema_version"), string("representation_version")
        split, protocol = string("split"), string("challenge_protocol")
        missingness = string("missingness_semantics")
        if split not in {"train", "development", "locked_test"}:
            raise ValueError("invalid split")
        if protocol != "paired_deterministic_v1":
            raise ValueError("unsupported challenge protocol")
        if missingness != "missing_is_unobserved_not_match":
            raise ValueError("unsupported missingness semantics")
        actions_raw = raw["actions"]
        if not isinstance(actions_raw, (list, tuple)) or not actions_raw:
            raise ValueError("actions must be a non-empty list")
        if any(not isinstance(a, str) or not a.strip() for a in actions_raw):
            raise ValueError("actions must be non-empty strings")
        actions = tuple(actions_raw)
        if len(set(actions)) != len(actions):
            raise ValueError("actions must be unique")
        costs_raw = raw["action_costs"]
        if not isinstance(costs_raw, Mapping) or set(costs_raw) != set(actions):
            raise ValueError("action_costs must define exactly the declared actions")
        costs = []
        for action in actions:
            cost = costs_raw[action]
            if isinstance(cost, bool) or not isinstance(cost, (int, float)):
                raise ValueError("action costs must be numeric")
            cost = float(cost)
            if not isfinite(cost) or cost <= 0:
                raise ValueError("action costs must be finite and > 0")
            costs.append((action, cost))
        horizon = raw["horizon"]
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise ValueError("horizon must be a positive integer")
        return cls(task_id, episode_id, actions, schema, representation, split,
                   tuple(costs), horizon, protocol, missingness)

    def learner_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "episode_id": self.episode_id,
            "actions": list(self.actions),
            "observation_schema_version": self.observation_schema_version,
            "representation_version": self.representation_version,
            "split": self.split, "action_costs": dict(self.action_costs),
            "horizon": self.horizon, "challenge_protocol": self.challenge_protocol,
            "missingness_semantics": self.missingness_semantics,
        }

def validate_learner_payload(payload: Any) -> None:
    """Reject evaluator-only keys recursively; this is defense-in-depth."""
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() in FORBIDDEN_LEARNER_KEYS:
                raise ValueError("forbidden evaluator-only key: " + key)
            validate_learner_payload(value)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            validate_learner_payload(value)

@dataclass(frozen=True)
class EvidenceProvenance:
    task_id: str
    episode_id: str
    trial_id: str
    action: str
    representation_version: str
    observation_schema_version: str
    split: str
    status: str
    measurement_cost: float

    def validate_against(self, manifest: TaskManifest) -> None:
        for field in ("task_id", "episode_id", "representation_version", "split"):
            if getattr(self, field) != getattr(manifest, field):
                raise ValueError("evidence " + field + " does not match manifest")
        if self.observation_schema_version != manifest.observation_schema_version:
            raise ValueError("observation schema version mismatch")
        if self.action not in manifest.actions:
            raise ValueError("undeclared evidence action")
        if not isinstance(self.trial_id, str) or not self.trial_id:
            raise ValueError("trial_id must be non-empty")
        if self.status not in {"observed", "missing", "censored"}:
            raise ValueError("invalid evidence status")
        cost = self.measurement_cost
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise ValueError("measurement_cost must be numeric")
        if not isfinite(float(cost)) or cost < 0:
            raise ValueError("measurement_cost must be finite and >= 0")
        if self.status == "observed" and cost <= 0:
            raise ValueError("observed evidence must record positive cost")
