"""Deterministic synthetic rule-family data for N0.10.

The generator creates role-conditioned candidate pools whose unique target is
selected by a latent three-way parity rule plus a small unary utility tie-break.
Train/dev use even parity; locked_test uses odd parity, making the rule-family
shift explicit rather than silently mixing it into an IID split.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from pathlib import Path
from typing import Any

GENERATOR_SCHEMA = "zhouyi-ai.n010-synthetic-rule-families-v1"
FEATURE_DIM = 4
ROLE_NAMES = ("r0", "r1", "r2")


def _validate_probability(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a finite probability in [0, 1]")


def _make_record(rng: random.Random, example_id: str, split: str,
                 rule_family: str, candidates_per_role: int,
                 noise_rate: float, missing_rate: float) -> dict[str, Any]:
    pools: list[list[dict[str, Any]]] = []
    latent_by_id: dict[str, int] = {}
    utility_by_id: dict[str, float] = {}
    for role_index, role in enumerate(ROLE_NAMES):
        # Every pool contains both latent signs, so either parity family has
        # at least one feasible complete assignment.
        signs = [1, -1] + [rng.choice((-1, 1)) for _ in range(candidates_per_role - 2)]
        rng.shuffle(signs)
        pool = []
        for candidate_index, latent_sign in enumerate(signs):
            node_id = f"{example_id}-{role}-c{candidate_index}"
            utility = rng.random()
            missing = rng.random() < missing_rate
            flipped = rng.random() < noise_rate
            observed_sign = 0.0 if missing else float(-latent_sign if flipped else latent_sign)
            quality = 0.0 if missing else (0.5 if flipped else 1.0)
            evidence_ids = [] if missing else [f"ev-{node_id}"]
            node = {
                "node_id": node_id,
                "node_type": role,
                "features": [observed_sign, utility, quality, 1.0 if missing else 0.0],
                "tags": ["candidate"],
                "evidence_ids": evidence_ids,
            }
            pool.append(node)
            latent_by_id[node_id] = latent_sign
            utility_by_id[node_id] = utility
        pools.append(pool)

    desired_parity = 1 if rule_family == "parity-even" else -1
    feasible = []
    for assignment in itertools.product(*pools):
        parity = math.prod(latent_by_id[node["node_id"]] for node in assignment)
        if parity == desired_parity:
            utility = math.fsum(utility_by_id[node["node_id"]] for node in assignment)
            ids = tuple(node["node_id"] for node in assignment)
            feasible.append((utility, ids))
    if not feasible:
        raise AssertionError("both-sign candidate pools must admit either parity")
    target_ids = max(feasible, key=lambda row: (row[0], row[1]))[1]
    return {
        "id": example_id,
        "split": split,
        "rule_family": rule_family,
        "nodes": [node for pool in pools for node in pool],
        "target_ids": list(target_ids),
    }


def generate_dataset(output_path: str | Path, *, seed: int = 0,
                     train_count: int = 256, dev_count: int = 64,
                     locked_test_count: int = 64, candidates_per_role: int = 3,
                     noise_rate: float = 0.05, missing_rate: float = 0.05) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    for name, count in (("train_count", train_count), ("dev_count", dev_count),
                        ("locked_test_count", locked_test_count)):
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(f"{name} must be a positive integer")
    if isinstance(candidates_per_role, bool) or not isinstance(candidates_per_role, int) or candidates_per_role < 2:
        raise ValueError("candidates_per_role must be an integer >= 2")
    _validate_probability("noise_rate", noise_rate)
    _validate_probability("missing_rate", missing_rate)

    rng = random.Random(seed)
    rows = []
    specs = (
        ("train", "parity-even", train_count, "train"),
        ("dev", "parity-even", dev_count, "dev"),
        ("locked_test", "parity-odd", locked_test_count, "locked-test"),
    )
    for split, family, count, prefix in specs:
        for index in range(count):
            rows.append(_make_record(
                rng, f"{prefix}-{index:06d}", split, family,
                candidates_per_role, noise_rate, missing_rate,
            ))
    encoded = "".join(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False) + "\n"
                      for row in rows).encode("utf-8")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    manifest = {
        "schema": GENERATOR_SCHEMA,
        "dataset_sha256": hashlib.sha256(encoded).hexdigest(),
        "seed": seed,
        "feature_dim": FEATURE_DIM,
        "roles": list(ROLE_NAMES),
        "counts": {"train": train_count, "dev": dev_count,
                   "locked_test": locked_test_count},
        "rule_families_by_split": {
            "train": ["parity-even"], "dev": ["parity-even"],
            "locked_test": ["parity-odd"],
        },
        "candidates_per_role": candidates_per_role,
        "noise_rate": noise_rate,
        "missing_rate": missing_rate,
        "target_rule": "latent_sign_product equals +1 for even, -1 for odd; utility breaks ties",
        "feature_layout": ["observed_sign", "unary_utility", "evidence_quality", "missing_indicator"],
        "split_policy": "locked_test rule family is disjoint from train and dev",
    }
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2,
                                        ensure_ascii=False, allow_nan=False) + "\n",
                             encoding="utf-8")
    return manifest



def _make_compositional_record(rng: random.Random, example_id: str, split: str,
                               rule_family: str, candidates_per_role: int,
                               noise_rate: float, missing_rate: float) -> dict[str, Any]:
    pools: list[list[dict[str, Any]]] = []
    latent: dict[str, tuple[float, float]] = {}
    for role_index, role in enumerate(ROLE_NAMES):
        pool = []
        for candidate_index in range(candidates_per_role):
            node_id = f"{example_id}-{role}-c{candidate_index}"
            x, y = rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)
            missing = rng.random() < missing_rate
            observed_x = 0.0 if missing else x + rng.uniform(-noise_rate, noise_rate)
            observed_y = 0.0 if missing else y + rng.uniform(-noise_rate, noise_rate)
            node = {
                "node_id": node_id, "node_type": role,
                "features": [observed_x, observed_y, 0.0 if missing else 1.0,
                             1.0 if missing else 0.0],
                "tags": ["candidate"],
                "evidence_ids": [] if missing else [f"ev-{node_id}"],
            }
            pool.append(node)
            latent[node_id] = (x, y)
        pools.append(pool)

    # A cyclic bilinear composition, not a parity/sign rule. The held-out
    # family reverses the cycle direction to test structural transfer.
    def relation_score(assignment):
        values = [latent[node["node_id"]] for node in assignment]
        if rule_family == "cycle-forward":
            return math.fsum((values[i][0] * values[(i + 1) % 3][1])
                             for i in range(3))
        return math.fsum((values[i][0] * values[(i - 1) % 3][1])
                         for i in range(3))

    scored = [(relation_score(row), tuple(node["node_id"] for node in row))
              for row in itertools.product(*pools)]
    target = max(scored, key=lambda item: (item[0], item[1]))[1]
    return {
        "id": example_id, "split": split, "rule_family": rule_family,
        "nodes": [node for pool in pools for node in pool],
        "target_ids": list(target),
    }


def generate_compositional_dataset(output_path: str | Path, *, seed: int = 0,
                                   train_count: int = 256, dev_count: int = 64,
                                   locked_test_count: int = 64,
                                   candidates_per_role: int = 3,
                                   noise_rate: float = 0.02,
                                   missing_rate: float = 0.02) -> dict[str, Any]:
    """Generate a non-parity cyclic-composition benchmark with family OOD."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    for name, count in (("train_count", train_count), ("dev_count", dev_count),
                        ("locked_test_count", locked_test_count)):
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(f"{name} must be a positive integer")
    if isinstance(candidates_per_role, bool) or not isinstance(candidates_per_role, int) or candidates_per_role < 2:
        raise ValueError("candidates_per_role must be an integer >= 2")
    _validate_probability("noise_rate", noise_rate)
    _validate_probability("missing_rate", missing_rate)

    rng = random.Random(seed)
    rows = []
    for split, family, count, prefix in (
        ("train", "cycle-forward", train_count, "cycle-train"),
        ("dev", "cycle-forward", dev_count, "cycle-dev"),
        ("locked_test", "cycle-reverse", locked_test_count, "cycle-locked"),
    ):
        for index in range(count):
            rows.append(_make_compositional_record(
                rng, f"{prefix}-{index:06d}", split, family,
                candidates_per_role, noise_rate, missing_rate,
            ))
    encoded = "".join(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False) + "\\n"
                      for row in rows).encode("utf-8")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    manifest = {
        "schema": GENERATOR_SCHEMA,
        "dataset_sha256": hashlib.sha256(encoded).hexdigest(),
        "seed": seed, "feature_dim": FEATURE_DIM, "roles": list(ROLE_NAMES),
        "counts": {"train": train_count, "dev": dev_count,
                   "locked_test": locked_test_count},
        "rule_families_by_split": {
            "train": ["cycle-forward"], "dev": ["cycle-forward"],
            "locked_test": ["cycle-reverse"],
        },
        "candidates_per_role": candidates_per_role,
        "noise_rate": noise_rate, "missing_rate": missing_rate,
        "target_rule": "maximize cyclic bilinear sum x_i*y_(i+1); locked test reverses cycle direction",
        "feature_layout": ["x", "y", "evidence_quality", "missing_indicator"],
        "split_policy": "locked-test cycle direction is disjoint from train and dev",
    }
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic N0.10 rule-family JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--train-count", type=int, default=256)
    parser.add_argument("--dev-count", type=int, default=64)
    parser.add_argument("--locked-test-count", type=int, default=64)
    parser.add_argument("--candidates-per-role", type=int, default=3)
    parser.add_argument("--noise-rate", type=float, default=0.05)
    parser.add_argument("--missing-rate", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(generate_dataset(
        args.output, seed=args.seed, train_count=args.train_count,
        dev_count=args.dev_count, locked_test_count=args.locked_test_count,
        candidates_per_role=args.candidates_per_role,
        noise_rate=args.noise_rate, missing_rate=args.missing_rate,
    ), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
