"""Empirical-Bayes meta-learning baseline for held-out Boolean rule families.

The meta-training split estimates a smoothed prior over finite relation rules.
Validation families select the prior-strength hyperparameter; locked test-family
query labels are never used for prior fitting or hyperparameter selection.
This is a symbolic empirical-Bayes baseline, not a neural meta-learner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any, Sequence

from prototype.cpg_ei_heldout_family_protocol import build_heldout_family_protocol
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    _truth_mask,
    enumerate_rule_hypotheses,
)
from prototype.cpg_ei_relation_operators import evaluate_rule, rule_manifest


DEFAULT_ALPHA_GRID = (0.0, 0.01, 0.03, 0.1, 0.3, 1.0)


def _state_index(state: Sequence[int]) -> int:
    if not state or any(bit not in (0, 1) for bit in state):
        raise ValueError("state must contain only binary values")
    return int("".join(str(bit) for bit in state), 2)


def _observation_masks(
    states: Sequence[Sequence[int]], targets: Sequence[Sequence[int]], output_dim: int
) -> tuple[int, list[int]]:
    if len(states) != len(targets) or not states:
        raise ValueError("observations must contain matching non-empty states and targets")
    observed = 0
    labels = [0] * output_dim
    for state, target in zip(states, targets):
        if len(target) != output_dim or any(bit not in (0, 1) for bit in target):
            raise ValueError("target width or values are invalid")
        index = _state_index(state)
        bit = 1 << index
        if observed & bit:
            raise ValueError("duplicate state in an episode's observations")
        observed |= bit
        for output_index, value in enumerate(target):
            if value:
                labels[output_index] |= bit
    return observed, labels


def learn_candidate_prior(
    meta_train_episodes: Sequence[dict],
    candidate_masks: Sequence[int],
    input_dim: int,
    *,
    smoothing: float = 1.0,
) -> tuple[float, ...]:
    """Estimate a candidate-rule prior from meta-train support + development labels."""
    if not meta_train_episodes or not candidate_masks:
        raise ValueError("meta-training episodes and candidate masks must be non-empty")
    if not math.isfinite(smoothing) or smoothing <= 0:
        raise ValueError("smoothing must be finite and positive")
    counts = [0.0] * len(candidate_masks)
    observations = 0
    for episode in meta_train_episodes:
        support = episode["support"]
        query_states = episode["query_states"]
        query_targets = episode["meta_train_query_targets"]
        states = [row["state"] for row in support] + list(query_states)
        targets = [row["target"] for row in support] + list(query_targets)
        output_dim = len(targets[0])
        observed_mask, target_masks = _observation_masks(states, targets, output_dim)
        for target_mask in target_masks:
            errors = [
                ((candidate_mask ^ target_mask) & observed_mask).bit_count()
                for candidate_mask in candidate_masks
            ]
            best_error = min(errors)
            winners = [i for i, error in enumerate(errors) if error == best_error]
            weight = 1.0 / len(winners)
            for index in winners:
                counts[index] += weight
            observations += 1
    denominator = sum(counts) + smoothing * len(counts)
    prior = tuple((count + smoothing) / denominator for count in counts)
    if not math.isclose(sum(prior), 1.0, rel_tol=1e-10, abs_tol=1e-10):
        raise AssertionError("candidate prior failed normalization")
    return prior


def _select_candidate_indices(
    episode: dict,
    candidate_masks: Sequence[int],
    log_prior: Sequence[float],
    alpha: float,
    input_dim: int,
) -> tuple[list[int], list[int]]:
    support = episode["support"]
    output_dim = len(support[0]["target"])
    observed_mask, target_masks = _observation_masks(
        [row["state"] for row in support],
        [row["target"] for row in support],
        output_dim,
    )
    selected: list[int] = []
    positive_counts = [
        sum(row["target"][j] for row in support) for j in range(output_dim)
    ]
    for target_mask in target_masks:
        errors = [
            ((candidate_mask ^ target_mask) & observed_mask).bit_count()
            for candidate_mask in candidate_masks
        ]
        # alpha=0 reproduces deterministic finite-grammar selection exactly.
        best_index = min(
            range(len(candidate_masks)),
            key=lambda i: (errors[i] - alpha * log_prior[i], i),
        )
        selected.append(best_index)
    return selected, positive_counts


def _evaluate_split(
    episodes: Sequence[dict],
    evaluator_targets: Sequence[dict],
    candidates: Sequence,
    candidate_masks: Sequence[int],
    prior: Sequence[float],
    alpha: float,
    input_dim: int,
) -> dict[str, Any]:
    targets_by_id = {row["task_id"]: row["query_targets"] for row in evaluator_targets}
    family_rows = []
    for episode in episodes:
        task_id = episode["task_id"]
        if task_id not in targets_by_id:
            raise ValueError("evaluator target missing for task")
        query_targets = targets_by_id[task_id]
        query_states = episode["query_states"]
        if len(query_states) != len(query_targets):
            raise ValueError("query states and evaluator targets have different lengths")
        selected, positive_counts = _select_candidate_indices(
            episode, candidate_masks, tuple(math.log(p) for p in prior), alpha, input_dim
        )
        output_dim = len(selected)
        symbolic_predictions = [
            [evaluate_rule(state, candidates[selected[j]]) for j in range(output_dim)]
            for state in query_states
        ]
        majority_predictions = [
            [int(positive_counts[j] * 2 > len(episode["support"])) for j in range(output_dim)]
            for _ in query_states
        ]

        def metrics(predictions: list[list[int]]) -> dict[str, float]:
            bit_total = len(query_states) * output_dim
            bit_correct = sum(
                int(predictions[i][j] == query_targets[i][j])
                for i in range(len(query_states))
                for j in range(output_dim)
            )
            exact_correct = sum(
                int(tuple(predictions[i]) == tuple(query_targets[i]))
                for i in range(len(query_states))
            )
            return {
                "bit_accuracy": bit_correct / bit_total,
                "exact_state_accuracy": exact_correct / len(query_states),
            }

        manifests = [
            rule_manifest(candidates[index], input_dim) for index in selected
        ]
        family_rows.append({
            "task_id": task_id,
            "empirical_bayes": metrics(symbolic_predictions),
            "majority": metrics(majority_predictions),
            "selected_rule_digest": hashlib.sha256(json.dumps(
                manifests, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest(),
        })
    return {"summary": _summarize(family_rows), "family_results": family_rows}


def _summarize(rows: Sequence[dict]) -> dict[str, float]:
    if not rows:
        return {"families": 0.0}
    summary: dict[str, float] = {"families": float(len(rows))}
    for method in ("empirical_bayes", "majority"):
        for metric in ("bit_accuracy", "exact_state_accuracy"):
            values = [row[method][metric] for row in rows]
            summary[f"{method}_{metric}_mean"] = statistics.mean(values)
            summary[f"{method}_{metric}_median"] = statistics.median(values)
            summary[f"{method}_{metric}_worst_family"] = min(values)
    return summary


def _choose_alpha(validation_grid: Sequence[dict]) -> dict:
    # Validation query labels select alpha; locked test labels are not consulted.
    return max(
        validation_grid,
        key=lambda row: (
            row["summary"]["empirical_bayes_bit_accuracy_mean"],
            row["summary"]["empirical_bayes_exact_state_accuracy_mean"],
            -row["alpha"],
        ),
    )


def run_meta_benchmark(
    *,
    family_count: int = 1600,
    input_dim: int = 8,
    output_dim: int = 8,
    seeds: tuple[int, ...] = (20261114, 20261115, 20261116),
    support_sizes: tuple[int, ...] = (16, 32, 64),
    alpha_grid: tuple[float, ...] = DEFAULT_ALPHA_GRID,
    smoothing: float = 1.0,
) -> dict[str, Any]:
    if not seeds or not support_sizes or not alpha_grid:
        raise ValueError("seeds, support sizes, and alpha grid must be non-empty")
    if any(not math.isfinite(a) or a < 0 for a in alpha_grid):
        raise ValueError("alpha values must be finite and non-negative")
    candidates = enumerate_rule_hypotheses(input_dim)
    candidate_masks = tuple(_truth_mask(rule, input_dim) for rule in candidates)
    results = []
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
            learner = protocol["learner_view"]
            evaluator = protocol["evaluator_view"]
            prior = learn_candidate_prior(
                learner["meta_train_episodes"], candidate_masks, input_dim,
                smoothing=smoothing,
            )
            prior_digest = hashlib.sha256(json.dumps(
                [round(value, 16) for value in prior], separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            validation_grid = []
            for alpha in alpha_grid:
                evaluated = _evaluate_split(
                    learner["validation_episodes"],
                    evaluator["validation_query_targets"],
                    candidates, candidate_masks, prior, alpha, input_dim,
                )
                validation_grid.append({
                    "alpha": alpha,
                    "summary": evaluated["summary"],
                })
            chosen = _choose_alpha(validation_grid)
            test = _evaluate_split(
                learner["test_episodes"], evaluator["test_query_targets"],
                candidates, candidate_masks, prior, chosen["alpha"], input_dim,
            )
            symbolic_test = _evaluate_split(
                learner["test_episodes"], evaluator["test_query_targets"],
                candidates, candidate_masks, prior, 0.0, input_dim,
            )
            results.append({
                "seed": seed,
                "support_size": support_size,
                "family_count": family_count,
                "candidate_count": len(candidates),
                "corpus_sha256": corpus["manifest"]["corpus_sha256"],
                "meta_train_families": learner["summary"]["training_families"],
                "validation_families": learner["summary"]["validation_families"],
                "test_families": learner["summary"]["test_families"],
                "prior_sha256": prior_digest,
                "prior_entropy_nats": -sum(p * math.log(p) for p in prior),
                "alpha_grid": list(alpha_grid),
                "validation_grid": validation_grid,
                "selected_alpha": chosen["alpha"],
                "test": test,
                "deterministic_symbolic_baseline": symbolic_test["summary"],
                "evaluation_wall_seconds": time.perf_counter() - started,
            })
    aggregate = []
    for support_size in support_sizes:
        selected = [row for row in results if row["support_size"] == support_size]
        for method in ("empirical_bayes", "majority"):
            for metric in ("bit_accuracy", "exact_state_accuracy"):
                values = [
                    family[method][metric]
                    for result in selected
                    for family in result["test"]["family_results"]
                ]
                aggregate.append({
                    "support_size": support_size,
                    "method": method,
                    "metric": metric,
                    "family_seed_cases": len(values),
                    "mean": statistics.mean(values),
                    "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "median": statistics.median(values),
                    "worst_family": min(values),
                })
    return {
        "benchmark_id": "zhouyi-cpg-ei-heldout-family-empirical-bayes-v1",
        "dataset": {
            "family_count_per_seed": family_count,
            "input_dim": input_dim,
            "output_dim": output_dim,
            "states_per_family": 2 ** input_dim,
            "seeds": list(seeds),
            "support_sizes": list(support_sizes),
            "candidate_count": len(candidates),
        },
        "meta_learning_method": (
            "Empirical-Bayes finite-rule prior estimated from meta-train families. "
            "Each meta-train rule is selected using its support and development labels; "
            "validation families select prior strength alpha; test-family query labels "
            "are used only for final evaluation."
        ),
        "baseline": (
            "The same finite-grammar support selector with alpha=0 and deterministic "
            "candidate-order tie breaking, plus a per-output majority predictor."
        ),
        "claim_boundary": (
            "A symbolic empirical-Bayes few-shot baseline over a fixed finite Boolean "
            "rule grammar. Not a learned neural meta-model, open-world discovery, "
            "Yi-Xue understanding, natural-language reasoning, causal discovery, "
            "or a Transformer comparison."
        ),
        "results": results,
        "aggregate_test_results": aggregate,
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
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261114, 20261115, 20261116])
    parser.add_argument("--support-sizes", type=int, nargs="+", default=[16, 32, 64])
    parser.add_argument("--alphas", type=float, nargs="+", default=list(DEFAULT_ALPHA_GRID))
    parser.add_argument("--smoothing", type=float, default=1.0)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = run_meta_benchmark(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seeds=tuple(args.seeds),
        support_sizes=tuple(args.support_sizes), alpha_grid=tuple(args.alphas),
        smoothing=args.smoothing,
    )
    write_report(report, args.json)
    print(json.dumps({
        "benchmark_id": report["benchmark_id"],
        "runs": len(report["results"]),
        "aggregate_test_results": report["aggregate_test_results"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
