"""E02-E: counterexample-driven discovery of unknown higher-order relations.

This is a transparent CPU baseline, not a neural learner. It does not receive
the target member set or relation order. It enumerates bounded interaction
candidates, ranks them on training evidence, then uses an independent gate set
to decide whether a candidate may become a persistent hyperedge.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import asdict, dataclass

from prototype.e02_edge_lifecycle import EdgeProposal, HyperedgeLifecycle, LifecycleError


@dataclass(frozen=True)
class Observation:
    sample_id: str
    values: tuple[int, ...]
    label: int


@dataclass(frozen=True)
class Candidate:
    members: tuple[int, ...]
    direction: int
    train_correlation: float


def make_dataset(*, seed: int, count: int, width: int = 8,
                 target_members: tuple[int, ...] | None = None,
                 noise: float = 0.02) -> tuple[list[Observation], tuple[int, ...]]:
    if count < 4 or width < 4 or not 0.0 <= noise < 0.5:
        raise ValueError("invalid dataset dimensions or noise")
    rng = random.Random(seed)
    if target_members is None:
        target_members = tuple(sorted(rng.sample(range(width), 3)))
    if len(target_members) < 2 or len(set(target_members)) != len(target_members):
        raise ValueError("target relation must contain unique members")
    if any(i < 0 or i >= width for i in target_members):
        raise ValueError("target member index outside feature width")
    rows = []
    for i in range(count):
        values = tuple(rng.choice((-1, 1)) for _ in range(width))
        label = 1
        for member in target_members:
            label *= values[member]
        if rng.random() < noise:
            label *= -1
        rows.append(Observation(f"s{seed}-{i}", values, label))
    return rows, target_members


def interaction(values: tuple[int, ...], members: tuple[int, ...]) -> int:
    result = 1
    for member in members:
        result *= values[member]
    return result


def propose_candidates(rows: list[Observation], *, min_order: int = 2,
                       max_order: int = 4, top_k: int = 8) -> list[Candidate]:
    if not rows or min_order < 2 or max_order < min_order:
        raise ValueError("invalid candidate-generation request")
    width = len(rows[0].values)
    if any(len(row.values) != width for row in rows):
        raise ValueError("inconsistent feature widths")
    ranked = []
    for order in range(min_order, min(max_order, width) + 1):
        for members in itertools.combinations(range(width), order):
            corr = sum(interaction(row.values, members) * row.label
                       for row in rows) / len(rows)
            ranked.append(Candidate(members, 1 if corr >= 0 else -1, abs(corr)))
    ranked.sort(key=lambda c: (-c.train_correlation, len(c.members), c.members))
    return ranked[:top_k]


def accuracy(rows: list[Observation], candidate: Candidate) -> float:
    if not rows:
        raise ValueError("evaluation set cannot be empty")
    return sum(candidate.direction * interaction(r.values, candidate.members)
               == r.label for r in rows) / len(rows)


def pairwise_baseline(train: list[Observation], gate: list[Observation]) -> float:
    pairs = propose_candidates(train, min_order=2, max_order=2, top_k=1)
    return accuracy(gate, pairs[0])


def discover(*, seed: int, train_n: int = 512, gate_n: int = 256,
             test_n: int = 512, noise: float = 0.02,
             min_gain: float = 0.05) -> dict:
    # Independent seeds prevent sample reuse across train, gate and final test.
    train, hidden_target = make_dataset(seed=seed * 1009 + 1, count=train_n,
                                        noise=noise)
    gate, _ = make_dataset(seed=seed * 1009 + 2, count=gate_n,
                           target_members=hidden_target, noise=noise)
    test, _ = make_dataset(seed=seed * 1009 + 3, count=test_n,
                           target_members=hidden_target, noise=noise)

    proposals = propose_candidates(train, top_k=16)
    if not proposals:
        raise RuntimeError("candidate generator returned no candidates")
    winner = proposals[0]
    gate_accuracy = accuracy(gate, winner)
    pair_gate_accuracy = pairwise_baseline(train, gate)
    gain = gate_accuracy - pair_gate_accuracy

    # Evidence IDs are disjoint by construction. Counterexamples are retained,
    # not silently discarded; the gate set is never used to fit the candidate.
    supports = tuple(r.sample_id for r in train
                     if winner.direction * interaction(r.values, winner.members) == r.label)
    counterexamples = tuple(r.sample_id for r in train
                            if winner.direction * interaction(r.values, winner.members) != r.label)
    manager = HyperedgeLifecycle(min_support=3, min_gain=min_gain, max_edges=32)
    created = False
    rejection = None
    if gain >= min_gain:
        try:
            manager.create(EdgeProposal(
                edge_id=f"e02e-{seed}-{','.join(map(str, winner.members))}",
                members=tuple(f"x{i}" for i in winner.members),
                roles=tuple(f"slot-{i}" for i in range(len(winner.members))),
                relation_type=f"interaction-order-{len(winner.members)}",
                support_ids=supports, counterexample_ids=counterexamples,
                validation_gain=gain, cost=float(len(proposals)),
            ))
            created = True
        except LifecycleError as exc:
            rejection = str(exc)
    else:
        rejection = "independent gate gain below creation threshold"

    return {
        "seed": seed,
        "feature_width": len(train[0].values),
        "candidate_pool_size": sum(
            1 for order in range(2, 5)
            for _ in itertools.combinations(range(len(train[0].values)), order)),
        "ranked_candidates": [
            {"members": list(c.members), "order": len(c.members),
             "train_correlation": c.train_correlation}
            for c in proposals
        ],
        "discovered_members": list(winner.members),
        "discovered_order": len(winner.members),
        "gate_accuracy": gate_accuracy,
        "pairwise_gate_accuracy": pair_gate_accuracy,
        "gate_gain": gain,
        "created": created,
        "rejection": rejection,
        "support_count": len(supports),
        "counterexample_count": len(counterexamples),
        "test_accuracy": accuracy(test, winner),
        "test_pairwise_accuracy": pairwise_baseline(train, test),
        "hidden_target_for_audit_only": list(hidden_target),
        "limitations": [
            "Bounded interaction enumeration is an explicit inductive bias, not open-ended concept invention.",
            "Synthetic binary interaction task only; no natural-language or causal discovery claim.",
            "A single gate split can be noisy; future work must add repeated gates and confidence intervals.",
            "The lifecycle manager is a validator/state machine, not the candidate learner."
        ],
    }


def run(seeds: int = 20, start_seed: int = 7, **kwargs) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    rows = [discover(seed=start_seed + i, **kwargs) for i in range(seeds)]
    return {
        "task": "E02E_unknown_higher_order_interaction_discovery",
        "seeds": rows,
        "summary": {
            "creation_rate": sum(r["created"] for r in rows) / seeds,
            "member_set_recovery_rate": sum(
                set(r["discovered_members"]) == set(r["hidden_target_for_audit_only"])
                for r in rows) / seeds,
            "mean_gate_accuracy": sum(r["gate_accuracy"] for r in rows) / seeds,
            "mean_test_accuracy": sum(r["test_accuracy"] for r in rows) / seeds,
            "mean_pairwise_test_accuracy": sum(
                r["test_pairwise_accuracy"] for r in rows) / seeds,
        },
        "interpretation": (
            "Discovery is counted only when a train-ranked candidate passes an "
            "independent gate against a pairwise baseline. Test data is evaluated "
            "after the structural decision and is not used to select the edge."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train", type=int, default=512)
    parser.add_argument("--gate", type=int, default=256)
    parser.add_argument("--test", type=int, default=512)
    parser.add_argument("--noise", type=float, default=0.02)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seeds, args.start_seed, train_n=args.train,
                  gate_n=args.gate, test_n=args.test, noise=args.noise)
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
