"""E02-C: auditable hyperedge lifecycle state machine.

This module is a deterministic research scaffold, not a learned hypergraph
model. All structural mutations require explicit evidence and held-out
validation measurements supplied by an evaluator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class EdgeProposal:
    edge_id: str
    members: tuple[str, ...]
    roles: tuple[str, ...]
    relation_type: str
    support_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    validation_gain: float
    cost: float


@dataclass(frozen=True)
class Hyperedge:
    edge_id: str
    members: tuple[str, ...]
    roles: tuple[str, ...]
    relation_type: str
    support_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    validation_gains: tuple[float, ...]
    cost: float
    age_windows: int = 1
    stale_windows: int = 0
    version: int = 1


class LifecycleError(ValueError):
    """Raised when a proposed structural mutation violates its contract."""


class HyperedgeLifecycle:
    def __init__(self, *, min_support: int = 3, min_gain: float = 0.01,
                 prune_patience: int = 3, merge_jaccard: float = 0.7,
                 split_gain_margin: float = 0.02,
                 max_edges: int = 128) -> None:
        if min_support < 1 or prune_patience < 1 or max_edges < 1:
            raise ValueError("support, patience, and edge budget must be positive")
        if not 0.0 <= merge_jaccard <= 1.0:
            raise ValueError("merge_jaccard must be in [0, 1]")
        self.min_support = min_support
        self.min_gain = min_gain
        self.prune_patience = prune_patience
        self.merge_jaccard = merge_jaccard
        self.split_gain_margin = split_gain_margin
        self.max_edges = max_edges
        self.edges: dict[str, Hyperedge] = {}
        self.events: list[dict] = []
        self._undo: list[dict[str, Hyperedge]] = []

    @staticmethod
    def _unique(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

    def _validate_proposal(self, p: EdgeProposal) -> None:
        if not p.edge_id or not p.relation_type:
            raise LifecycleError("edge_id and relation_type are required")
        if len(p.members) < 2 or len(set(p.members)) != len(p.members):
            raise LifecycleError("members must contain at least two unique ids")
        if len(p.roles) != len(p.members) or any(not role for role in p.roles):
            raise LifecycleError("each member must have one non-empty role")
        if len(set(p.support_ids)) < self.min_support:
            raise LifecycleError("insufficient independent support ids")
        if p.validation_gain < self.min_gain:
            raise LifecycleError("held-out validation gain is below threshold")
        if p.cost < 0:
            raise LifecycleError("cost cannot be negative")

    def _commit(self, event: dict) -> None:
        self._undo.append(dict(self.edges))
        self.events.append(event)

    def create(self, p: EdgeProposal) -> Hyperedge:
        self._validate_proposal(p)
        if p.edge_id in self.edges:
            raise LifecycleError("edge_id already exists")
        if len(self.edges) >= self.max_edges:
            raise LifecycleError("edge budget exhausted")
        edge = Hyperedge(
            edge_id=p.edge_id, members=p.members, roles=p.roles,
            relation_type=p.relation_type,
            support_ids=self._unique(p.support_ids),
            counterexample_ids=self._unique(p.counterexample_ids),
            validation_gains=(p.validation_gain,), cost=p.cost,
        )
        self._commit({"op": "CREATE", "edge_id": p.edge_id,
                      "validation_gain": p.validation_gain,
                      "support_count": len(edge.support_ids)})
        self.edges[p.edge_id] = edge
        return edge

    def observe(self, edge_id: str, *, support_ids: Iterable[str],
                counterexample_ids: Iterable[str], validation_gain: float,
                cost: float) -> Hyperedge:
        if edge_id not in self.edges:
            raise LifecycleError("unknown edge_id")
        if cost < 0:
            raise LifecycleError("cost cannot be negative")
        old = self.edges[edge_id]
        support = self._unique((*old.support_ids, *support_ids))
        counter = self._unique((*old.counterexample_ids, *counterexample_ids))
        stale = old.stale_windows + 1 if validation_gain < self.min_gain else 0
        updated = Hyperedge(
            edge_id=old.edge_id, members=old.members, roles=old.roles,
            relation_type=old.relation_type, support_ids=support,
            counterexample_ids=counter,
            validation_gains=old.validation_gains + (validation_gain,),
            cost=cost, age_windows=old.age_windows + 1,
            stale_windows=stale, version=old.version + 1,
        )
        self._commit({"op": "OBSERVE", "edge_id": edge_id,
                      "validation_gain": validation_gain,
                      "stale_windows": stale})
        self.edges[edge_id] = updated
        return updated

    @staticmethod
    def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb) if sa | sb else 0.0

    def merge(self, edge_a: str, edge_b: str, *, new_edge_id: str,
              measured_validation_gain: float) -> Hyperedge:
        if edge_a == edge_b or edge_a not in self.edges or edge_b not in self.edges:
            raise LifecycleError("merge requires two distinct existing edges")
        if new_edge_id in self.edges:
            raise LifecycleError("new edge_id already exists")
        a, b = self.edges[edge_a], self.edges[edge_b]
        if a.relation_type != b.relation_type or a.roles != b.roles:
            raise LifecycleError("cannot merge incompatible relation types or roles")
        if self._jaccard(a.members, b.members) < self.merge_jaccard:
            raise LifecycleError("member overlap is below merge threshold")
        if measured_validation_gain < max(a.validation_gains[-1],
                                           b.validation_gains[-1]) - self.split_gain_margin:
            raise LifecycleError("merged edge fails validation non-regression gate")
        members = self._unique((*a.members, *b.members))
        if len(members) != len(a.roles):
            raise LifecycleError("role mapping is ambiguous after member union")
        support = self._unique((*a.support_ids, *b.support_ids))
        if len(support) < self.min_support:
            raise LifecycleError("merged edge has insufficient support")
        if len(self.edges) - 1 > self.max_edges:
            raise LifecycleError("edge budget exceeded")
        merged = Hyperedge(
            edge_id=new_edge_id, members=members, roles=a.roles,
            relation_type=a.relation_type, support_ids=support,
            counterexample_ids=self._unique((*a.counterexample_ids,
                                              *b.counterexample_ids)),
            validation_gains=(measured_validation_gain,),
            cost=a.cost + b.cost, age_windows=1, stale_windows=0,
            version=max(a.version, b.version) + 1,
        )
        self._commit({"op": "MERGE", "parents": [edge_a, edge_b],
                      "edge_id": new_edge_id,
                      "validation_gain": measured_validation_gain})
        del self.edges[edge_a]
        del self.edges[edge_b]
        self.edges[new_edge_id] = merged
        return merged

    def split(self, edge_id: str, children: tuple[EdgeProposal, ...], *,
              measured_total_validation_gain: float) -> tuple[Hyperedge, ...]:
        if edge_id not in self.edges:
            raise LifecycleError("unknown parent edge")
        parent = self.edges[edge_id]
        if len(children) < 2:
            raise LifecycleError("split requires at least two children")
        if len({c.edge_id for c in children}) != len(children):
            raise LifecycleError("child edge ids must be unique")
        if any(c.edge_id in self.edges and c.edge_id != edge_id for c in children):
            raise LifecycleError("child edge_id already exists")
        if measured_total_validation_gain < parent.validation_gains[-1] + self.split_gain_margin:
            raise LifecycleError("split does not improve held-out validation enough")
        flattened = [m for child in children for m in child.members]
        if len(flattened) != len(set(flattened)) or set(flattened) != set(parent.members):
            raise LifecycleError("children must partition parent members exactly")
        built = []
        for child in children:
            self._validate_proposal(child)
            if child.relation_type != parent.relation_type:
                raise LifecycleError("child relation type must match parent")
            built.append(Hyperedge(
                edge_id=child.edge_id, members=child.members, roles=child.roles,
                relation_type=child.relation_type,
                support_ids=self._unique(child.support_ids),
                counterexample_ids=self._unique(child.counterexample_ids),
                validation_gains=(child.validation_gain,), cost=child.cost,
                age_windows=1, stale_windows=0, version=parent.version + 1,
            ))
        if len(self.edges) - 1 + len(built) > self.max_edges:
            raise LifecycleError("edge budget exceeded")
        self._commit({"op": "SPLIT", "parent": edge_id,
                      "children": [e.edge_id for e in built],
                      "validation_gain": measured_total_validation_gain})
        del self.edges[edge_id]
        for edge in built:
            self.edges[edge.edge_id] = edge
        return tuple(built)

    def prune(self, edge_id: str) -> Hyperedge:
        if edge_id not in self.edges:
            raise LifecycleError("unknown edge_id")
        edge = self.edges[edge_id]
        if edge.stale_windows < self.prune_patience:
            raise LifecycleError("edge has not met stale-window prune patience")
        self._commit({"op": "PRUNE", "edge_id": edge_id,
                      "stale_windows": edge.stale_windows})
        del self.edges[edge_id]
        return edge

    def rollback_last(self) -> dict:
        if not self.events:
            raise LifecycleError("no committed operation to roll back")
        event = self.events.pop()
        self.edges = self._undo.pop()
        return {"rolled_back": event, "remaining_edges": sorted(self.edges)}

    def audit_log(self) -> list[dict]:
        return [dict(event) for event in self.events]
