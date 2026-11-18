"""Few-shot finite-grammar induction on genuinely held-out teacher families.

Candidate selection sees only labeled support examples. Validation/test query
labels remain in the separate evaluator view. This is symbolic few-shot transfer,
not a learned meta-model or natural-language reasoning system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.cpg_ei_heldout_family_protocol import build_heldout_family_protocol
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    _truth_mask, enumerate_rule_hypotheses,
)
from prototype.cpg_ei_relation_operators import evaluate_rule, rule_manifest


def _state_index(state: list[int] | tuple[int, ...]) -> int:
    return int("".join(str(bit) for bit in state), 2)


def _predict_episode(episode: dict, target_record: dict,
                     candidates: tuple, candidate_masks: tuple[int, ...],
                     input_dim: int) -> dict[str, Any]:
    support = episode["support"]
    query_states = episode["query_states"]
    query_targets = target_record["query_targets"]
    if len(query_states) != len(query_targets):
        raise ValueError("query states and evaluator targets must have equal lengths")
    output_dim = len(support[0]["target"])
    support_mask = 0
    target_masks = [0] * output_dim
    positive_counts = [0] * output_dim
    for row in support:
        bit_index = _state_index(row["state"])
        support_mask |= 1 << bit_index
        for output_index, label in enumerate(row["target"]):
            if label:
                target_masks[output_index] |= 1 << bit_index
                positive_counts[output_index] += 1

    selected_indices = []
    symbolic_predictions = [[0] * output_dim for _ in query_states]
    majority_predictions = [[0] * output_dim for _ in query_states]
    tie_counts = []
    for output_index in range(output_dim):
        scores = [
            ((prediction_mask ^ target_masks[output_index]) & support_mask).bit_count()
            for prediction_mask in candidate_masks
        ]
        best_score = min(scores)
        finalists = [index for index, score in enumerate(scores) if score == best_score]
        selected_index = finalists[0]
        selected_indices.append(selected_index)
        tie_counts.append(len(finalists))
        majority = int(positive_counts[output_index] * 2 > len(support))
        for query_index, state in enumerate(query_states):
            symbolic_predictions[query_index][output_index] = evaluate_rule(
                state, candidates[selected_index]
            )
            majority_predictions[query_index][output_index] = majority

    def metrics(predictions: list[list[int]]) -> dict[str, float]:
        bit_total = len(query_states) * output_dim
        bit_correct = sum(
            int(predictions[i][j] == query_targets[i][j])
            for i in range(len(query_states)) for j in range(output_dim)
        )
        exact_correct = sum(
            int(tuple(predictions[i]) == tuple(query_targets[i]))
            for i in range(len(query_states))
        )
        return {
            "bit_accuracy": bit_correct / bit_total,
            "exact_state_accuracy": exact_correct / len(query_states),
        }

    selected_specs = [
        rule_manifest(candidates[index], input_dim) for index in selected_indices
    ]
    return {
        "task_id": episode["task_id"],
        "symbolic": metrics(symbolic_predictions),
        "majority": metrics(majority_predictions),
        "mean_candidate_tie_count": sum(tie_counts) / len(tie_counts),
        "selected_rule_digest": hashlib.sha256(json.dumps(
            selected_specs, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }


def _summarize(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {"families": 0}
    result: dict[str, float] = {"families": float(len(rows))}
    for method in ("symbolic", "majority"):
        for metric in ("bit_accuracy", "exact_state_accuracy"):
            values = sorted(row[method][metric] for row in rows)
            result[f"{method}_{metric}_mean"] = sum(values) / len(values)
            result[f"{method}_{metric}_median"] = values[len(values) // 2]
            result[f"{method}_{metric}_worst_family"] = values[0]
    result["mean_candidate_tie_count"] = sum(
        row["mean_candidate_tie_count"] for row in rows
    ) / len(rows)
    return result


def evaluate_protocol_views(protocol: dict, candidates: tuple,
                            candidate_masks: tuple[int, ...],
                            input_dim: int) -> dict[str, Any]:
    learner = protocol["learner_view"]
    evaluator = protocol["evaluator_view"]
    results = {}
    for split, episodes_key, targets_key in (
        ("validation", "validation_episodes", "validation_query_targets"),
        ("test", "test_episodes", "test_query_targets"),
    ):
        target_by_id = {
            row["task_id"]: row for row in evaluator[targets_key]
        }
        rows = [
            _predict_episode(
                episode, target_by_id[episode["task_id"]],
                candidates, candidate_masks, input_dim,
            )
            for episode in learner[episodes_key]
        ]
        results[split] = {
            "summary": _summarize(rows),
            "selection_digest": hashlib.sha256(json.dumps(
                [(row["task_id"], row["selected_rule_digest"]) for row in rows],
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest(),
            "family_results": rows,
        }
    return results


def run_fewshot_benchmark(*, family_count: int = 1600, input_dim: int = 8,
                          output_dim: int = 8, seeds: tuple[int, ...] = (20261114,),
                          support_sizes: tuple[int, ...] = (16, 32, 64)) -> dict[str, Any]:
    if not seeds or not support_sizes:
        raise ValueError("seeds and support_sizes must be non-empty")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
           for value in support_sizes):
        raise ValueError("support sizes must be positive integers")
    candidates = enumerate_rule_hypotheses(input_dim)
    candidate_masks = tuple(_truth_mask(rule, input_dim) for rule in candidates)
    all_results = []
    for seed in seeds:
        corpus = generate_mixed_corpus(
            family_count=family_count, input_dim=input_dim,
            output_dim=output_dim, seed=seed,
        )
        for support_size in support_sizes:
            started = time.perf_counter()
            protocol = build_heldout_family_protocol(
                corpus, support_size=support_size, seed=seed + 1,
            )
            evaluated = evaluate_protocol_views(
                protocol, candidates, candidate_masks, input_dim,
            )
            evaluation_seconds = time.perf_counter() - started
            all_results.append({
                "seed": seed,
                "corpus_sha256": corpus["manifest"]["corpus_sha256"],
                "support_size": support_size,
                "family_count": family_count,
                "candidate_count": len(candidates),
                "evaluation_wall_seconds": evaluation_seconds,
                "validation": evaluated["validation"],
                "test": evaluated["test"],
            })
    aggregate_results = []
    for support_size in support_sizes:
        for split in ("validation", "test"):
            selected = [
                row for row in all_results if row["support_size"] == support_size
            ]
            method_metrics = {}
            for method in ("symbolic", "majority"):
                method_metrics[method] = {}
                for metric in ("bit_accuracy", "exact_state_accuracy"):
                    values = [
                        family[method][metric]
                        for row in selected
                        for family in row[split]["family_results"]
                    ]
                    method_metrics[method][metric] = {
                        "families_across_seeds": len(values),
                        "mean": statistics.mean(values),
                        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
                        "median": statistics.median(values),
                        "worst_family": min(values),
                    }
            aggregate_results.append({
                "support_size": support_size,
                "split": split,
                "methods": method_metrics,
            })

    return {
        "benchmark_id": "zhouyi-cpg-ei-heldout-family-fewshot-symbolic-v1",
        "dataset": {
            "family_count_per_seed": family_count,
            "total_teacher_families_across_seeds": family_count * len(seeds),
            "input_dim": input_dim,
            "output_dim": output_dim,
            "states_per_family": 2 ** input_dim,
            "operators": 7,
            "seeds": list(seeds),
            "support_sizes": list(support_sizes),
            "timing_scope": "protocol construction and query evaluation; corpus generation and candidate precomputation excluded",
        },
        "candidate_selection": (
            "Minimum support-state error over the declared finite operator grammar; "
            "ties resolved by deterministic candidate enumeration order. Query labels "
            "are not read during candidate selection."
        ),
        "protocol": (
            "Disjoint teacher-family train/validation/test groups. Validation and test "
            "families provide labeled support states from their within-family train split; "
            "query states come from development and locked splits respectively. "
            "This is few-shot family transfer, not zero-shot transfer."
        ),
        "baseline": "Per-output majority prediction from the same support examples.",
        "claim_boundary": (
            "Finite symbolic grammar few-shot induction on synthetic Boolean relations. "
            "Not a learned meta-model, open-world discovery, Yi-Xue understanding, "
            "natural-language reasoning, or a Transformer comparison."
        ),
        "results": all_results,
        "aggregate_results": aggregate_results,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=1600)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261114])
    parser.add_argument("--support-sizes", type=int, nargs="+", default=[16, 32, 64])
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = run_fewshot_benchmark(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seeds=tuple(args.seeds),
        support_sizes=tuple(args.support_sizes),
    )
    write_report(report, args.json)
    print(json.dumps({
        "benchmark_id": report["benchmark_id"],
        "runs": len(report["results"]),
        "test_summary": [
            {"seed": row["seed"], "support_size": row["support_size"],
             **row["test"]["summary"]}
            for row in report["results"]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
