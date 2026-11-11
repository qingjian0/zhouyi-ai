"""E12-A17: budgeted discovery of typed directed relation paths.

Research prototype: discovers one-edge and two-edge typed path motifs from
observed graphs. It does not infer causality or semantic meaning from labels.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, order=True)
class Node:
    node_id: str
    node_type: str
    state: str = ""

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip()
               for v in (self.node_id, self.node_type)):
            raise ValueError("node_id and node_type must be non-empty strings")
        if not isinstance(self.state, str):
            raise ValueError("state must be a string")


@dataclass(frozen=True, order=True)
class DirectedEdge:
    source: str
    relation: str
    target: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip()
               for v in (self.source, self.relation, self.target)):
            raise ValueError("edge endpoints and relation must be non-empty strings")
        if self.source == self.target:
            raise ValueError("self edges are not supported in this prototype")


@dataclass(frozen=True)
class GraphObservation:
    observation_id: str
    nodes: tuple[Node, ...]
    edges: tuple[DirectedEdge, ...]
    outcome: str

    def __post_init__(self):
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not isinstance(self.outcome, str) or not self.outcome.strip():
            raise ValueError("outcome is required")
        if not isinstance(self.nodes, tuple) or not isinstance(self.edges, tuple):
            raise ValueError("nodes and edges must be tuples")
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique within an observation")
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError("every edge endpoint must reference a known node")
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("duplicate edges are not allowed")


@dataclass(frozen=True)
class GraphDiscoveryConfig:
    max_path_length: int = 2
    min_train_support: int = 3
    min_validation_support: int = 2
    max_candidates: int = 2000
    max_complexity_bits: float = 24.0
    min_train_mdl_gain_bits: float = 0.0
    min_validation_gain_bits: float = 0.0
    laplace_alpha: float = 0.5
    validation_fraction: float = 0.25

    def __post_init__(self):
        for name in ("max_path_length", "min_train_support", "min_validation_support",
                     "max_candidates"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("max_complexity_bits", "min_train_mdl_gain_bits",
                     "min_validation_gain_bits", "laplace_alpha", "validation_fraction"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.max_complexity_bits <= 0 or self.laplace_alpha <= 0:
            raise ValueError("complexity budget and Laplace alpha must be positive")
        if not 0 <= self.validation_fraction < 1:
            raise ValueError("validation_fraction must be in [0,1)")


@dataclass(frozen=True)
class RelationMotif:
    motif_id: str
    version: int
    path: tuple[tuple[str, str, str], ...]
    train_support: int
    validation_support: int
    train_gain_bits: float
    validation_gain_bits: float
    complexity_bits: float
    mdl_gain_bits: float
    parent_refs: tuple[str, ...]
    grammar_version: str


@dataclass(frozen=True)
class GraphDiscoveryResult:
    motifs: tuple[RelationMotif, ...]
    generated_candidate_count: int
    truncated: bool
    train_observation_ids: tuple[str, ...]
    validation_observation_ids: tuple[str, ...]
    dataset_digest: str


def _split(rows: tuple[GraphObservation, ...], fraction: float):
    ordered = sorted(rows, key=lambda row: row.observation_id)
    if fraction == 0 or len(ordered) < 4:
        return ordered, []
    count = max(1, min(len(ordered) - 2, round(len(ordered) * fraction)))
    return ordered[:-count], ordered[-count:]


def _paths(row: GraphObservation, max_length: int):
    nodes = {node.node_id: node for node in row.nodes}
    outgoing: dict[str, list[DirectedEdge]] = {}
    for edge in row.edges:
        outgoing.setdefault(edge.source, []).append(edge)
    found = set()

    def walk(node_id: str, path: tuple, visited: frozenset[str]):
        if path:
            found.add(path)
        if len(path) >= max_length:
            return
        for edge in sorted(outgoing.get(node_id, [])):
            if edge.target in visited:
                continue
            signature = (nodes[edge.source].node_type, edge.relation,
                         nodes[edge.target].node_type)
            walk(edge.target, path + (signature,), visited | {edge.target})

    for node_id in sorted(nodes):
        walk(node_id, (), frozenset({node_id}))
    return found


def _matches(row: GraphObservation, motif: tuple[tuple[str, str, str], ...]) -> bool:
    return motif in _paths(row, len(motif))


def _distribution(rows, outcomes, alpha):
    counts = Counter(row.outcome for row in rows)
    denom = len(rows) + alpha * len(outcomes)
    return {o: (counts[o] + alpha) / denom for o in outcomes}


def _gain(rows, baseline, conditional, motif):
    return sum(math.log2(conditional[row.outcome] / baseline[row.outcome])
               for row in rows if _matches(row, motif))


def _complexity(motif, signature_vocab_size):
    # Explicit cost for path header, length, and each typed edge signature.
    n = max(2, signature_vocab_size)
    return 2.0 + math.log2(len(motif) + 1) + len(motif) * math.log2(n + 1)


def discover_relation_motifs(observations: Iterable[GraphObservation], *,
                             parent_refs: tuple[str, ...] = (),
                             grammar_version: str = "typed-directed-path-v1",
                             config: GraphDiscoveryConfig = GraphDiscoveryConfig()
                             ) -> GraphDiscoveryResult:
    rows = tuple(observations)
    if len(rows) < 4:
        raise ValueError("at least four observations are required")
    if len({r.observation_id for r in rows}) != len(rows):
        raise ValueError("observation ids must be unique")
    if any(not isinstance(x, str) or not x.strip() for x in parent_refs):
        raise ValueError("parent_refs must contain non-empty strings")
    if not isinstance(grammar_version, str) or not grammar_version.strip():
        raise ValueError("grammar_version is required")

    train, validation = _split(rows, config.validation_fraction)
    outcomes = tuple(sorted({r.outcome for r in rows}))
    vocab = sorted(set().union(*(_paths(r, config.max_path_length) for r in rows)))
    if not outcomes or not vocab:
        raise ValueError("observations need outcomes and at least one directed edge")
    baseline = _distribution(train, outcomes, config.laplace_alpha)
    generated, truncated, motifs = 0, False, []

    # Candidate generation is open over observed typed path motifs, not a fixed ontology.
    for motif in vocab:
        if generated >= config.max_candidates:
            truncated = True
            break
        generated += 1
        matched_train = [r for r in train if _matches(r, motif)]
        matched_val = [r for r in validation if _matches(r, motif)]
        if len(matched_train) < config.min_train_support:
            continue
        if validation and len(matched_val) < config.min_validation_support:
            continue
        conditional = _distribution(matched_train, outcomes, config.laplace_alpha)
        complexity = _complexity(motif, len(vocab))
        if complexity > config.max_complexity_bits:
            continue
        train_gain = _gain(train, baseline, conditional, motif)
        val_gain = _gain(validation, baseline, conditional, motif) if validation else train_gain
        mdl_gain = train_gain - complexity
        if mdl_gain <= config.min_train_mdl_gain_bits:
            continue
        if validation and val_gain <= config.min_validation_gain_bits:
            continue
        payload = {"path": motif, "parents": parent_refs, "grammar": grammar_version}
        motifs.append(RelationMotif("motif:" + _digest(payload)[:20], 1, motif,
            len(matched_train), len(matched_val), train_gain, val_gain,
            complexity, mdl_gain, parent_refs, grammar_version))

    motifs.sort(key=lambda m: (-m.validation_gain_bits, -m.mdl_gain_bits,
                               len(m.path), m.path, m.motif_id))
    dataset_payload = [{
        "id": r.observation_id,
        "nodes": [(n.node_id, n.node_type, n.state) for n in sorted(r.nodes)],
        "edges": [(e.source, e.relation, e.target) for e in sorted(r.edges)],
        "outcome": r.outcome,
    } for r in sorted(rows, key=lambda x: x.observation_id)]
    return GraphDiscoveryResult(tuple(motifs), generated, truncated,
        tuple(r.observation_id for r in train),
        tuple(r.observation_id for r in validation), _digest(dataset_payload))
