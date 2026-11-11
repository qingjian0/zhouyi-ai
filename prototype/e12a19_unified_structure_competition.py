"""E12-A19: shared-budget competition for sparse, path, and fork/join structures.

Candidates are proposed from training observations only. Validation is scored by
one shared categorical evaluator. Locked-test observations/labels are never accepted.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class Node:
    node_id: str
    node_type: str
    state: str = ""

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip()
               for x in (self.node_id, self.node_type)):
            raise ValueError("node_id and node_type are required")
        if not isinstance(self.state, str):
            raise ValueError("node state must be a string")


@dataclass(frozen=True, order=True)
class Edge:
    source: str
    relation: str
    target: str
    transition: str = ""

    def __post_init__(self):
        if any(not isinstance(x, str) or not x.strip()
               for x in (self.source, self.relation, self.target)):
            raise ValueError("edge endpoints and relation are required")
        if not isinstance(self.transition, str):
            raise ValueError("transition must be a string")
        if self.source == self.target:
            raise ValueError("self edges are unsupported")


@dataclass(frozen=True)
class Example:
    observation_id: str
    atoms: tuple[str, ...]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    outcome: str

    def __post_init__(self):
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not isinstance(self.outcome, str) or not self.outcome.strip():
            raise ValueError("outcome is required")
        if tuple(sorted(set(self.atoms))) != self.atoms:
            raise ValueError("atoms must be sorted and unique")
        if any(not isinstance(a, str) or not a.strip() for a in self.atoms):
            raise ValueError("atoms must be non-empty strings")
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError("edge endpoint is unknown")
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("duplicate edges are unsupported")


@dataclass(frozen=True)
class SplitManifest:
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    locked_test_ids: tuple[str, ...]
    outcome_vocabulary: tuple[str, ...]

    def __post_init__(self):
        groups = (self.train_ids, self.validation_ids, self.locked_test_ids)
        for group in groups:
            if tuple(sorted(set(group))) != group:
                raise ValueError("split IDs must be sorted and unique")
        if not self.train_ids or not self.validation_ids:
            raise ValueError("train and validation splits must be non-empty")
        if any(set(groups[i]) & set(groups[j]) for i in range(3) for j in range(i+1, 3)):
            raise ValueError("split IDs must be pairwise disjoint")
        if tuple(sorted(set(self.outcome_vocabulary))) != self.outcome_vocabulary:
            raise ValueError("outcome vocabulary must be sorted and unique")
        if len(self.outcome_vocabulary) < 2:
            raise ValueError("at least two declared outcome classes are required")

    @property
    def digest(self) -> str:
        return _digest({"train": self.train_ids, "validation": self.validation_ids,
                        "locked_test": self.locked_test_ids,
                        "outcomes": self.outcome_vocabulary})


@dataclass(frozen=True)
class Budget:
    max_candidates_per_family: int = 2000
    max_predicate_evaluations_per_family: int = 200000
    min_train_support: int = 3
    max_sparse_arity: int = 3
    max_path_length: int = 2
    alpha: float = 0.5

    def __post_init__(self):
        for name in ("max_candidates_per_family", "max_predicate_evaluations_per_family",
                     "min_train_support", "max_sparse_arity", "max_path_length"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(name + " must be a positive integer")
        if isinstance(self.alpha, bool) or not isinstance(self.alpha, (int, float)) or not math.isfinite(self.alpha) or self.alpha <= 0:
            raise ValueError("alpha must be finite and positive")


@dataclass(frozen=True)
class Candidate:
    family: str
    key: str
    payload: tuple


@dataclass(frozen=True)
class Metrics:
    log_loss: float
    accuracy: float
    brier_score: float


@dataclass(frozen=True)
class FamilyResult:
    family: str
    generated_candidate_count: int
    evaluated_candidate_count: int
    predicate_evaluations: int
    truncated: bool
    best_candidate_key: str | None
    best_candidate_complexity_bits_proxy: int | None
    validation: Metrics | None


@dataclass(frozen=True)
class CompetitionResult:
    split_digest: str
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    locked_test_ids: tuple[str, ...]
    baseline: Metrics
    families: tuple[FamilyResult, ...]
    dataset_digest: str


def _candidate(family: str, payload: tuple) -> Candidate:
    key = family.lower() + ":" + _digest(payload)[:20]
    return Candidate(family, key, payload)


def _path_signatures(row: Example, max_length: int):
    nodes = {n.node_id: n for n in row.nodes}
    outgoing = {}
    for edge in row.edges:
        outgoing.setdefault(edge.source, []).append(edge)
    found = set()

    def walk(node_id, path, visited):
        if path:
            found.add(path)
        if len(path) >= max_length:
            return
        for edge in sorted(outgoing.get(node_id, ())):
            if edge.target in visited:
                continue
            sig = (nodes[edge.source].node_type, edge.relation,
                   nodes[edge.target].node_type)
            walk(edge.target, path + (sig,), visited | {edge.target})

    for node_id in sorted(nodes):
        walk(node_id, (), frozenset((node_id,)))
    return found


def _fork_join_signatures(row: Example):
    types = {n.node_id: n.node_type for n in row.nodes}
    found = set()
    for center in row.nodes:
        outgoing = sorted((e.relation, types[e.target], e.transition)
                          for e in row.edges if e.source == center.node_id)
        incoming = sorted((e.relation, types[e.source], e.transition)
                          for e in row.edges if e.target == center.node_id)
        for shape, arms in (("FORK", outgoing), ("JOIN", incoming)):
            for i in range(len(arms)):
                for j in range(i + 1, len(arms)):
                    found.add((shape, center.node_type, (arms[i], arms[j])))
    return found


def _universe(train: tuple[Example, ...], budget: Budget):
    atoms = sorted({a for row in train for a in row.atoms})
    sparse = [_candidate("SPARSE_CONJUNCTION", tuple(combo))
              for k in range(1, min(budget.max_sparse_arity, len(atoms)) + 1)
              for combo in itertools.combinations(atoms, k)]
    paths = sorted(set().union(*(_path_signatures(r, budget.max_path_length) for r in train)))
    path_candidates = [_candidate("TYPED_PATH", p) for p in paths]
    forks = sorted(set().union(*(_fork_join_signatures(r) for r in train)))
    fork_candidates = [_candidate("FORK_JOIN", p) for p in forks]
    return {
        "SPARSE_CONJUNCTION": sorted(sparse, key=lambda c: c.key),
        "TYPED_PATH": sorted(path_candidates, key=lambda c: c.key),
        "FORK_JOIN": sorted(fork_candidates, key=lambda c: c.key),
    }


def _matches(row: Example, candidate: Candidate, budget: Budget) -> bool:
    if candidate.family == "SPARSE_CONJUNCTION":
        return all(atom in row.atoms for atom in candidate.payload)
    if candidate.family == "TYPED_PATH":
        return candidate.payload in _path_signatures(row, budget.max_path_length)
    if candidate.family == "FORK_JOIN":
        shape, center_type, arms = candidate.payload
        required = Counter(arms)
        types = {n.node_id: n.node_type for n in row.nodes}
        for center in row.nodes:
            if center.node_type != center_type:
                continue
            if shape == "FORK":
                actual = Counter((e.relation, types[e.target], e.transition)
                                 for e in row.edges if e.source == center.node_id)
            else:
                actual = Counter((e.relation, types[e.source], e.transition)
                                 for e in row.edges if e.target == center.node_id)
            if all(actual[arm] >= count for arm, count in required.items()):
                return True
        return False
    raise ValueError("unknown candidate family")


def _distribution(rows, outcomes, alpha):
    counts = Counter(r.outcome for r in rows)
    denom = len(rows) + alpha * len(outcomes)
    return {o: (counts[o] + alpha) / denom for o in outcomes}


def _metrics(rows, predictions, outcomes) -> Metrics:
    if not rows:
        raise ValueError("cannot score an empty split")
    losses, correct, briers = [], 0, []
    for row, probs in zip(rows, predictions):
        p = probs.get(row.outcome, 0.0)
        losses.append(-math.log(max(p, 1e-15)))
        correct += int(max(probs, key=probs.get) == row.outcome)
        briers.append(sum((probs[o] - (1.0 if row.outcome == o else 0.0)) ** 2
                          for o in outcomes))
    return Metrics(math.fsum(losses) / len(losses), correct / len(rows),
                   math.fsum(briers) / len(briers))


def _score_candidate(candidate, train, validation, outcomes, budget):
    matched = [r for r in train if _matches(r, candidate, budget)]
    if len(matched) < budget.min_train_support:
        return None, len(train) + len(validation)
    conditional = _distribution(matched, outcomes, budget.alpha)
    baseline = _distribution(train, outcomes, budget.alpha)
    predictions = [conditional if _matches(r, candidate, budget) else baseline
                   for r in validation]
    return _metrics(validation, predictions, outcomes), len(train) + len(validation)


def compete(train_examples: Iterable[Example], validation_examples: Iterable[Example],
            manifest: SplitManifest, *, budget: Budget = Budget()) -> CompetitionResult:
    """Compare three proposal families; no locked-test examples or labels are accepted."""
    train, validation = tuple(train_examples), tuple(validation_examples)
    if len({r.observation_id for r in train}) != len(train):
        raise ValueError("duplicate training observation IDs")
    if len({r.observation_id for r in validation}) != len(validation):
        raise ValueError("duplicate validation observation IDs")
    if tuple(sorted(r.observation_id for r in train)) != manifest.train_ids:
        raise ValueError("training IDs do not match split manifest")
    if tuple(sorted(r.observation_id for r in validation)) != manifest.validation_ids:
        raise ValueError("validation IDs do not match split manifest")
    if set(r.outcome for r in train) - set(manifest.outcome_vocabulary):
        raise ValueError("training outcome outside declared vocabulary")
    if set(r.outcome for r in validation) - set(manifest.outcome_vocabulary):
        raise ValueError("validation outcome outside declared vocabulary")
    if any(r.observation_id in set(manifest.locked_test_ids) for r in train + validation):
        raise ValueError("locked-test ID leaked into learner-visible data")

    outcomes = manifest.outcome_vocabulary
    prior = _distribution(train, outcomes, budget.alpha)
    baseline = _metrics(validation, [prior for _ in validation], outcomes)
    universes = _universe(train, budget)
    results = []
    dataset_digest = _digest([
        {"id": r.observation_id, "atoms": r.atoms,
         "nodes": [(n.node_id, n.node_type, n.state) for n in sorted(r.nodes)],
         "edges": [(e.source, e.relation, e.target, e.transition) for e in sorted(r.edges)],
         "outcome": r.outcome}
        for r in sorted(train + validation, key=lambda x: x.observation_id)
    ])

    for family in ("SPARSE_CONJUNCTION", "TYPED_PATH", "FORK_JOIN"):
        universe = universes[family]
        limited = universe[:budget.max_candidates_per_family]
        truncated = len(universe) > len(limited)
        used, evaluated, best = 0, 0, None
        for candidate in limited:
            cost = len(train) + len(validation)
            if used + cost > budget.max_predicate_evaluations_per_family:
                truncated = True
                break
            metric, actual_cost = _score_candidate(candidate, train, validation,
                                                   outcomes, budget)
            used += actual_cost
            evaluated += 1
            if metric is not None and (best is None or
                    (metric.log_loss, candidate.key) < (best[0].log_loss, best[1].key)):
                best = (metric, candidate, len(_canonical(candidate.payload).encode("utf-8")) * 8)
        results.append(FamilyResult(
            family, len(universe), evaluated, used, truncated,
            best[1].key if best else None,
            best[2] if best else None,
            best[0] if best else None))
    return CompetitionResult(manifest.digest, manifest.train_ids,
        manifest.validation_ids, manifest.locked_test_ids, baseline,
        tuple(results), dataset_digest)
