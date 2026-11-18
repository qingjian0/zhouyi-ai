"""Dimension-generic synthetic relational corpus for scaled CPG-EI experiments.

The default generator creates 40 independent 8-input / 8-output teachers.
Each teacher is evaluated on all 256 Boolean states, yielding 10,240
teacher-state rows. This is a data generator, not a trained learner.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Teacher:
    family_id: str
    seed: int
    supports: tuple[tuple[int, ...], ...]
    digest: str


def candidate_supports(
    input_dim: int, min_arity: int = 2, max_arity: int = 6
) -> tuple[tuple[int, ...], ...]:
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 2:
        raise ValueError("input_dim must be an integer >= 2")
    if (isinstance(min_arity, bool) or not isinstance(min_arity, int)
            or isinstance(max_arity, bool) or not isinstance(max_arity, int)
            or min_arity < 2 or max_arity < min_arity or max_arity > input_dim):
        raise ValueError("arity bounds must satisfy 2 <= min_arity <= max_arity <= input_dim")
    return tuple(
        support
        for arity in range(min_arity, max_arity + 1)
        for support in itertools.combinations(range(input_dim), arity)
    )


def make_teacher(
    family_seed: int,
    *,
    input_dim: int = 8,
    output_dim: int = 8,
    min_arity: int = 2,
    max_arity: int = 6,
) -> Teacher:
    candidates = candidate_supports(input_dim, min_arity, max_arity)
    if isinstance(output_dim, bool) or not isinstance(output_dim, int):
        raise ValueError("output_dim must be an integer")
    if not 1 <= output_dim <= len(candidates):
        raise ValueError("output_dim must be between 1 and the candidate support count")
    supports = tuple(sorted(random.Random(family_seed).sample(candidates, output_dim)))
    payload = {
        "family_seed": family_seed,
        "input_dim": input_dim,
        "output_dim": output_dim,
        "min_arity": min_arity,
        "max_arity": max_arity,
        "operator": "xor_parity",
        "supports": [list(item) for item in supports],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return Teacher(
        family_id=f"teacher-{family_seed}",
        seed=family_seed,
        supports=supports,
        digest=digest,
    )


def enumerate_states(input_dim: int) -> list[tuple[int, ...]]:
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 2:
        raise ValueError("input_dim must be an integer >= 2")
    return list(itertools.product((0, 1), repeat=input_dim))


def label_state(
    state: tuple[int, ...], supports: tuple[tuple[int, ...], ...]
) -> tuple[int, ...]:
    if any(index >= len(state) for support in supports for index in support):
        raise ValueError("support index exceeds state dimension")
    return tuple(sum(state[index] for index in support) % 2 for support in supports)


def _partition_sizes(total: int) -> tuple[int, int, int]:
    train = total // 2
    development = total // 4
    locked = total - train - development
    return train, development, locked


def _family_roles(
    states: list[tuple[int, ...]], family_split: str, seed: int
) -> dict[tuple[int, ...], str]:
    shuffled = list(states)
    random.Random(seed).shuffle(shuffled)
    support_count = max(1, len(shuffled) // 4)
    roles = {}
    for index, state in enumerate(shuffled):
        if family_split == "train":
            role = "meta_train"
        elif index < support_count:
            role = "support"
        elif family_split == "development":
            role = "query_development"
        else:
            role = "query_locked"
        roles[state] = role
    return roles


def generate_corpus(
    *,
    family_count: int = 40,
    input_dim: int = 8,
    output_dim: int = 8,
    min_arity: int = 2,
    max_arity: int = 6,
    seed: int = 20261113,
) -> dict:
    """Generate both state-disjoint and unseen-teacher split annotations."""
    if isinstance(family_count, bool) or not isinstance(family_count, int) or family_count < 5:
        raise ValueError("family_count must be an integer >= 5")
    states = enumerate_states(input_dim)
    train_size, development_size, locked_size = _partition_sizes(len(states))
    family_seeds = tuple(seed + 1000 + index for index in range(family_count))
    teachers = [
        make_teacher(
            family_seed,
            input_dim=input_dim,
            output_dim=output_dim,
            min_arity=min_arity,
            max_arity=max_arity,
        )
        for family_seed in family_seeds
    ]
    if len({teacher.digest for teacher in teachers}) != family_count:
        raise AssertionError("teacher generator produced duplicate family digests")

    family_order = list(range(family_count))
    random.Random(seed + 500_000).shuffle(family_order)
    train_families = int(family_count * 0.6)
    development_families = int(family_count * 0.2)
    family_split_by_index = {}
    for index in family_order[:train_families]:
        family_split_by_index[index] = "train"
    for index in family_order[train_families:train_families + development_families]:
        family_split_by_index[index] = "development"
    for index in family_order[train_families + development_families:]:
        family_split_by_index[index] = "locked"

    rows = []
    state_split_counts = Counter()
    family_split_counts = Counter()
    fewshot_role_counts = Counter()
    for teacher_index, teacher in enumerate(teachers):
        state_order = list(states)
        random.Random(seed + 700_000 + teacher.seed).shuffle(state_order)
        state_split_by_state = {}
        for state in state_order[:train_size]:
            state_split_by_state[state] = "train"
        for state in state_order[train_size:train_size + development_size]:
            state_split_by_state[state] = "development"
        for state in state_order[train_size + development_size:]:
            state_split_by_state[state] = "locked"

        family_split = family_split_by_index[teacher_index]
        roles = _family_roles(states, family_split, seed + 900_000 + teacher.seed)
        family_split_counts[family_split] += 1
        for state in states:
            state_split = state_split_by_state[state]
            role = roles[state]
            row = {
                "family_id": teacher.family_id,
                "family_seed": teacher.seed,
                "teacher_digest": teacher.digest,
                "family_split": family_split,
                "fewshot_role": role,
                "state_split": state_split,
                "state": list(state),
                "target": list(label_state(state, teacher.supports)),
            }
            rows.append(row)
            state_split_counts[state_split] += 1
            fewshot_role_counts[role] += 1

    manifest = {
        "dataset_id": "zhouyi-cpg-ei-scaled-relations-v1",
        "generator_version": "1.0.0",
        "seed": seed,
        "input_dim": input_dim,
        "output_dim": output_dim,
        "operator": "xor_parity",
        "arity_range": [min_arity, max_arity],
        "candidate_support_count": len(candidate_supports(input_dim, min_arity, max_arity)),
        "family_count": family_count,
        "states_per_family": len(states),
        "row_count": len(rows),
        "state_split_rows": dict(sorted(state_split_counts.items())),
        "family_split_counts": dict(sorted(family_split_counts.items())),
        "fewshot_role_rows": dict(sorted(fewshot_role_counts.items())),
        "state_split_per_family": {
            "train": train_size,
            "development": development_size,
            "locked": locked_size,
        },
        "family_split_policy": "60/20/20 by teacher identity before model fitting",
        "fewshot_policy": "25% support and remaining query states for held-out teacher families",
        "teacher_digests": [teacher.digest for teacher in teachers],
        "claim_boundary": (
            "Synthetic XOR relation benchmark only. It does not establish causal discovery, "
            "natural-language reasoning, arbitrary relation learning, or superiority to "
            "Transformer models."
        ),
    }
    canonical = json.dumps(
        {"manifest": manifest, "rows": rows},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest["corpus_sha256"] = hashlib.sha256(canonical).hexdigest()
    _validate_corpus(manifest, rows, teachers, states)
    return {"manifest": manifest, "teachers": teachers, "rows": rows}


def _validate_corpus(manifest, rows, teachers, states) -> None:
    if len(rows) != manifest["family_count"] * len(states):
        raise AssertionError("row count does not match family_count * state_count")
    by_family = {}
    for row in rows:
        by_family.setdefault(row["family_id"], []).append(row)
        if len(row["state"]) != manifest["input_dim"]:
            raise AssertionError("row state dimension mismatch")
        if len(row["target"]) != manifest["output_dim"]:
            raise AssertionError("row target dimension mismatch")
    if set(by_family) != {teacher.family_id for teacher in teachers}:
        raise AssertionError("teacher family coverage mismatch")
    for family_rows in by_family.values():
        state_sets = {
            split: {tuple(row["state"]) for row in family_rows if row["state_split"] == split}
            for split in ("train", "development", "locked")
        }
        if any(len(state_sets[split]) != manifest["state_split_per_family"][split]
               for split in state_sets):
            raise AssertionError("state split size mismatch")
        if (state_sets["train"] & state_sets["development"]
                or state_sets["train"] & state_sets["locked"]
                or state_sets["development"] & state_sets["locked"]):
            raise AssertionError("state leakage across state-disjoint splits")
        if set.union(*state_sets.values()) != set(states):
            raise AssertionError("state split does not cover the full state space")
    family_splits = {}
    for row in rows:
        family_splits.setdefault(row["family_id"], row["family_split"])
        if family_splits[row["family_id"]] != row["family_split"]:
            raise AssertionError("teacher family leaked across family splits")


def iter_jsonl(corpus: dict) -> Iterator[str]:
    for row in corpus["rows"]:
        yield json.dumps(row, sort_keys=True, separators=(",", ":"))


def write_jsonl(corpus: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for line in iter_jsonl(corpus):
            handle.write(line)
            handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=40)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--min-arity", type=int, default=2)
    parser.add_argument("--max-arity", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument("--jsonl", type=Path)
    args = parser.parse_args()
    corpus = generate_corpus(
        family_count=args.families,
        input_dim=args.input_dim,
        output_dim=args.output_dim,
        min_arity=args.min_arity,
        max_arity=args.max_arity,
        seed=args.seed,
    )
    if args.jsonl:
        write_jsonl(corpus, args.jsonl)
    print(json.dumps(corpus["manifest"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
