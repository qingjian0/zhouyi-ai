"""Compute-accounted comparison of symbolic, full-basis, and hybrid learners.

The hybrid uses only training-selected finite-rule support candidates to build a
per-output Boolean-monomial basis, then fits a logistic head with development
checkpoint selection. Locked states are report-only. All results are synthetic
finite Boolean diagnostics, not open-world or language reasoning claims.
"""
from __future__ import annotations

import argparse
import gc
import itertools
import json
import platform
import sys
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows portability
    resource = None

from prototype.cpg_ei_early_stopping import (
    run_early_stopping_baseline,
    fit_with_early_stopping,
)
from prototype.cpg_ei_numpy_learner import fit_with_early_stopping_numpy
from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel,
    TransitionExample,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    enumerate_rule_hypotheses,
    run_discovery_benchmark,
)
from prototype.cpg_ei_relation_operators import evaluate_rule


def _state_index(state: tuple[int, ...]) -> int:
    return int("".join(str(bit) for bit in state), 2)


def _truth_mask(rule: Any, input_dim: int) -> int:
    mask = 0
    for state in itertools.product((0, 1), repeat=input_dim):
        if evaluate_rule(state, rule):
            mask |= 1 << _state_index(state)
    return mask


def _candidate_masks(input_dim: int) -> tuple[tuple[Any, int], ...]:
    return tuple(
        (rule, _truth_mask(rule, input_dim))
        for rule in enumerate_rule_hypotheses(input_dim)
    )


def _monomial_subsets(scope: tuple[int, ...]) -> set[tuple[int, ...]]:
    return {
        subset
        for arity in range(1, len(scope) + 1)
        for subset in itertools.combinations(scope, arity)
    }


def _derive_support_features(
    corpus: dict,
    candidates: tuple[tuple[Any, int], ...],
) -> dict[str, Any]:
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)

    family_results = []
    train_score_evaluations = 0
    total_minimizers = 0
    for family_id in sorted(rows_by_family):
        rows = rows_by_family[family_id]
        train_rows = [row for row in rows if row["state_split"] == "train"]
        train_mask = 0
        for row in train_rows:
            train_mask |= 1 << _state_index(tuple(row["state"]))

        supports_by_output = []
        minimizer_counts = []
        candidate_scope_counts = []
        for output_index in range(output_dim):
            target_mask = 0
            for row in train_rows:
                if row["target"][output_index]:
                    target_mask |= 1 << _state_index(tuple(row["state"]))

            best_error: int | None = None
            minimizers = []
            for rule, prediction_mask in candidates:
                train_score_evaluations += 1
                error = ((prediction_mask ^ target_mask) & train_mask).bit_count()
                if best_error is None or error < best_error:
                    best_error = error
                    minimizers = [rule]
                elif error == best_error:
                    minimizers.append(rule)

            feature_supports: set[tuple[int, ...]] = set()
            scopes = set()
            for rule in minimizers:
                scope_values = list(rule.support)
                if rule.operator == "conditional_xor":
                    scope_values.append(rule.context_index)
                scope = tuple(sorted(set(scope_values)))
                scopes.add(scope)
                feature_supports.update(_monomial_subsets(scope))

            ordered_features = tuple(sorted(
                feature_supports, key=lambda item: (len(item), item)
            ))
            if not ordered_features:
                raise AssertionError("training-selected symbolic support produced no features")
            supports_by_output.append(ordered_features)
            minimizer_counts.append(len(minimizers))
            candidate_scope_counts.append(len(scopes))
            total_minimizers += len(minimizers)

        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "supports_by_output": supports_by_output,
            "feature_counts_by_output": [len(item) for item in supports_by_output],
            "train_minimizer_counts_by_output": minimizer_counts,
            "candidate_scope_counts_by_output": candidate_scope_counts,
        })

    return {
        "candidate_hypothesis_count": len(candidates),
        "candidate_truth_table_state_evaluations": (
            len(candidates) * (2 ** input_dim)
        ),
        "candidate_output_train_score_evaluations": train_score_evaluations,
        "total_train_minimizers": total_minimizers,
        "family_results": family_results,
    }


