"""Out-of-grammar compositional Boolean benchmark for CPG-EI.

Teachers emit XORs of two conjunctions. This composition is intentionally absent
from the finite single-operator grammar used by the symbolic baseline. Every
teacher family is still adapted from its own train split; this is not family-OOD
or zero-shot transfer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import random
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from prototype.cpg_ei_early_stopping import run_early_stopping_baseline
from prototype.cpg_ei_compute_accounted_hybrid import (
    derive_train_only_support_features,
    run_support_constrained_hybrid,
)
from prototype.cpg_ei_mixed_operator_discovery import enumerate_rule_hypotheses
from prototype.cpg_ei_relation_operators import RelationRule, evaluate_rule


def generate_compositional_corpus(
    *, family_count: int = 8, input_dim: int = 6, output_dim: int = 4,
    seed: int = 20261114,
) -> dict[str, Any]:
    if isinstance(family_count, bool) or not isinstance(family_count, int) or family_count < 5:
        raise ValueError("family_count must be an integer >= 5")
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 4:
        raise ValueError("input_dim must be an integer >= 4")
    if isinstance(output_dim, bool) or not isinstance(output_dim, int) or output_dim < 1:
        raise ValueError("output_dim must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    states = tuple(itertools.product((0, 1), repeat=input_dim))
    rows: list[dict[str, Any]] = []
    teachers: list[dict[str, Any]] = []
    family_split_counts = {"train": 0, "development": 0, "locked": 0}

    for family_index in range(family_count):
        family_seed = seed + 31_000 + family_index
        rng = random.Random(family_seed)
        family_id = f"composed-teacher-{family_seed}"
        rules = []
        for output_index in range(output_dim):
            selected = rng.sample(range(input_dim), 4)
            left, right = tuple(sorted(selected[:2])), tuple(sorted(selected[2:]))
            rules.append({"operator": "xor_of_conjunctions",
                          "left_support": list(left),
                          "right_support": list(right)})
        teacher_payload = json.dumps(
            {"family_seed": family_seed, "rules": rules},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        teacher_digest = hashlib.sha256(teacher_payload).hexdigest()
        teachers.append({
            "family_id": family_id, "teacher_digest": teacher_digest,
            "family_seed": family_seed, "rules": rules,
        })

        family_split = ("train" if family_index < int(family_count * 0.6)
                        else "development" if family_index < int(family_count * 0.8)
                        else "locked")
        family_split_counts[family_split] += 1
        state_order = list(states)
        random.Random(seed + 700_000 + family_seed).shuffle(state_order)
        train_n, dev_n = len(states) // 2, len(states) // 4
        split_by_state = {}
        for state in state_order[:train_n]:
            split_by_state[state] = "train"
        for state in state_order[train_n:train_n + dev_n]:
            split_by_state[state] = "development"
        for state in state_order[train_n + dev_n:]:
            split_by_state[state] = "locked"

        for state in states:
            target = []
            for rule in rules:
                a, b = rule["left_support"]
                c, d = rule["right_support"]
                target.append((state[a] & state[b]) ^ (state[c] & state[d]))
            rows.append({
                "family_id": family_id, "teacher_digest": teacher_digest,
                "family_split": family_split,
                "state_split": split_by_state[state],
                "state": list(state), "target": target,
            })

    manifest = {
        "dataset_id": "zhouyi-cpg-ei-compositional-ood-v1",
        "generator_version": "1.0.0",
        "seed": seed, "input_dim": input_dim, "output_dim": output_dim,
        "operators": ["xor_of_conjunctions"],
        "family_count": family_count, "states_per_family": len(states),
        "row_count": len(rows), "teacher_rule_count": family_count * output_dim,
        "family_split_counts": family_split_counts,
        "state_split_per_family": {
            "train": len(states) // 2,
            "development": len(states) // 4,
            "locked": len(states) - len(states) // 2 - len(states) // 4,
        },
        "claim_boundary": (
            "Synthetic compositional Boolean functions outside the declared "
            "single-operator discovery grammar. Per-family supervised adaptation "
            "is used; this is not cross-family transfer or language reasoning."
        ),
    }
    canonical = json.dumps(
        {"manifest": manifest, "teachers": teachers, "rows": rows},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    manifest["corpus_sha256"] = hashlib.sha256(canonical).hexdigest()
    return {"manifest": manifest, "teachers": teachers, "rows": rows}


def _state_index(state: Sequence[int]) -> int:
    return int("".join(str(bit) for bit in state), 2)


def _rule_key(rule: RelationRule) -> tuple[Any, ...]:
    return (rule.operator, rule.support, rule.threshold,
            rule.context_index, rule.context_value)


def run_symbolic_baseline(corpus: dict[str, Any]) -> dict[str, Any]:
    """Train-first, development-tie-break symbolic baseline; locked is report-only."""
    manifest = corpus["manifest"]
    input_dim, output_dim = manifest["input_dim"], manifest["output_dim"]
    candidates = tuple(
        (rule, tuple(evaluate_rule(state, rule)
                     for state in itertools.product((0, 1), repeat=input_dim)))
        for rule in enumerate_rule_hypotheses(input_dim)
    )
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)

    family_results = []
    for family_id in sorted(rows_by_family):
        rows = rows_by_family[family_id]
        train = [row for row in rows if row["state_split"] == "train"]
        dev = [row for row in rows if row["state_split"] == "development"]
        locked = [row for row in rows if row["state_split"] == "locked"]
        selected_rules = []
        for output_index in range(output_dim):
            scored = []
            for rule, predictions in candidates:
                train_error = sum(
                    int(predictions[_state_index(row["state"])] != row["target"][output_index])
                    for row in train
                )
                scored.append((train_error, rule, predictions))
            best_train = min(item[0] for item in scored)
            train_minimizers = [item for item in scored if item[0] == best_train]
            best_dev = min(sum(
                int(predictions[_state_index(row["state"])] != row["target"][output_index])
                for row in dev
            ) for _, _, predictions in train_minimizers)
            finalists = [
                (rule, predictions) for _, rule, predictions in train_minimizers
                if sum(int(predictions[_state_index(row["state"])] != row["target"][output_index])
                       for row in dev) == best_dev
            ]
            selected_rules.append(min(finalists, key=lambda item: _rule_key(item[0])))

        bit_correct = exact_correct = 0
        for row in locked:
            prediction = tuple(
                int(predictions[_state_index(row["state"])])
                for _, predictions in selected_rules
            )
            target = tuple(row["target"])
            bit_correct += sum(int(a == b) for a, b in zip(prediction, target))
            exact_correct += int(prediction == target)
        total_bits = len(locked) * output_dim
        family_results.append({
            "family_id": family_id,
            "locked_bit_accuracy": bit_correct / total_bits,
            "locked_exact_state_accuracy": exact_correct / len(locked),
            "selected_rules": [
                {"operator": rule.operator, "support": list(rule.support),
                 "threshold": rule.threshold, "context_index": rule.context_index,
                 "context_value": rule.context_value}
                for rule, _ in selected_rules
            ],
        })

    return {
        "candidate_hypothesis_count": len(candidates),
        "locked_summary": {
            "families": len(family_results),
            "mean_bit_accuracy": statistics.mean(
                row["locked_bit_accuracy"] for row in family_results),
            "mean_exact_state_accuracy": statistics.mean(
                row["locked_exact_state_accuracy"] for row in family_results),
        },
        "family_results": family_results,
        "selection_protocol": (
            "minimum train error; development error breaks train ties; "
            "locked states are report-only"
        ),
    }


def run_compositional_ood_benchmark(
    *, seeds: Sequence[int] = (20261114, 20261115, 20261116),
    family_count: int = 8, input_dim: int = 6, output_dim: int = 4,
    max_epochs: int = 120, patience: int = 15,
) -> dict[str, Any]:
    selected_seeds = tuple(seeds)
    if len(selected_seeds) < 2 or len(set(selected_seeds)) != len(selected_seeds):
        raise ValueError("at least two unique seeds are required")
    seed_results = []
    for seed in selected_seeds:
        corpus = generate_compositional_corpus(
            family_count=family_count, input_dim=input_dim,
            output_dim=output_dim, seed=seed,
        )
        symbolic_started = time.perf_counter()
        symbolic = run_symbolic_baseline(corpus)
        symbolic_seconds = time.perf_counter() - symbolic_started

        full_started = time.perf_counter()
        full = run_early_stopping_baseline(
            corpus, max_epochs=max_epochs, patience=patience,
            min_delta=1e-5, learning_rate=0.1, l2=1e-4,
        )
        full_seconds = time.perf_counter() - full_started

        hybrid_started = time.perf_counter()
        hybrid = run_support_constrained_hybrid(
            corpus, max_epochs=max_epochs, patience=patience,
            min_delta=1e-5, learning_rate=0.1, l2=1e-4,
        )
        hybrid_seconds = time.perf_counter() - hybrid_started

        seed_results.append({
            "seed": seed, "corpus_sha256": corpus["manifest"]["corpus_sha256"],
            "rows": corpus["manifest"]["row_count"],
            "symbolic": {
                "locked": symbolic["locked_summary"],
                "wall_seconds": symbolic_seconds,
            },
            "full_polynomial": {
                "locked": full["locked_summary"],
                "wall_seconds": full_seconds,
            },
            "symbolic_support_hybrid": {
                "locked": hybrid["locked_summary"],
                "wall_seconds": hybrid_seconds,
            },
            "symbolic_selection": symbolic["selection_protocol"],
            "hybrid_feature_selection": hybrid["model"]["feature_selection"],
        })

    def aggregate(method: str, metric: str) -> dict[str, float]:
        values = [float(item[method]["locked"][metric]) for item in seed_results]
        return {
            "mean_across_seeds": statistics.mean(values),
            "sample_std_across_seeds": statistics.stdev(values),
            "min_across_seeds": min(values), "max_across_seeds": max(values),
        }

    return {
        "benchmark_id": "zhouyi-cpg-ei-compositional-ood-v1",
        "dataset": {
            "families_per_seed": family_count, "input_dim": input_dim,
            "output_dim": output_dim, "states_per_family": 2 ** input_dim,
            "seeds": list(selected_seeds),
            "total_teacher_families": family_count * len(selected_seeds),
            "total_rows": family_count * (2 ** input_dim) * len(selected_seeds),
            "target_function": "AND(a,b) XOR AND(c,d), four distinct input variables",
        },
        "protocol": (
            "Each teacher output is a composition of two conjunctions under XOR. "
            "The symbolic candidate grammar contains only single declared operators "
            "and therefore does not contain this composition. All methods adapt "
            "independently to each family's train split; development selects ties "
            "or checkpoints; locked states are report-only. This is operator-grammar "
            "OOD, not held-out-family zero-shot transfer."
        ),
        "results": {
            method: {
                "locked_bit_accuracy": aggregate(method, "mean_bit_accuracy"),
                "locked_exact_state_accuracy": aggregate(method, "mean_exact_state_accuracy"),
            }
            for method in ("symbolic", "full_polynomial", "symbolic_support_hybrid")
        },
        "seed_results": seed_results,
        "claim_boundary": (
            "Synthetic Boolean composition benchmark only. It does not establish "
            "Yi-Xue understanding, natural-language reasoning, causal discovery, "
            "open-world intelligence, or Transformer superiority."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+",
                        default=[20261114, 20261115, 20261116])
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=6)
    parser.add_argument("--output-dim", type=int, default=4)
    parser.add_argument("--max-epochs", type=int, default=120)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_compositional_ood_benchmark(
        seeds=args.seeds, family_count=args.families,
        input_dim=args.input_dim, output_dim=args.output_dim,
        max_epochs=args.max_epochs, patience=args.patience,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
