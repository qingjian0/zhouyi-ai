"""Mixed-operator relational corpus for CPG-EI.

Four hundred independent teachers each define eight output rules over all 8-bit states.
The corpus is synthetic and deterministic; it is a benchmark fixture, not evidence
of natural-language or classical-analogy reasoning.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import Counter
from pathlib import Path

from prototype.cpg_ei_relation_operators import (
    OPERATORS, RelationRule, evaluate_rule, rule_manifest,
)


def make_rule(rng: random.Random, operator: str, input_dim: int) -> RelationRule:
    if operator == "implies":
        arity = 2
    else:
        arity = rng.randint(2, min(6, input_dim - (operator == "conditional_xor")))
    support = tuple(sorted(rng.sample(range(input_dim), arity)))
    if operator == "implies":
        support = tuple(rng.sample(support, len(support)))
    if operator == "threshold":
        return RelationRule(operator, support, threshold=rng.randint(1, arity))
    if operator == "conditional_xor":
        context_candidates = [i for i in range(input_dim) if i not in support]
        return RelationRule(
            operator, support, context_index=rng.choice(context_candidates),
            context_value=rng.randint(0, 1),
        )
    return RelationRule(operator, support)


def _split_families(family_count: int, seed: int) -> dict[int, str]:
    order = list(range(family_count))
    random.Random(seed + 500_000).shuffle(order)
    train = int(family_count * 0.6)
    development = int(family_count * 0.2)
    result = {index: "train" for index in order[:train]}
    result.update({index: "development" for index in order[train:train + development]})
    result.update({index: "locked" for index in order[train + development:]})
    return result


def generate_mixed_corpus(
    *, family_count: int = 40, input_dim: int = 8, output_dim: int = 8,
    seed: int = 20261114,
) -> dict:
    if isinstance(family_count, bool) or not isinstance(family_count, int) or family_count < 5:
        raise ValueError("family_count must be an integer >= 5")
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 3:
        raise ValueError("input_dim must be an integer >= 3")
    if isinstance(output_dim, bool) or not isinstance(output_dim, int) or output_dim < 1:
        raise ValueError("output_dim must be a positive integer")

    states = tuple(itertools.product((0, 1), repeat=input_dim))
    family_splits = _split_families(family_count, seed)
    teachers = []
    rows = []
    operator_counts = Counter()
    arity_counts = Counter()
    family_split_counts = Counter()

    for family_index in range(family_count):
        family_seed = seed + 1000 + family_index
        rng = random.Random(family_seed)
        rules = []
        for output_index in range(output_dim):
            # Round-robin assignment prevents rare operators disappearing by chance.
            operator = OPERATORS[(family_index * output_dim + output_index) % len(OPERATORS)]
            rule = make_rule(rng, operator, input_dim)
            rule.validate(input_dim)
            rules.append(rule)
            operator_counts[operator] += 1
            arity_counts[str(len(rule.support))] += 1

        rule_specs = [rule_manifest(rule, input_dim) for rule in rules]
        digest_payload = json.dumps(
            {"seed": family_seed, "rules": rule_specs},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(digest_payload).hexdigest()
        family_id = f"mixed-teacher-{family_seed}"
        teachers.append({
            "family_id": family_id, "family_seed": family_seed,
            "teacher_digest": digest, "rules": rule_specs,
        })
        family_split = family_splits[family_index]
        family_split_counts[family_split] += 1

        state_order = list(states)
        random.Random(seed + 700_000 + family_seed).shuffle(state_order)
        split_by_state = {}
        n = len(states)
        train_n, dev_n = n // 2, n // 4
        for state in state_order[:train_n]:
            split_by_state[state] = "train"
        for state in state_order[train_n:train_n + dev_n]:
            split_by_state[state] = "development"
        for state in state_order[train_n + dev_n:]:
            split_by_state[state] = "locked"

        for state in states:
            target = [evaluate_rule(state, rule) for rule in rules]
            rows.append({
                "family_id": family_id,
                "teacher_digest": digest,
                "family_split": family_split,
                "state_split": split_by_state[state],
                "state": list(state),
                "target": target,
            })

    manifest = {
        "dataset_id": "zhouyi-cpg-ei-mixed-operators-v1",
        "generator_version": "1.0.0",
        "seed": seed,
        "input_dim": input_dim,
        "output_dim": output_dim,
        "operators": list(OPERATORS),
        "family_count": family_count,
        "states_per_family": len(states),
        "row_count": len(rows),
        "teacher_rule_count": family_count * output_dim,
        "operator_rule_counts": dict(sorted(operator_counts.items())),
        "arity_rule_counts": dict(sorted(arity_counts.items())),
        "family_split_counts": dict(sorted(family_split_counts.items())),
        "state_split_per_family": {
            "train": len(states) // 2,
            "development": len(states) // 4,
            "locked": len(states) - len(states) // 2 - len(states) // 4,
        },
        "teacher_digests": [teacher["teacher_digest"] for teacher in teachers],
        "claim_boundary": (
            "Synthetic mixed Boolean-operator benchmark. It does not establish "
            "causal discovery, natural-language reasoning, classical-analogy "
            "understanding, or superiority to Transformer models."
        ),
    }
    canonical = json.dumps(
        {"manifest": manifest, "teachers": teachers, "rows": rows},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    manifest["corpus_sha256"] = hashlib.sha256(canonical).hexdigest()
    _validate(manifest, teachers, rows, states)
    return {"manifest": manifest, "teachers": teachers, "rows": rows}


def _validate(manifest: dict, teachers: list[dict], rows: list[dict], states: tuple) -> None:
    if len(rows) != manifest["family_count"] * len(states):
        raise AssertionError("row count mismatch")
    if len({t["teacher_digest"] for t in teachers}) != len(teachers):
        raise AssertionError("duplicate teacher digest")
    by_family = {}
    for row in rows:
        by_family.setdefault(row["family_id"], []).append(row)
        if len(row["state"]) != manifest["input_dim"] or len(row["target"]) != manifest["output_dim"]:
            raise AssertionError("row dimensions mismatch")
    expected = manifest["state_split_per_family"]
    for family_rows in by_family.values():
        splits = {
            split: {tuple(row["state"]) for row in family_rows if row["state_split"] == split}
            for split in ("train", "development", "locked")
        }
        if any(len(splits[key]) != expected[key] for key in expected):
            raise AssertionError("state split cardinality mismatch")
        if (splits["train"] & splits["development"] or splits["train"] & splits["locked"]
                or splits["development"] & splits["locked"]):
            raise AssertionError("state leakage")
        if set.union(*splits.values()) != set(states):
            raise AssertionError("state coverage mismatch")
    if set(by_family) != {teacher["family_id"] for teacher in teachers}:
        raise AssertionError("teacher coverage mismatch")


def write_jsonl(corpus: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for row in corpus["rows"]:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=40)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--jsonl", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    if args.jsonl:
        write_jsonl(corpus, args.jsonl)
    print(json.dumps(corpus["manifest"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
