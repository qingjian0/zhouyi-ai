"""E12-A18: bounded fork/join and state-transition motif discovery.

Predictive structure discovery only: graph motifs are not causal claims.
"""
from __future__ import annotations
import hashlib, json, math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


def _canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def _hash(x):
    return hashlib.sha256(_canon(x)).hexdigest()


@dataclass(frozen=True, order=True)
class Node:
    node_id: str
    node_type: str
    state: str = ""
    def __post_init__(self):
        if not self.node_id.strip() or not self.node_type.strip():
            raise ValueError("node id and type are required")


@dataclass(frozen=True, order=True)
class Edge:
    source: str
    relation: str
    target: str
    transition: str = ""
    def __post_init__(self):
        if not self.source.strip() or not self.target.strip() or not self.relation.strip():
            raise ValueError("edge endpoints and relation are required")
        if self.source == self.target:
            raise ValueError("self edges are unsupported")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    outcome: str
    def __post_init__(self):
        if not self.observation_id.strip() or not self.outcome.strip():
            raise ValueError("observation id and outcome are required")
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError("edge references unknown node")
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("duplicate edges")


@dataclass(frozen=True)
class Config:
    min_train_support: int = 3
    min_validation_support: int = 2
    max_candidates: int = 2000
    max_complexity_bits: float = 32.0
    min_train_mdl_gain_bits: float = 0.0
    min_validation_gain_bits: float = 0.0
    alpha: float = 0.5
    validation_fraction: float = 0.25
    def __post_init__(self):
        for n in ("min_train_support", "min_validation_support", "max_candidates"):
            if isinstance(getattr(self, n), bool) or getattr(self, n) < 1:
                raise ValueError(n + " must be positive")
        for n in ("max_complexity_bits", "min_train_mdl_gain_bits",
                  "min_validation_gain_bits", "alpha", "validation_fraction"):
            v = getattr(self, n)
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(n + " must be finite")
        if self.alpha <= 0 or self.max_complexity_bits <= 0:
            raise ValueError("alpha and complexity budget must be positive")
        if not 0 <= self.validation_fraction < 1:
            raise ValueError("validation_fraction must be in [0,1)")


@dataclass(frozen=True)
class Motif:
    motif_id: str
    shape: str
    center_type: str
    arms: tuple[tuple[str, str, str], ...]
    train_support: int
    validation_support: int
    train_gain_bits: float
    validation_gain_bits: float
    complexity_bits: float
    mdl_gain_bits: float
    grammar_version: str


@dataclass(frozen=True)
class Result:
    motifs: tuple[Motif, ...]
    generated_candidate_count: int
    truncated: bool
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    dataset_digest: str


def _split(rows, fraction):
    ordered = sorted(rows, key=lambda r: r.observation_id)
    if fraction == 0 or len(ordered) < 4:
        return ordered, []
    n = max(1, min(len(ordered)-2, round(len(ordered)*fraction)))
    return ordered[:-n], ordered[-n:]


def _present(row, shape, center_type, arms):
    """Require the full multiset of arms, including repeated signatures."""
    required = Counter(arms)
    types = {n.node_id: n.node_type for n in row.nodes}
    if shape == "FORK":
        for center in row.nodes:
            if center.node_type != center_type: continue
            sigs = Counter((e.relation, types[e.target], e.transition)
                           for e in row.edges if e.source == center.node_id)
            if all(sigs[arm] >= count for arm, count in required.items()):
                return True
    else:
        for center in row.nodes:
            if center.node_type != center_type: continue
            sigs = Counter((e.relation, types[e.source], e.transition)
                           for e in row.edges if e.target == center.node_id)
            if all(sigs[arm] >= count for arm, count in required.items()):
                return True
    return False


def _patterns(row):
    types = {n.node_id: n.node_type for n in row.nodes}
    found = set()
    for center in row.nodes:
        outgoing = sorted((e.relation, types[e.target], e.transition)
                          for e in row.edges if e.source == center.node_id)
        incoming = sorted((e.relation, types[e.source], e.transition)
                          for e in row.edges if e.target == center.node_id)
        for shape, sigs in (("FORK", outgoing), ("JOIN", incoming)):
            for i in range(len(sigs)):
                for j in range(i+1, len(sigs)):
                    found.add((shape, center.node_type, (sigs[i], sigs[j])))
    return found


def _dist(rows, outcomes, alpha):
    counts = Counter(r.outcome for r in rows)
    denom = len(rows) + alpha * len(outcomes)
    return {o:(counts[o]+alpha)/denom for o in outcomes}


def _gain(rows, base, cond, pattern):
    shape, center, arms = pattern
    return sum(math.log2(cond[r.outcome]/base[r.outcome])
               for r in rows if _present(r, shape, center, arms))


def discover(observations: Iterable[Observation], *, grammar_version="fork-join-state-v1",
             config=Config()):
    rows = tuple(observations)
    if len(rows) < 4: raise ValueError("at least four observations required")
    if len({r.observation_id for r in rows}) != len(rows):
        raise ValueError("observation ids must be unique")
    train, val = _split(rows, config.validation_fraction)
    outcomes = tuple(sorted({r.outcome for r in rows}))
    vocab = sorted(set().union(*(_patterns(r) for r in rows)))
    base = _dist(train, outcomes, config.alpha)
    candidates, motifs, truncated = 0, [], False
    for p in vocab:
        if candidates >= config.max_candidates:
            truncated = True
            break
        candidates += 1
        shape, center, arms = p
        mt = [r for r in train if _present(r, shape, center, arms)]
        mv = [r for r in val if _present(r, shape, center, arms)]
        if len(mt) < config.min_train_support: continue
        if val and len(mv) < config.min_validation_support: continue
        cond = _dist(mt, outcomes, config.alpha)
        complexity = 3 + math.log2(len(arms)+1) + len(arms)*math.log2(max(2,len(vocab))+1)
        if complexity > config.max_complexity_bits: continue
        tg = _gain(train, base, cond, p)
        vg = _gain(val, base, cond, p) if val else tg
        mg = tg-complexity
        if mg <= config.min_train_mdl_gain_bits: continue
        if val and vg <= config.min_validation_gain_bits: continue
        payload = {"shape":shape,"center":center,"arms":arms,"grammar":grammar_version}
        motifs.append(Motif("motif:"+_hash(payload)[:20],shape,center,arms,
            len(mt),len(mv),tg,vg,complexity,mg,grammar_version))
    motifs.sort(key=lambda m:(-m.validation_gain_bits,-m.mdl_gain_bits,m.shape,m.center_type,m.arms))
    digest = _hash([{"id":r.observation_id,
        "nodes":[(n.node_id,n.node_type,n.state) for n in sorted(r.nodes)],
        "edges":[(e.source,e.relation,e.target,e.transition) for e in sorted(r.edges)],
        "outcome":r.outcome} for r in sorted(rows,key=lambda x:x.observation_id)])
    return Result(tuple(motifs),candidates,truncated,
        tuple(r.observation_id for r in train),tuple(r.observation_id for r in val),digest)