def derive_train_only_support_features(corpus: dict) -> dict[str, Any]:
    """Public diagnostic helper used by leakage and support-boundary tests."""
    manifest = corpus["manifest"]
    candidates = _candidate_masks(manifest["input_dim"])
    derived = _derive_support_features(corpus, candidates)
    return {
        key: value for key, value in derived.items()
        if key != "family_results"
    } | {
        "family_features": [
            {
                "family_id": family["family_id"],
                "supports_by_output": [
                    [list(support) for support in supports]
                    for supports in family["supports_by_output"]
                ],
                "feature_counts_by_output": family["feature_counts_by_output"],
                "train_minimizer_counts_by_output": family["train_minimizer_counts_by_output"],
            }
            for family in derived["family_results"]
        ]
    }


def _split_metrics(
    models: list[RelationalTransitionModel],
    rows: list[dict],
) -> dict[str, float]:
    if not rows:
        raise ValueError("evaluation split must not be empty")
    bit_correct = 0
    exact_correct = 0
    for row in rows:
        state = tuple(row["state"])
        prediction = tuple(model.predict(state)[0] for model in models)
        target = tuple(row["target"])
        bit_correct += sum(int(a == b) for a, b in zip(prediction, target))
        exact_correct += int(prediction == target)
    return {
        "examples": len(rows),
        "bit_accuracy": bit_correct / (len(rows) * len(models)),
        "exact_state_accuracy": exact_correct / len(rows),
    }


