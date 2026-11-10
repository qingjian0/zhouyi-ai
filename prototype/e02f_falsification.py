"""E02-F: falsification under train-only nuisance correlations.

A synthetic parity relation is hidden among binary features. In the nuisance
condition, one extra feature is made perfectly predictive in TRAIN ONLY and is
independent in gate/test. The learner searches singleton through 4-way
interactions, so it can select the nuisance feature. An independent gate must
reject it rather than persist a spurious hyperedge.

This is a targeted falsification benchmark, not an open-domain learner.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass

from prototype.e02_edge_lifecycle import EdgeProposal, HyperedgeLifecycle, LifecycleError


@dataclass(frozen=True)
class Row:
    sample_id: str
    values: tuple[int, ...]
    label: int


@dataclass(frozen=True)
class Candidate:
    members: tuple[int, ...]
    direction: int
    score: float


def make_split(*, seed: int, count: int, target: tuple[int, ...],
               width: int = 9, noise: float = 0.02,
               nuisance: str = "none", nuisance_noise: float = 0.0) -> list[Row]:
    if count < 4 or width < 5 or len(set(target)) != len(target):
        raise ValueError("invalid dimensions or target")
    if any(i < 0 or i >= width - 1 for i in target):
        raise ValueError("target members must exclude nuisance feature")
    if not 0 <= noise < 0.5 or not 0 <= nuisance_noise < 0.5:
        raise ValueError("noise rates must be in [0, 0.5)")
    if nuisance not in {"none", "train_only"}:
        raise ValueError("unknown nuisance mode")
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        values = [rng.choice((-1, 1)) for _ in range(width)]
        label = 1
        for member in target:
            label *= values[member]
        if rng.random() < noise:
            label *= -1
        if nuisance == "train_only":
            values[-1] = label * (-1 if rng.random() < nuisance_noise else 1)
        rows.append(Row(f"{seed}:{i}", tuple(values), label))
    return rows


def candidates(rows: list[Row], *, max_order: int = 4) -> list[Candidate]:
    if not rows:
        raise ValueError("rows cannot be empty")
    width = len(rows[0].values)
    if any(len(r.values) != width for r in rows):
        raise ValueError("inconsistent feature width")
    ranked = []
    for order in range(1, min(max_order, width) + 1):
        for members in itertools.combinations(range(width), order):
            corr = sum(
                r.label * _interaction(r.values, members) for r in rows
            ) / len(rows)
            ranked.append(Candidate(members, 1 if corr >= 0 else -1, abs(corr)))
    return sorted(ranked, key=lambda c: (-c.score, len(c.members), c.members))


def _interaction(values: tuple[int, ...], members: tuple[int, ...]) -> int:
    out = 1
    for member in members:
        out *= values[member]
    return out


def accuracy(rows: list[Row], candidate: Candidate) -> float:
    if not rows:
        raise ValueError("rows cannot be empty")
    return sum(
        candidate.direction * _interaction(r.values, candidate.members) == r.label
        for r in rows
    ) / len(rows)


def best_pair_accuracy(train: list[Row], evaluation: list[Row]) -> float:
    pairs = [
        c for c in candidates(train, max_order=2) if len(c.members) == 2
    ]
    return accuracy(evaluation, pairs[0])


def run_episode(*, seed: int, nuisance: str, train_n: int = 512,
                gate_n: int = 512, test_n: int = 512,
                label_noise: float = 0.02,
                nuisance_noise: float = 0.0,
                min_gain: float = 0.05, min_gate_accuracy: float = 0.75) -> dict:
    target_rng = random.Random(seed * 17 + 3)
    target = tuple(sorted(target_rng.sample(range(8), 3)))
    train = make_split(seed=seed * 1009 + 1, count=train_n, target=target,
                       noise=label_noise,
                       nuisance="train_only" if nuisance == "train_only" else "none",
                       nuisance_noise=nuisance_noise)
    gate = make_split(seed=seed * 1009 + 2, count=gate_n, target=target,
                      noise=label_noise, nuisance="none")
    test = make_split(seed=seed * 1009 + 3, count=test_n, target=target,
                      noise=label_noise, nuisance="none")

    winner = candidates(train)[0]
    gate_acc = accuracy(gate, winner)
    pair_gate = best_pair_accuracy(train, gate)
    gain = gate_acc - pair_gate
    support = tuple(r.sample_id for r in train
                    if winner.direction * _interaction(r.values, winner.members) == r.label)
    counter = tuple(r.sample_id for r in train
                    if winner.direction * _interaction(r.values, winner.members) != r.label)
    created = False
    rejection = None
    manager = HyperedgeLifecycle(min_support=3, min_gain=min_gain, max_edges=8)
    if gate_acc >= min_gate_accuracy and gain >= min_gain:
        try:
            manager.create(EdgeProposal(
                edge_id=f"e02f-{seed}",
                members=tuple(f"x{i}" for i in winner.members),
                roles=tuple(f"slot-{i}" for i in range(len(winner.members))),
                relation_type=f"interaction-order-{len(winner.members)}",
                support_ids=support, counterexample_ids=counter,
                validation_gain=gain, cost=1.0,
            ))
            created = True
        except LifecycleError as exc:
            rejection = str(exc)
    else:
        rejection = "independent gate accuracy or gain below creation threshold"

    return {
        "seed": seed, "condition": nuisance,
        "target": list(target), "winner": list(winner.members),
        "winner_order": len(winner.members), "train_score": winner.score,
        "gate_accuracy": gate_acc, "pairwise_gate_accuracy": pair_gate,
        "gate_gain": gain, "created": created, "rejection": rejection,
        "test_accuracy": accuracy(test, winner),
        "target_recovered": set(winner.members) == set(target),
        "support_count": len(support), "counterexample_count": len(counter),
    }


def run(*, seeds: int = 100, start_seed: int = 100,
        train_n: int = 512, gate_n: int = 512, test_n: int = 512,
        label_noise: float = 0.02, nuisance_noise: float = 0.0) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    conditions = {}
    for condition in ("none", "train_only"):
        rows = [run_episode(
            seed=start_seed + i, nuisance=condition, train_n=train_n,
            gate_n=gate_n, test_n=test_n, label_noise=label_noise,
            nuisance_noise=nuisance_noise,
        ) for i in range(seeds)]
        conditions[condition] = {
            "episodes": rows,
            "target_recovery_rate": sum(r["target_recovered"] for r in rows) / seeds,
            "create_rate": sum(r["created"] for r in rows) / seeds,
            "mean_gate_accuracy": sum(r["gate_accuracy"] for r in rows) / seeds,
            "mean_test_accuracy": sum(r["test_accuracy"] for r in rows) / seeds,
            "mean_pairwise_gate_accuracy": sum(
                r["pairwise_gate_accuracy"] for r in rows) / seeds,
            "mean_gate_gain": sum(r["gate_gain"] for r in rows) / seeds,
        }
    return {
        "task": "E02F_train_only_nuisance_falsification",
        "seeds": seeds, "seed_start": start_seed,
        "settings": {
            "train_n": train_n, "gate_n": gate_n, "test_n": test_n,
            "label_noise": label_noise, "nuisance_noise": nuisance_noise,
            "candidate_orders": "1..4", "min_gain": 0.05, "min_gate_accuracy": 0.75,
        },
        "conditions": conditions,
        "interpretation": (
            "The train_only condition adds a highly predictive nuisance feature "
            "only to training data. A robust discovery gate should reject it "
            "rather than commit it as a persistent relation. The clean condition "
            "checks that this rejection does not simply disable all discovery."
        ),
        "limitations": [
            "Binary synthetic parity family only.",
            "The candidate language remains bounded to multiplicative interactions.",
            "A single independent gate is a falsification screen, not a calibrated "
            "family-wise confidence procedure.",
            "No causal or open-domain concept discovery claim is made.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--train", type=int, default=512)
    parser.add_argument("--gate", type=int, default=512)
    parser.add_argument("--test", type=int, default=512)
    parser.add_argument("--label-noise", type=float, default=0.02)
    parser.add_argument("--nuisance-noise", type=float, default=0.0)
    args = parser.parse_args()
    print(json.dumps(run(
        seeds=args.seeds, start_seed=args.start_seed,
        train_n=args.train, gate_n=args.gate, test_n=args.test,
        label_noise=args.label_noise, nuisance_noise=args.nuisance_noise,
    ), indent=2))


if __name__ == "__main__":
    main()
