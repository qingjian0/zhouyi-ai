"""Evidence-driven concept split/merge prototype for E10-B.

Concept boundaries are revised from accumulated, revealed entity observations.
The current learner is a bounded categorical decision-tree-like partitioner:
it is not an open-world concept learner or a raw-perception system.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _gini(targets: list[bool]) -> float:
    if not targets:
        return 0.0
    p = sum(targets) / len(targets)
    return 2.0 * p * (1.0 - p)


@dataclass
class _Concept:
    concept_id: str
    parent_id: str | None
    members: list[str] = field(default_factory=list)
    split_key: str | None = None
    children: dict[str, str] = field(default_factory=dict)
    generation: int = 0
    last_revision_step: int = -10**9


class ConceptReviser:
    """Incrementally revise a categorical concept partition using revealed labels."""

    def __init__(
        self,
        *,
        min_members_per_child: int = 2,
        min_split_gain: float = 0.10,
        merge_rate_tolerance: float = 0.10,
        max_children: int = 4,
        proposal_budget: int = 128,
        revision_cooldown: int = 2,
    ):
        if (not isinstance(min_members_per_child, int) or isinstance(min_members_per_child, bool)
                or min_members_per_child < 2):
            raise ValueError("min_members_per_child must be an integer >= 2")
        if not 0.0 <= min_split_gain <= 1.0:
            raise ValueError("min_split_gain must be in [0, 1]")
        if not 0.0 <= merge_rate_tolerance <= 1.0:
            raise ValueError("merge_rate_tolerance must be in [0, 1]")
        if not isinstance(max_children, int) or isinstance(max_children, bool) or max_children < 2:
            raise ValueError("max_children must be an integer >= 2")
        if not isinstance(proposal_budget, int) or isinstance(proposal_budget, bool) or proposal_budget < 1:
            raise ValueError("proposal_budget must be an integer >= 1")
        if not isinstance(revision_cooldown, int) or isinstance(revision_cooldown, bool) or revision_cooldown < 0:
            raise ValueError("revision_cooldown must be an integer >= 0")
        self.min_members_per_child = min_members_per_child
        self.min_split_gain = min_split_gain
        self.merge_rate_tolerance = merge_rate_tolerance
        self.max_children = max_children
        self.proposal_budget = proposal_budget
        self.revision_cooldown = revision_cooldown
        self._root_id = "concept-root"
        self._nodes: dict[str, _Concept] = {self._root_id: _Concept(self._root_id, None)}
        self._evidence: dict[str, dict[str, Any]] = {}
        self._entity_observations: dict[str, str] = {}
        # Evidence that cannot traverse the current partition remains pending;
        # a later merge may make it routable without discarding its label.
        self._pending_observations: set[str] = set()
        self._events: list[dict[str, Any]] = []
        self._step = 0
        self._observation_step = 0
        self._proposal_evaluations = 0
        self._budget_exhausted = False

    def _leaf_for(self, features: dict[str, str]) -> str | None:
        current = self._root_id
        while True:
            node = self._nodes[current]
            if node.split_key is None:
                return current
            value = features.get(node.split_key)
            if value is None or value not in node.children:
                return None
            current = node.children[value]

    def _route_pending(self) -> int:
        """Re-route retained evidence after structural changes."""
        routed = 0
        for observation_id in sorted(tuple(self._pending_observations)):
            evidence = self._evidence[observation_id]
            leaf = self._leaf_for(evidence["features"])
            if leaf is None:
                continue
            self._nodes[leaf].members.append(observation_id)
            parent_id = self._nodes[leaf].parent_id
            while parent_id is not None:
                parent = self._nodes[parent_id]
                parent.members.append(observation_id)
                parent_id = parent.parent_id
            self._pending_observations.remove(observation_id)
            routed += 1
        if routed:
            self._record("reroute_pending", {
                "routed_count": routed,
                "pending_count": len(self._pending_observations),
            })
        return routed

    def _ancestor_split_keys(self, concept_id: str) -> set[str]:
        keys: set[str] = set()
        current: str | None = concept_id
        while current is not None:
            node = self._nodes[current]
            if node.split_key is not None:
                keys.add(node.split_key)
            current = node.parent_id
        return keys

    def _record(self, operation: str, payload: dict[str, Any]) -> None:
        self._step += 1
        self._events.append({
            "event_id": f"concept-revision-{self._step:06d}",
            "operation": operation,
            **payload,
        })

    def _targets(self, members: list[str]) -> list[bool]:
        return [self._evidence[eid]["target"] for eid in members]

    def _try_merge(self, parent: _Concept) -> bool:
        if parent.split_key is None or not parent.children:
            return False
        if self._observation_step - parent.last_revision_step < self.revision_cooldown:
            return False
        child_nodes = [self._nodes[cid] for _, cid in sorted(parent.children.items())]
        if any(not child.members or child.split_key is not None for child in child_nodes):
            return False
        rates = [sum(self._targets(child.members)) / len(child.members) for child in child_nodes]
        if max(rates) - min(rates) > self.merge_rate_tolerance:
            return False
        before = len(child_nodes)
        merged_members = sorted(eid for child in child_nodes for eid in child.members)
        child_ids = [child.concept_id for child in child_nodes]
        for child in child_nodes:
            child.members = []
        parent.members = merged_members
        parent.split_key = None
        parent.children = {}
        parent.generation += 1
        parent.last_revision_step = self._observation_step
        self._record("merge", {
            "parent_concept_id": parent.concept_id,
            "retired_child_concept_ids": child_ids,
            "evidence_ids": merged_members,
            "child_target_rates": rates,
            "rate_spread": max(rates) - min(rates),
            "complexity_delta": 1 - before,
        })
        return True

    def _best_split(self, node: _Concept) -> tuple[str, dict[str, list[str]], float] | None:
        if len(node.members) < self.min_members_per_child * 2:
            return None
        targets = self._targets(node.members)
        parent_impurity = _gini(targets)
        if parent_impurity <= 0.0:
            return None
        blocked = self._ancestor_split_keys(node.concept_id)
        keys = sorted({
            key for eid in node.members for key in self._evidence[eid]["features"]
            if key not in blocked
        })
        best: tuple[str, dict[str, list[str]], float] | None = None
        for key in keys:
            if self._proposal_evaluations >= self.proposal_budget:
                self._budget_exhausted = True
                return None
            self._proposal_evaluations += 1
            groups: dict[str, list[str]] = {}
            for eid in node.members:
                value = self._evidence[eid]["features"].get(key)
                if value is not None:
                    groups.setdefault(value, []).append(eid)
            if len(groups) < 2 or len(groups) > self.max_children:
                continue
            if any(len(group) < self.min_members_per_child for group in groups.values()):
                continue
            # Missing values are not silently treated as a category.
            if sum(map(len, groups.values())) != len(node.members):
                continue
            weighted = sum(
                len(group) / len(node.members) * _gini(self._targets(group))
                for group in groups.values()
            )
            gain = parent_impurity - weighted
            if gain < self.min_split_gain:
                continue
            candidate = (key, groups, gain)
            if best is None or gain > best[2] + 1e-12 or (
                abs(gain - best[2]) <= 1e-12 and key < best[0]
            ):
                best = candidate
        return best

    def _try_split(self, node: _Concept) -> bool:
        if self._observation_step - node.last_revision_step < self.revision_cooldown:
            return False
        proposal = self._best_split(node)
        if proposal is None:
            return False
        key, groups, gain = proposal
        child_ids: dict[str, str] = {}
        child_records = []
        for value, members in sorted(groups.items()):
            child_id = f"{node.concept_id}/{key}={value}/g{node.generation}"
            child = _Concept(child_id, node.concept_id, sorted(members))
            self._nodes[child_id] = child
            child_ids[value] = child_id
            child_records.append({
                "concept_id": child_id,
                "feature_value": value,
                "member_count": len(members),
                "target_rate": sum(self._targets(members)) / len(members),
            })
        parent_members = list(node.members)
        node.members = []
        node.split_key = key
        node.children = child_ids
        node.last_revision_step = self._observation_step
        self._record("split", {
            "parent_concept_id": node.concept_id,
            "feature_key": key,
            "children": child_records,
            "evidence_ids": sorted(parent_members),
            "impurity_gain": gain,
            "complexity_delta": len(child_ids) - 1,
        })
        return True

    def observe(
        self,
        *,
        observation_id: str,
        entity_id: str,
        features: dict[str, str],
        target: bool,
    ) -> dict[str, Any]:
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError("observation_id must be non-empty")
        if observation_id in self._evidence:
            raise ValueError("observation_id already observed")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("entity_id must be non-empty")
        if entity_id in self._entity_observations:
            raise ValueError("entity_id already has an observation")
        if not isinstance(features, dict) or not features:
            raise ValueError("features must be a non-empty dictionary")
        if any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
               for k, v in features.items()):
            raise ValueError("feature keys and values must be non-empty strings")
        if not isinstance(target, bool):
            raise ValueError("target must be boolean")
        self._observation_step += 1
        self._proposal_evaluations = 0
        self._budget_exhausted = False
        copied = dict(sorted(features.items()))
        self._evidence[observation_id] = {
            "observation_id": observation_id,
            "entity_id": entity_id,
            "features": copied,
            "target": target,
        }
        self._entity_observations[entity_id] = observation_id
        leaf = self._leaf_for(copied)
        if leaf is None:
            self._pending_observations.add(observation_id)
            self._record("unassigned", {
                "observation_id": observation_id,
                "entity_id": entity_id,
                "reason": "unseen_split_value_or_missing_feature",
            })
            return self.snapshot()
        self._nodes[leaf].members.append(observation_id)
        # Keep every ancestor's aggregate membership available for reversible merge.
        parent_id = self._nodes[leaf].parent_id
        while parent_id is not None:
            parent = self._nodes[parent_id]
            parent.members.append(observation_id)
            parent_id = parent.parent_id

        # First consider whether a previous split has become unnecessary.
        for node in list(self._nodes.values()):
            if node.split_key is not None:
                self._try_merge(node)
        # Then search current leaves for a better-supported split.
        for node in list(self._nodes.values()):
            if node.split_key is None and node.members:
                self._try_split(node)
        # A merge may remove a previously blocking split key. Revisit retained
        # observations only after all structural edits for this evidence step.
        self._route_pending()
        return self.snapshot()

    def predict_concept(self, features: dict[str, str]) -> dict[str, Any]:
        if not isinstance(features, dict):
            raise ValueError("features must be a dictionary")
        leaf = self._leaf_for(features)
        if leaf is None:
            return {
                "decision_status": "ABSTAIN_UNSEEN_CONCEPT_BRANCH",
                "concept_id": None,
                "partition_hash": self.partition_hash,
            }
        return {
            "decision_status": "ASSIGN",
            "concept_id": leaf,
            "partition_hash": self.partition_hash,
        }

    @property
    def partition_hash(self) -> str:
        active = self._active_partition()
        return _hash(active)

    def _active_partition(self) -> list[dict[str, Any]]:
        out = []
        for node in sorted(self._nodes.values(), key=lambda item: item.concept_id):
            if node.split_key is None and node.members:
                out.append({
                    "concept_id": node.concept_id,
                    "parent_id": node.parent_id,
                    "members": sorted(node.members),
                    "positive_rate": sum(self._targets(node.members)) / len(node.members),
                })
        return out

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self._step,
            "partition_hash": self.partition_hash,
            "active_concepts": self._active_partition(),
            "events": [dict(event) for event in self._events],
            "evidence_count": len(self._evidence),
            "pending_count": len(self._pending_observations),
            "pending_observation_ids": sorted(self._pending_observations),
            "observation_step": self._observation_step,
            "proposal_evaluations": self._proposal_evaluations,
            "proposal_budget": self.proposal_budget,
            "budget_exhausted": self._budget_exhausted,
        }