def run_support_constrained_hybrid(
    corpus: dict,
    *,
    max_epochs: int = 600,
    patience: int = 30,
    min_delta: float = 1e-5,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
    optimizer_backend: str = "python",
) -> dict[str, Any]:
    if optimizer_backend not in ("python", "numpy"):
        raise ValueError("optimizer_backend must be 'python' or 'numpy'")
    fit_function = (
        fit_with_early_stopping_numpy if optimizer_backend == "numpy"
        else fit_with_early_stopping
    )
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    candidates = _candidate_masks(input_dim)
    derived = _derive_support_features(corpus, candidates)
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)

    family_results = []
    total_feature_columns = 0
    total_coefficients = 0
    total_gradient_terms = 0
    total_feature_encodings = 0
    total_development_feature_encodings = 0
    for family in derived["family_results"]:
        rows = rows_by_family[family["family_id"]]
        split_rows = {
            split: [row for row in rows if row["state_split"] == split]
            for split in ("train", "development", "locked")
        }
        examples_by_output = [
            {
                split: [
                    TransitionExample(
                        tuple(row["state"]), (row["target"][output_index],)
                    )
                    for row in split_rows[split]
                ]
                for split in ("train", "development", "locked")
            }
            for output_index in range(output_dim)
        ]

        models = []
        fits = []
        for output_index, supports in enumerate(family["supports_by_output"]):
            model = RelationalTransitionModel(
                input_dim=input_dim,
                output_dim=1,
                supports=supports,
                weights=[[0.0] * (len(supports) + 1)],
            )
            examples = examples_by_output[output_index]
            fit = fit_function(
                model,
                examples["train"],
                examples["development"],
                max_epochs=max_epochs,
                patience=patience,
                min_delta=min_delta,
                learning_rate=learning_rate,
                l2=l2,
            )
            columns = len(supports) + 1
            total_feature_columns += columns
            total_coefficients += columns
            if optimizer_backend == "numpy":
                total_feature_encodings += len(examples["train"]) * columns
                total_development_feature_encodings += (
                    len(examples["development"]) * columns
                )
            else:
                total_feature_encodings += (
                    fit["epochs_run"] * len(examples["train"]) * columns
                )
                total_development_feature_encodings += (
                    (fit["epochs_run"] + 1) * len(examples["development"]) * columns
                )
            total_gradient_terms += fit["epochs_run"] * len(examples["train"]) * columns
            models.append(model)
            fits.append({
                "output_index": output_index,
                "feature_count_excluding_bias": len(supports),
                "feature_columns_including_bias": columns,
                "train_minimizer_count": family["train_minimizer_counts_by_output"][output_index],
                "candidate_scope_count": family["candidate_scope_counts_by_output"][output_index],
                **fit,
            })

        family_results.append({
            "family_id": family["family_id"],
            "family_split": family["family_split"],
            "training": _split_metrics(models, split_rows["train"]),
            "development": _split_metrics(models, split_rows["development"]),
            "locked": _split_metrics(models, split_rows["locked"]),
            "feature_counts_by_output": family["feature_counts_by_output"],
            "mean_feature_count_per_output": (
                sum(family["feature_counts_by_output"]) / output_dim
            ),
            "total_model_coefficients": sum(
                item["feature_columns_including_bias"] for item in fits
            ),
            "output_fits": fits,
        })

    def summarize(split: str) -> dict[str, float]:
        selected = [item[split] for item in family_results]
        return {
            "families": len(selected),
            "mean_bit_accuracy": sum(row["bit_accuracy"] for row in selected) / len(selected),
            "mean_exact_state_accuracy": sum(
                row["exact_state_accuracy"] for row in selected
            ) / len(selected),
        }

    feature_counts = [
        count
        for family in family_results
        for count in family["feature_counts_by_output"]
    ]
    return {
        "benchmark_id": "zhouyi-cpg-ei-symbolic-support-hybrid-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "model": {
            "type": "per-output logistic heads over train-only symbolic-support monomials",
            "optimizer_backend": optimizer_backend,
            "input_dim": input_dim,
            "output_dim": output_dim,
            "max_epochs": max_epochs,
            "patience": patience,
            "min_delta": min_delta,
            "learning_rate": learning_rate,
            "l2": l2,
            "feature_selection": (
                "union of all non-empty monomial subsets of scopes belonging to "
                "minimum-training-error finite-rule candidates; no development or locked labels"
            ),
            "checkpoint_selection": "minimum development binary cross-entropy",
        },
        "candidate_accounting": {
            "candidate_hypothesis_count": derived["candidate_hypothesis_count"],
            "candidate_truth_table_state_evaluations": derived[
                "candidate_truth_table_state_evaluations"
            ],
            "candidate_output_train_score_evaluations": derived[
                "candidate_output_train_score_evaluations"
            ],
            "total_train_minimizers": derived["total_train_minimizers"],
        },
        "feature_accounting": {
            "feature_count_excluding_bias": {
                "min": min(feature_counts),
                "mean": sum(feature_counts) / len(feature_counts),
                "max": max(feature_counts),
                "total_across_family_output_heads": sum(feature_counts),
            },
            "feature_columns_including_bias_total": total_feature_columns,
            "model_coefficients_total": total_coefficients,
        },
        "compute_accounting": {
            "optimizer_epochs_total": sum(
                fit["epochs_run"]
                for family in family_results
                for fit in family["output_fits"]
            ),
            "training_feature_encodings": total_feature_encodings,
            "development_feature_encodings_for_checkpoint_selection": (
                total_development_feature_encodings
            ),
            "gradient_feature_contributions": total_gradient_terms,
        },
        "training_summary": summarize("training"),
        "development_summary": summarize("development"),
        "locked_summary": summarize("locked"),
        "family_results": family_results,
        "evaluation_protocol": (
            "Per-family supervised adaptation. Candidate supports are selected "
            "from training labels only. Development labels select checkpoints. "
            "Locked labels are report-only and never affect support or weights."
        ),
        "claim_boundary": (
            "Synthetic finite Boolean benchmark only. The hybrid uses an explicit "
            "finite rule grammar to constrain features and independently fits each "
            "family; it is not cross-family meta-learning, zero-shot transfer, "
            "open-world relation discovery, causal discovery, Yi-Xue understanding, "
            "natural-language reasoning, or evidence of Transformer superiority."
        ),
    }


