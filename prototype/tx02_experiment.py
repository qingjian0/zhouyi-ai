"""TX-02B-4 reproducible support-size and representation sweep.

The locked test is evaluated only after fitting on train and inspecting validation
metrics. This runner records the exact affine-family audit beside model metrics;
it does not claim compute-matched comparisons or representation superiority.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict
from typing import Iterable

from prototype.tx02_identifiability import audit_episode
from prototype.tx02_learners import SetConditionedMLPLearner
from prototype.tx02_compute import (
    apply_abstention, choose_abstention_threshold, choose_hidden_size_for_compute_budget,
    estimate_forward_macs, probability_metrics, risk_coverage_curve, select_representation,
)
from prototype.tx02_state_encoders import build_codebook
from prototype.tx02_multistate_benchmark import episode_to_dict
from prototype.tx02_splits import EvaluationEpisode, make_rule_disjoint_splits

FAMILIES = ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED", "FIXED_RANDOM", "PERMUTED")


def _metrics(predictions: list[tuple[int, ...]], episodes: Iterable[EvaluationEpisode],
             cardinality: int) -> dict:
    rows = tuple(episodes)
    correct = total = exact = 0
    brier_sum = 0.0
    identifiable_correct = identifiable_total = 0
    bayes_sum = 0.0
    audited = 0
    audited_query_count = 0
    for prediction, episode in zip(predictions, rows):
        episode_correct = True
        for qi, (guess, target) in enumerate(zip(prediction, episode.targets)):
            hit = int(guess == target)
            correct += hit
            total += 1
            episode_correct = episode_correct and bool(hit)
            audit_payload = {
                "cardinality": episode.inputs.cardinality,
                "symbol_mapping": episode.inputs.symbol_mapping,
                "support": [list(x) for x in episode.inputs.support],
                "queries": [list(x) for x in episode.inputs.queries],
                "candidates": [list(x) for x in episode.inputs.candidates],
            }
            # One exact audit per episode; query statistics are accumulated below.
            if qi == 0:
                audit = audit_episode(audit_payload)
                if audit["status"] == "ok":
                    audited += 1
                    for qresult in audit["queries"]:
                        bayes_sum += qresult["bayes_optimal_accuracy"]
                        audited_query_count += 1
                        if qresult["answer_identifiable"]:
                            qindex = qresult["query_index"]
                            identifiable_total += 1
                            identifiable_correct += int(prediction[qindex] == episode.targets[qindex])
        exact += int(episode_correct)
    return {
        "query_accuracy": correct / total if total else None,
        "episode_exact_match": exact / len(rows) if rows else None,
        "identifiable_query_accuracy": (
            identifiable_correct / identifiable_total if identifiable_total else None
        ),
        "identifiable_query_count": identifiable_total,
        "mean_exact_posterior_bayes_accuracy": (
            bayes_sum / audited_query_count if audited_query_count else None
        ),
        "audited_episodes": audited,
        "audited_query_count": audited_query_count,
        "query_count": total,
        "uniform_chance_accuracy": 1.0 / cardinality,
    }


def model_parameter_count(family: str, cardinality: int, hidden_size: int,
                           embedding_dim: int = 6) -> int:
    if family in ("LEARNED", "FIXED_RANDOM"):
        feature_dim = embedding_dim
    else:
        code_family = "PERMUTED" if family == "PERMUTED" else family
        feature_dim = build_codebook(cardinality, code_family).dimension
    trainable_embedding_count = cardinality * embedding_dim if family == "LEARNED" else 0
    return trainable_embedding_count + hidden_size * (6 * feature_dim + 2) + 1


def choose_hidden_size_for_budget(family: str, cardinality: int, target_parameters: int,
                                  embedding_dim: int = 6,
                                  max_hidden_size: int = 4096) -> tuple[int, int]:
    if type(target_parameters) is not int or target_parameters < 1:
        raise ValueError("target_parameters must be a positive integer")
    candidates = [
        (model_parameter_count(family, cardinality, hidden, embedding_dim), hidden)
        for hidden in range(1, max_hidden_size + 1)
    ]
    # Prefer the largest model that does not exceed the target; if impossible,
    # use the smallest model and expose the mismatch in the report.
    under = [(count, hidden) for count, hidden in candidates if count <= target_parameters]
    if not under:
        raise ValueError(
            f"parameter budget {target_parameters} is below the minimum model size "
            f"for {family} at K={cardinality}"
        )
    count, hidden = max(under, key=lambda pair: pair[0])
    return hidden, count


def _collect_probabilities(learner: SetConditionedMLPLearner,
                            episodes: Iterable[EvaluationEpisode]) -> tuple[list[tuple[float, ...]], list[int]]:
    probability_rows = []
    targets = []
    for episode in episodes:
        for qi, target in enumerate(episode.targets):
            probability_rows.append(learner.predict_proba(episode.inputs, qi))
            targets.append(target)
    return probability_rows, targets


def run_condition(cardinality: int, support_size: int, seed: int,
                  episodes_per_rule: int, epochs: int, hidden_size: int,
                  parameter_matched: bool = True,
                  parameter_budget: int | None = None,
                  compute_matched: bool = False,
                  forward_mac_budget: int | None = None,
                  max_selective_risk: float = 0.20) -> dict:
    if parameter_matched and compute_matched:
        raise ValueError("choose either parameter matching or compute matching, not both")
    if not 0.0 <= max_selective_risk <= 1.0:
        raise ValueError("max_selective_risk must be in [0,1]")
    splits = make_rule_disjoint_splits(
        cardinality=cardinality, episodes_per_rule=episodes_per_rule,
        support_size=support_size, query_count=2, seed=seed,
        symbol_mappings=("canonical", "permuted"),
    )
    target_parameter_budget = parameter_budget
    if target_parameter_budget is None and parameter_matched:
        target_parameter_budget = max(
            model_parameter_count(family, cardinality, hidden_size, 6)
            for family in FAMILIES
        )
    target_compute_budget = forward_mac_budget
    if compute_matched and target_compute_budget is None:
        target_compute_budget = max(
            estimate_forward_macs(family, cardinality, hidden_size,
                                  support_size, 2, cardinality, 6)
            for family in FAMILIES
        )

    # Phase A: train all candidates and inspect validation only.
    trained = {}
    validation_selection_metrics = {}
    for family in FAMILIES:
        selected_hidden_size = hidden_size
        if parameter_matched:
            selected_hidden_size, _ = choose_hidden_size_for_budget(
                family, cardinality, target_parameter_budget, embedding_dim=6
            )
        elif compute_matched:
            selected_hidden_size, _ = choose_hidden_size_for_compute_budget(
                family, cardinality, target_compute_budget,
                support_size, 2, cardinality, 6
            )
        learner = SetConditionedMLPLearner(
            family=family, hidden_size=selected_hidden_size, embedding_dim=6, seed=seed
        )
        started = time.perf_counter()
        fit = learner.fit(
            splits.train, validation_episodes=splits.validation,
            budget={"epochs": epochs}, seed=seed,
        )
        train_seconds = time.perf_counter() - started
        validation_probs, validation_targets = _collect_probabilities(learner, splits.validation)
        validation_metrics = probability_metrics(validation_probs, validation_targets)
        episode_macs = estimate_forward_macs(
            family, cardinality, selected_hidden_size, support_size, 2, cardinality, 6
        )
        threshold = choose_abstention_threshold(
            validation_probs, validation_targets, max_selective_risk
        )
        validation_selection_metrics[family] = {
            "accuracy": validation_metrics["accuracy"],
            "nll": validation_metrics["nll"],
            "forward_macs": episode_macs,
            "parameter_count": fit.parameter_count,
        }
        trained[family] = {
            "learner": learner, "fit": fit, "hidden_size": selected_hidden_size,
            "train_seconds": train_seconds, "validation_metrics": validation_metrics,
            "validation_abstention": threshold, "episode_macs": episode_macs,
        }

    # Freeze the adaptive choice before reading any locked-test targets.
    adaptive_choice = select_representation(validation_selection_metrics)

    # Phase B: evaluate fixed baselines and the already-frozen selected policy.
    # Fixed-family test metrics are retained as descriptive baselines; they never
    # feed back into the selector or validation-calibrated abstention threshold.
    family_results = {}
    for family in FAMILIES:
        record = trained[family]
        learner = record["learner"]
        test_probs, test_targets = _collect_probabilities(learner, splits.locked_test)
        cursor = 0
        episode_predictions = []
        for item in splits.locked_test:
            count = len(item.targets)
            episode_predictions.append(tuple(
                max(range(len(test_probs[cursor + offset])),
                    key=lambda i: test_probs[cursor + offset][i])
                for offset in range(count)
            ))
            cursor += count
        metrics = _metrics(episode_predictions, splits.locked_test, cardinality)
        test_probability_metrics = probability_metrics(test_probs, test_targets)
        deferred = apply_abstention(
            test_probs, record["validation_abstention"]["threshold"]
        )
        accepted = [(decision, target) for decision, target in zip(deferred, test_targets)
                    if decision is not None]
        selective = {
            "threshold_selected_on": "validation",
            "threshold": record["validation_abstention"]["threshold"],
            "validation_coverage": record["validation_abstention"]["coverage"],
            "validation_selective_risk": record["validation_abstention"]["selective_risk"],
            "locked_test_coverage": len(accepted) / len(test_targets) if test_targets else 0.0,
            "locked_test_selective_risk": (
                sum(decision != target for decision, target in accepted) / len(accepted)
                if accepted else None
            ),
            "locked_test_deferred_count": len(test_targets) - len(accepted),
            "locked_test_risk_coverage_curve": list(risk_coverage_curve(test_probs, test_targets)),
        }
        by_mapping = {}
        for mapping in ("canonical", "permuted"):
            selected = [(prediction, episode) for prediction, episode
                        in zip(episode_predictions, splits.locked_test)
                        if episode.inputs.symbol_mapping == mapping]
            by_mapping[mapping] = _metrics(
                [prediction for prediction, _ in selected],
                [episode for _, episode in selected], cardinality
            )
        fit = record["fit"]
        episode_macs = record["episode_macs"]
        family_results[family] = {
            "fit": asdict(fit),
            "metadata": learner.metadata(),
            "target_parameter_budget": target_parameter_budget if parameter_matched else None,
            "parameter_budget_delta": (
                fit.parameter_count - target_parameter_budget if parameter_matched else None
            ),
            "target_forward_mac_budget": target_compute_budget if compute_matched else None,
            "forward_macs_per_episode": episode_macs,
            "forward_macs_budget_delta": (
                episode_macs - target_compute_budget if compute_matched else None
            ),
            "estimated_training_forward_macs": len(splits.train) * epochs * episode_macs,
            "train_seconds": record["train_seconds"],
            "validation_probability_metrics": record["validation_metrics"],
            "validation_abstention_calibration": record["validation_abstention"],
            "locked_test_probability_metrics": test_probability_metrics,
            "locked_test_selective_prediction": selective,
            "locked_test": metrics,
            "locked_test_by_mapping": by_mapping,
        }

    selected_family = adaptive_choice["selected_family"]
    adaptive_locked_test = family_results[selected_family]["locked_test"]
    return {
        "cardinality": cardinality, "support_size": support_size, "seed": seed,
        "parameter_matched": parameter_matched, "compute_matched": compute_matched,
        "target_parameter_budget": target_parameter_budget if parameter_matched else None,
        "target_forward_mac_budget": target_compute_budget if compute_matched else None,
        "validation_representation_selection": adaptive_choice,
        "adaptive_representation_locked_test": adaptive_locked_test,
        "split_metadata": splits.metadata,
        "rule_counts": {key: len(value) for key, value in splits.rule_families.items()},
        "episode_counts": {
            "train": len(splits.train), "validation": len(splits.validation),
            "locked_test": len(splits.locked_test),
        },
        "families": family_results,
    }


def aggregate_runs(runs: list[dict]) -> dict:
    result = {}
    for family in FAMILIES:
        values = [r["families"][family]["locked_test"]["query_accuracy"] for r in runs]
        result[family] = {
            "mean_query_accuracy": statistics.mean(values),
            "stdev_query_accuracy": statistics.stdev(values) if len(values) > 1 else 0.0,
            "seed_count": len(values),
            "parameter_counts": [
                r["families"][family]["fit"]["parameter_count"] for r in runs
            ],
        }
    adaptive_values = [
        r["adaptive_representation_locked_test"]["query_accuracy"] for r in runs
    ]
    result["ADAPTIVE_VALIDATION_SELECTED"] = {
        "mean_query_accuracy": statistics.mean(adaptive_values),
        "stdev_query_accuracy": (
            statistics.stdev(adaptive_values) if len(adaptive_values) > 1 else 0.0
        ),
        "seed_count": len(adaptive_values),
        "selected_families": [
            r["validation_representation_selection"]["selected_family"] for r in runs
        ],
    }
    return result


def run_sweep(cardinalities: tuple[int, ...] = (3,), support_sizes: tuple[int, ...] = (2, 4, 8),
              seeds: tuple[int, ...] = (11, 29, 47), episodes_per_rule: int = 1,
              epochs: int = 5, hidden_size: int = 24,
              parameter_matched: bool = True,
              parameter_budget: int | None = None,
              compute_matched: bool = False,
              forward_mac_budget: int | None = None,
              max_selective_risk: float = 0.20) -> dict:
    conditions = []
    for k in cardinalities:
        for support in support_sizes:
            if not 1 <= support < k * k:
                raise ValueError(f"support_size must be in [1, K*K): K={k}, support={support}")
            runs = [
                run_condition(
                    k, support, seed, episodes_per_rule, epochs, hidden_size,
                    parameter_matched, parameter_budget,
                    compute_matched, forward_mac_budget, max_selective_risk,
                )
                for seed in seeds
            ]
            conditions.append({
                "cardinality": k,
                "support_size": support,
                "runs": runs,
                "aggregate": aggregate_runs(runs),
            })
    return {
        "protocol": "TX-02D-1",
        "families": list(FAMILIES),
        "configuration": {
            "cardinalities": list(cardinalities),
            "support_sizes": list(support_sizes),
            "seeds": list(seeds),
            "episodes_per_rule": episodes_per_rule,
            "epochs": epochs,
            "hidden_size": hidden_size,
            "parameter_matched": parameter_matched,
            "parameter_budget": parameter_budget,
            "compute_matched": compute_matched,
            "forward_mac_budget": forward_mac_budget,
            "max_selective_risk": max_selective_risk,
        },
        "conditions": conditions,
        "interpretation_limits": [
            "Locked-test scores are descriptive for this finite affine rule generator only.",
            "Rule coefficients are disjoint across train, validation and locked-test.",
            "Posterior audit is exact only within the TX-02A affine hypothesis class and its stated uniform prior.",
            "Parameter matching and forward-MAC matching are separate modes; neither is a complete FLOPs or wall-clock match.",
            "Forward-MAC proxy excludes nonlinearities, pooling, softmax, memory traffic, Python overhead, backward pass and optimizer work.",
            "Adaptive representation is selected using validation metrics only; locked-test evaluates the already selected family.",
            "Selective-risk threshold is calibrated on validation only; locked-test risk-coverage is descriptive and never used for threshold selection.",
            "FIXED_RANDOM and LEARNED share the same embedding dimension and initialization distribution; only LEARNED updates the embedding table.",
            "Validation metrics drive the adaptive representation selector; locked-test labels never enter selection or calibration.",
            "Results do not establish natural-language or general-intelligence capability.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cardinalities", type=int, nargs="+", default=[3])
    parser.add_argument("--support-sizes", type=int, nargs="+", default=[2, 4, 8])
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 29, 47])
    parser.add_argument("--episodes-per-rule", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--hidden-size", type=int, default=24)
    parser.add_argument("--no-parameter-match", action="store_true")
    parser.add_argument("--parameter-budget", type=int, default=None)
    parser.add_argument("--compute-match", action="store_true")
    parser.add_argument("--forward-mac-budget", type=int, default=None)
    parser.add_argument("--max-selective-risk", type=float, default=0.20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_sweep(
        tuple(args.cardinalities),
        tuple(args.support_sizes),
        tuple(args.seeds),
        args.episodes_per_rule,
        args.epochs,
        args.hidden_size,
        not args.no_parameter_match and not args.compute_match,
        args.parameter_budget,
        args.compute_match,
        args.forward_mac_budget,
        args.max_selective_risk,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else {
        "protocol": result["protocol"],
        "configuration": result["configuration"],
        "conditions": [{
            "cardinality": c["cardinality"],
            "support_size": c["support_size"],
            "aggregate": c["aggregate"],
        } for c in result["conditions"]],
    })


if __name__ == "__main__":
    main()
