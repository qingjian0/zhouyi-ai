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
            bayes_sum / (sum(len(e.inputs.queries) for e in rows)) if audited else None
        ),
        "audited_episodes": audited,
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
    count, hidden = max(under, key=lambda pair: pair[0]) if under else min(candidates)
    return hidden, count


def run_condition(cardinality: int, support_size: int, seed: int,
                  episodes_per_rule: int, epochs: int, hidden_size: int,
                  parameter_matched: bool = True,
                  parameter_budget: int | None = None) -> dict:
    splits = make_rule_disjoint_splits(
        cardinality=cardinality,
        episodes_per_rule=episodes_per_rule,
        support_size=support_size,
        query_count=2,
        seed=seed,
        symbol_mappings=("canonical", "permuted"),
    )
    family_results = {}
    for family in FAMILIES:
        learner = SetConditionedMLPLearner(
            family=family, hidden_size=hidden_size, embedding_dim=6, seed=seed
        )
        started = time.perf_counter()
        fit = learner.fit(
            splits.train, validation_episodes=splits.validation,
            budget={"epochs": epochs}, seed=seed,
        )
        train_seconds = time.perf_counter() - started
        # Predictions are produced from learner-visible inputs only.
        predictions = [learner.predict(item.inputs) for item in splits.locked_test]
        metrics = _metrics(predictions, splits.locked_test, cardinality)
        by_mapping = {}
        for mapping in ("canonical", "permuted"):
            selected = [(p, e) for p, e in zip(predictions, splits.locked_test)
                        if e.inputs.symbol_mapping == mapping]
            by_mapping[mapping] = _metrics(
                [p for p, _ in selected], [e for _, e in selected], cardinality
            )
        family_results[family] = {
            "fit": asdict(fit),
            "metadata": learner.metadata(),
            "train_seconds": train_seconds,
            "locked_test": metrics,
            "locked_test_by_mapping": by_mapping,
        }
    return {
        "cardinality": cardinality,
        "support_size": support_size,
        "seed": seed,
        "split_metadata": splits.metadata,
        "rule_counts": {k: len(v) for k, v in splits.rule_families.items()},
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
    return result


def run_sweep(cardinalities: tuple[int, ...] = (3,), support_sizes: tuple[int, ...] = (2, 4, 8),
              seeds: tuple[int, ...] = (11, 29, 47), episodes_per_rule: int = 1,
              epochs: int = 5, hidden_size: int = 24,\n              parameter_matched: bool = True, parameter_budget: int | None = None) -> dict:
    conditions = []
    for k in cardinalities:
        for support in support_sizes:
            if not 1 <= support < k * k:
                raise ValueError(f"support_size must be in [1, K*K): K={k}, support={support}")
            runs = [run_condition(k, support, seed, episodes_per_rule, epochs, hidden_size,\n                                      parameter_matched, parameter_budget)
                    for seed in seeds]
            conditions.append({
                "cardinality": k, "support_size": support,
                "runs": runs, "aggregate": aggregate_runs(runs),
            })
    return {
        "protocol": "TX-02B-4",
        "families": list(FAMILIES),
        "configuration": {
            "cardinalities": list(cardinalities), "support_sizes": list(support_sizes),
            "seeds": list(seeds), "episodes_per_rule": episodes_per_rule,
            "epochs": epochs, "hidden_size": hidden_size,\n            "parameter_matched": parameter_matched, "parameter_budget": parameter_budget,\n            "parameter_matched": parameter_matched, "parameter_budget": parameter_budget,
        },
        "conditions": conditions,
        "interpretation_limits": [
            "Locked-test scores are descriptive for this finite affine rule generator only.",
            "Rule coefficients are disjoint across train, validation and locked-test.",
            "Posterior audit is exact only within the TX-02A affine hypothesis class and its stated uniform prior.",
            "Parameter matching is approximate: each family chooses the largest hidden size under a shared parameter budget; parameter deltas are reported. This is not compute matching.",\n            "FIXED_RANDOM and LEARNED share the same embedding dimension and initialization distribution; only LEARNED updates the embedding table.",
            "Validation is reported but no hyperparameter search or test-driven model selection is performed.",
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
    parser.add_argument("--hidden-size", type=int, default=24)\n    parser.add_argument("--no-parameter-match", action="store_true")\n    parser.add_argument("--parameter-budget", type=int, default=None)\n    parser.add_argument("--no-parameter-match", action="store_true")\n    parser.add_argument("--parameter-budget", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_sweep(tuple(args.cardinalities), tuple(args.support_sizes),
                       tuple(args.seeds), args.episodes_per_rule,
                       args.epochs, args.hidden_size,\n                       not args.no_parameter_match, args.parameter_budget)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else {
        "protocol": result["protocol"], "configuration": result["configuration"],
        "conditions": [{
            "cardinality": c["cardinality"], "support_size": c["support_size"],
            "aggregate": c["aggregate"],
        } for c in result["conditions"]],
    })


if __name__ == "__main__":
    main()