def _symbolic_quality(report: dict[str, Any]) -> dict[str, Any]:
    outputs = [
        output
        for family in report["family_results"]
        for output in family["output_results"]
    ]
    count = len(outputs)
    return {
        "outputs": count,
        "locked_bit_accuracy": sum(
            item["locked_bit_accuracy"] for item in outputs
        ) / count,
        "full_truth_table_exact_rate": sum(
            item["full_truth_table_exact"] for item in outputs
        ) / count,
        "operator_recovery_rate": sum(
            item["operator_recovered"] for item in outputs
        ) / count,
        "exact_rule_recovery_rate": sum(
            item["exact_rule_recovered"] for item in outputs
        ) / count,
        "mean_train_minimizer_count": sum(
            item["train_minimizer_count"] for item in outputs
        ) / count,
        "mean_development_tie_count": sum(
            item["development_tie_count"] for item in outputs
        ) / count,
    }


def _peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _measure(callable_obj):
    gc.collect()
    baseline_current, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    started = time.perf_counter()
    result = callable_obj()
    wall_seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    return result, wall_seconds, max(0, peak - baseline_current)


def run_compute_accounted_comparison(
    corpus: dict,
    *,
    max_epochs: int = 600,
    patience: int = 30,
    min_delta: float = 1e-5,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    manifest = corpus["manifest"]
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    try:
        symbolic_report, symbolic_seconds, symbolic_peak = _measure(
            lambda: run_discovery_benchmark(corpus)
        )
        symbolic_quality = _symbolic_quality(symbolic_report)
        symbolic_candidate_count = symbolic_report["candidate_hypothesis_count"]
        symbolic_dev_ties = sum(
            output["train_minimizer_count"]
            for family in symbolic_report["family_results"]
            for output in family["output_results"]
        )
        symbolic_candidate_evaluations = (
            symbolic_candidate_count * manifest["family_count"] * manifest["output_dim"]
        )
        symbolic_aliases = {
            "truth_functions": symbolic_report["candidate_truth_function_count"],
            "structural_aliases": symbolic_report["candidate_structural_alias_count"],
        }
        del symbolic_report
        gc.collect()

        full_report, full_seconds, full_peak = _measure(
            lambda: run_early_stopping_baseline(
                corpus,
                max_epochs=max_epochs,
                patience=patience,
                min_delta=min_delta,
                learning_rate=learning_rate,
                l2=l2,
            )
        )
        full_quality = {
            "training": full_report["training_summary"],
            "development": full_report["development_summary"],
            "locked": full_report["locked_summary"],
        }
        full_family_results = full_report["family_results"]
        full_columns = (2 ** manifest["input_dim"])
        full_train_count = manifest["state_split_per_family"]["train"]
        full_epochs_total = sum(row["epochs_run"] for row in full_family_results)
        full_feature_encodings = (
            full_epochs_total * full_train_count * full_columns
        )
        full_gradient_terms = (
            full_feature_encodings * manifest["output_dim"]
        )
        full_accounting = {
            "feature_count_excluding_bias_per_output": full_columns - 1,
            "feature_columns_including_bias_per_output": full_columns,
            "model_coefficients_per_family": full_columns * manifest["output_dim"],
            "optimizer_epochs_total": full_epochs_total,
            "training_feature_encodings": full_feature_encodings,
            "gradient_feature_contributions": full_gradient_terms,
            "candidate_output_train_score_evaluations": 0,
        }
        del full_report, full_family_results
        gc.collect()

        hybrid_report, hybrid_seconds, hybrid_peak = _measure(
            lambda: run_support_constrained_hybrid(
                corpus,
                max_epochs=max_epochs,
                patience=patience,
                min_delta=min_delta,
                learning_rate=learning_rate,
                l2=l2,
            )
        )
        hybrid_quality = {
            "training": hybrid_report["training_summary"],
            "development": hybrid_report["development_summary"],
            "locked": hybrid_report["locked_summary"],
        }
        hybrid_candidates = hybrid_report["candidate_accounting"]
        hybrid_features = hybrid_report["feature_accounting"]
        hybrid_compute = hybrid_report["compute_accounting"]
        hybrid_claim_boundary = hybrid_report["claim_boundary"]
        del hybrid_report
        gc.collect()

        return {
            "benchmark_id": "zhouyi-cpg-ei-compute-accounted-hybrid-v1",
            "dataset_id": manifest["dataset_id"],
            "corpus_sha256": manifest["corpus_sha256"],
            "dataset": {
                "seed": manifest["seed"],
                "families": manifest["family_count"],
                "rows": manifest["row_count"],
                "input_dim": manifest["input_dim"],
                "output_dim": manifest["output_dim"],
                "state_split_per_family": manifest["state_split_per_family"],
                "family_split_counts": manifest["family_split_counts"],
            },
            "optimizer_config": {
                "max_epochs": max_epochs,
                "patience": patience,
                "min_delta": min_delta,
                "learning_rate": learning_rate,
                "l2": l2,
                "initialization": "all-zero weights",
            },
            "methods": {
                "exhaustive_symbolic": {
                    "wall_seconds": symbolic_seconds,
                    "peak_traced_allocation_delta_bytes": symbolic_peak,
                    "candidate_hypothesis_count": symbolic_candidate_count,
                    "candidate_truth_table_state_evaluations": (
                        symbolic_candidate_count * (2 ** manifest["input_dim"])
                    ),
                    "candidate_output_train_score_evaluations": symbolic_candidate_evaluations,
                    "development_tie_break_evaluations": symbolic_dev_ties,
                    "candidate_aliases": symbolic_aliases,
                    "quality": symbolic_quality,
                },
                "full_polynomial_early_stopping": {
                    "wall_seconds": full_seconds,
                    "peak_traced_allocation_delta_bytes": full_peak,
                    "candidate_hypothesis_count": 0,
                    "feature_accounting": full_accounting,
                    "quality": full_quality,
                },
                "symbolic_support_constrained_hybrid": {
                    "wall_seconds": hybrid_seconds,
                    "peak_traced_allocation_delta_bytes": hybrid_peak,
                    "candidate_accounting": hybrid_candidates,
                    "feature_accounting": hybrid_features,
                    "compute_accounting": hybrid_compute,
                    "quality": hybrid_quality,
                    "claim_boundary": hybrid_claim_boundary,
                },
            },
            "resource_accounting": {
                "memory_method": (
                    "tracemalloc peak allocation increase over each method's "
                    "pre-call Python-heap baseline; corpus is generated before timing"
                ),
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "rss_scope": (
                    "process-wide high-water mark across all methods, not an "
                    "isolated per-method RSS measurement"
                ),
                "wall_time_scope": (
                    "method execution only; common corpus generation is excluded; "
                    "tracemalloc instrumentation is enabled consistently"
                ),
                "runtime": {
                    "python": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "platform": platform.platform(),
                },
            },
            "evaluation_protocol": (
                "All methods use the identical corpus digest and per-family state "
                "splits. Symbolic selection uses train error then development "
                "tie-breaking. The hybrid uses training-only candidate supports; "
                "development selects checkpoints. Locked states are evaluation-only. "
                "Each family is fitted independently; this is not cross-family transfer."
            ),
            "claim_boundary": (
                "Synthetic finite Boolean operators and a declared finite symbolic "
                "hypothesis space only. No claim of generalization, Yi-Xue understanding, "
                "causal discovery, natural-language reasoning, open-world induction, "
                "or Transformer superiority."
            ),
        }
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()


def write_json_report(report: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--max-epochs", type=int, default=600)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families,
        input_dim=args.input_dim,
        output_dim=args.output_dim,
        seed=args.seed,
    )
    report = run_compute_accounted_comparison(
        corpus,
        max_epochs=args.max_epochs,
        patience=args.patience,
        min_delta=args.min_delta,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
