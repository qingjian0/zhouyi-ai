"""E02-H: discovery of unknown three-input Boolean rules.

Unlike E02-E/F/G, the target is not a parity/product interaction. The learner
searches truth tables over unknown 2- and 3-feature subsets. The hidden target
table and member set are generator-only audit data.
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
    truth_table: int
    train_accuracy: float


def _state(values: tuple[int, ...], members: tuple[int, ...]) -> int:
    state = 0
    for position, member in enumerate(members):
        if values[member] == 1:
            state |= 1 << (len(members) - position - 1)
    return state


def _table_label(table: int, state: int) -> int:
    return 1 if (table >> state) & 1 else -1


def _is_affine(table: int) -> bool:
    outputs = [_table_label(table, i) == 1 for i in range(8)]
    for bias, a, b, c in itertools.product((0, 1), repeat=4):
        if all(outputs[i] == bool(
            bias ^ (a * ((i >> 2) & 1)) ^
            (b * ((i >> 1) & 1)) ^ (c * (i & 1))
        ) for i in range(8)):
            return True
    return False


def _all_variables_essential(table: int) -> bool:
    for bit in (2, 1, 0):
        if not any(_table_label(table, i) != _table_label(table, i ^ (1 << bit))
                   for i in range(8) if not (i & (1 << bit))):
            return False
    return True


def _best_pairwise_accuracy(table: int) -> float:
    best = 0.0
    for pair in ((0, 1), (0, 2), (1, 2)):
        remaining = ({0, 1, 2} - set(pair)).pop()
        correct = 0
        for a, b in itertools.product((0, 1), repeat=2):
            labels = []
            for third in (0, 1):
                bits = [0, 0, 0]
                bits[pair[0]], bits[pair[1]], bits[remaining] = a, b, third
                state = bits[0] * 4 + bits[1] * 2 + bits[2]
                labels.append(_table_label(table, state))
            correct += max(labels.count(1), labels.count(-1))
        best = max(best, correct / 8)
    return best


def admissible_target_tables() -> tuple[int, ...]:
    """Generator-only task constraints; never passed to the discovery code."""
    return tuple(
        table for table in range(256)
        if _all_variables_essential(table)
        and not _is_affine(table)
        and _best_pairwise_accuracy(table) <= 0.75
    )


def make_rows(*, seed: int, count: int, target_members: tuple[int, ...],
              target_table: int, width: int = 8, noise: float = 0.02) -> list[Row]:
    if count < 4 or width < 3 or len(target_members) != 3:
        raise ValueError("invalid sample count, width, or target order")
    if len(set(target_members)) != 3 or any(i < 0 or i >= width for i in target_members):
        raise ValueError("invalid target members")
    if not 0 <= target_table < 256 or not 0 <= noise < 0.5:
        raise ValueError("invalid truth table or noise")
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        values = tuple(rng.choice((-1, 1)) for _ in range(width))
        label = _table_label(target_table, _state(values, target_members))
        if rng.random() < noise:
            label *= -1
        rows.append(Row(f"{seed}:{i}", values, label))
    return rows


def _rank_subset(rows: list[Row], members: tuple[int, ...]) -> Candidate:
    states = 1 << len(members)
    positive = [0] * states
    negative = [0] * states
    for row in rows:
        state = _state(row.values, members)
        if row.label == 1:
            positive[state] += 1
        else:
            negative[state] += 1
    best_table, best_correct = 0, -1
    for table in range(1 << states):
        correct = sum(
            positive[s] if (table >> s) & 1 else negative[s]
            for s in range(states)
        )
        if correct > best_correct:
            best_table, best_correct = table, correct
    return Candidate(members, best_table, best_correct / len(rows))


def discover(rows: list[Row], *, min_order: int = 2, max_order: int = 3) -> Candidate:
    if not rows or min_order < 2 or max_order < min_order or max_order > 3:
        raise ValueError("invalid discovery request")
    width = len(rows[0].values)
    if any(len(row.values) != width for row in rows):
        raise ValueError("inconsistent feature widths")
    ranked = []
    for order in range(min_order, min(max_order, width) + 1):
        for members in itertools.combinations(range(width), order):
            ranked.append(_rank_subset(rows, members))
    ranked.sort(key=lambda c: (-c.train_accuracy, len(c.members),
                               c.members, c.truth_table))
    return ranked[0]


def predict(row: Row, candidate: Candidate) -> int:
    return _table_label(candidate.truth_table, _state(row.values, candidate.members))


def accuracy(rows: list[Row], candidate: Candidate) -> float:
    if not rows:
        raise ValueError("evaluation data cannot be empty")
    return sum(predict(row, candidate) == row.label for row in rows) / len(rows)


def pairwise_baseline(train: list[Row], evaluation: list[Row]) -> float:
    ranked = [_rank_subset(train, members)
              for members in itertools.combinations(range(len(train[0].values)), 2)]
    ranked.sort(key=lambda c: (-c.train_accuracy, c.members, c.truth_table))
    return accuracy(evaluation, ranked[0])


def run_episode(*, seed: int, train_n: int = 1024, gate_n: int = 512,
                test_n: int = 512, noise: float = 0.02,
                min_gate_accuracy: float = 0.75,
                min_gain: float = 0.05) -> dict:
    rng = random.Random(seed * 37 + 11)
    target_members = tuple(sorted(rng.sample(range(8), 3)))
    target_table = rng.choice(admissible_target_tables())
    train = make_rows(seed=seed * 1009 + 1, count=train_n,
                      target_members=target_members, target_table=target_table,
                      noise=noise)
    gate = make_rows(seed=seed * 1009 + 2, count=gate_n,
                     target_members=target_members, target_table=target_table,
                     noise=noise)
    test = make_rows(seed=seed * 1009 + 3, count=test_n,
                     target_members=target_members, target_table=target_table,
                     noise=noise)

    winner = discover(train)
    gate_accuracy = accuracy(gate, winner)
    pair_gate = pairwise_baseline(train, gate)
    gain = gate_accuracy - pair_gate
    support = tuple(r.sample_id for r in train if predict(r, winner) == r.label)
    counter = tuple(r.sample_id for r in train if predict(r, winner) != r.label)
    created = False
    rejection = None
    if gate_accuracy >= min_gate_accuracy and gain >= min_gain:
        manager = HyperedgeLifecycle(min_support=3, min_gain=min_gain, max_edges=8)
        try:
            manager.create(EdgeProposal(
                edge_id=f"e02h-{seed}",
                members=tuple(f"x{i}" for i in winner.members),
                roles=tuple(f"input-{i}" for i in range(len(winner.members))),
                relation_type=f"boolean-truth-table-order-{len(winner.members)}",
                support_ids=support, counterexample_ids=counter,
                validation_gain=gain, cost=1.0,
            ))
            created = True
        except LifecycleError as exc:
            rejection = str(exc)
    else:
        rejection = "independent gate accuracy or gain below threshold"

    return {
        "seed": seed,
        "discovered_members": list(winner.members),
        "discovered_truth_table": winner.truth_table,
        "train_accuracy": winner.train_accuracy,
        "gate_accuracy": gate_accuracy,
        "pairwise_gate_accuracy": pair_gate,
        "gate_gain": gain,
        "created": created,
        "rejection": rejection,
        "test_accuracy": accuracy(test, winner),
        "pairwise_test_accuracy": pairwise_baseline(train, test),
        "member_recovered": set(winner.members) == set(target_members),
        "truth_table_recovered": (
            tuple(winner.members) == target_members and
            winner.truth_table == target_table
        ),
        "target_members_for_audit_only": list(target_members),
        "target_truth_table_for_audit_only": target_table,
        "support_count": len(support),
        "counterexample_count": len(counter),
    }


def run(*, seeds: int = 30, start_seed: int = 900,
        train_n: int = 1024, gate_n: int = 512,
        test_n: int = 512, noise: float = 0.02) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    episodes = [run_episode(seed=start_seed + i, train_n=train_n,
                            gate_n=gate_n, test_n=test_n, noise=noise)
                for i in range(seeds)]
    return {
        "task": "E02H_unknown_non_affine_boolean_rule_discovery",
        "seeds": seeds,
        "settings": {
            "train_n": train_n, "gate_n": gate_n, "test_n": test_n,
            "noise": noise, "candidate_orders": "2..3",
            "candidate_language": "all truth tables over each 2- or 3-feature subset",
            "target_rule_family": "generator samples non-affine 3-input tables with all variables essential and pairwise Bayes accuracy <= 0.75",
        },
        "summary": {
            "member_recovery_rate": sum(e["member_recovered"] for e in episodes) / seeds,
            "exact_truth_table_recovery_rate": sum(e["truth_table_recovered"] for e in episodes) / seeds,
            "create_rate": sum(e["created"] for e in episodes) / seeds,
            "mean_gate_accuracy": sum(e["gate_accuracy"] for e in episodes) / seeds,
            "mean_test_accuracy": sum(e["test_accuracy"] for e in episodes) / seeds,
            "mean_pairwise_test_accuracy": sum(e["pairwise_test_accuracy"] for e in episodes) / seeds,
        },
        "episodes": episodes,
        "limitations": [
            "Synthetic binary three-input Boolean rules only.",
            "The generator constrains target functions to make the pairwise comparison meaningful; this is not an unconstrained task distribution.",
            "The learner's rule language is finite truth-table enumeration over subsets of size 2 or 3.",
            "No causal, natural-language, or open-domain discovery claim.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--start-seed", type=int, default=900)
    parser.add_argument("--train", type=int, default=1024)
    parser.add_argument("--gate", type=int, default=512)
    parser.add_argument("--test", type=int, default=512)
    parser.add_argument("--noise", type=float, default=0.02)
    args = parser.parse_args()
    print(json.dumps(run(seeds=args.seeds, start_seed=args.start_seed,
                         train_n=args.train, gate_n=args.gate,
                         test_n=args.test, noise=args.noise), indent=2))


if __name__ == "__main__":
    main()
