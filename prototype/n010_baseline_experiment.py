"""Side-by-side N0.10 Xiang / MLP / low-rank tensor evaluation.

The runner builds binary relation examples from each record's complete role
candidate product. Only train targets become labels for fitting; dev and locked
test labels are used after fitting for evaluation. All models see identical
assignments and expansion caps.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Sequence

from prototype.n09_learnable_srok import (
    LearnableSROKError, Node, RelationClassificationExample, RoleSpec,
)
from prototype.n010_baselines import (
    BaselineConfig, ParameterMatchedLowRankTensor, ParameterMatchedMLP,
    match_mlp_hidden_dim, match_tensor_rank, xiang_parameter_count,
)
from prototype.n010_experiment import load_dataset
from prototype.n010_xiang_operator import LearnableXiangOperator, XiangConfig


def _assignments(row, max_expansions: int):
    pools = row["pools"]
    total = math.prod(len(pool) for pool in pools)
    if total > max_expansions:
        raise LearnableSROKError(
            f"record {row['id']} requires {total} candidates; cap is {max_expansions}"
        )
    return tuple(itertools.product(*pools))


def _training_rows(train_records, max_expansions):
    """Materialize labels for train only; dev/test targets are not touched here."""
    rows = []
    for record in train_records:
        target = tuple(record["target_ids"])
        for assignment in _assignments(record, max_expansions):
            ids = tuple(node.node_id for node in assignment)
            rows.append(RelationClassificationExample(
                assignment, 1 if ids == target else -1
            ))
    return rows


def _metrics(model, records, max_expansions):
    exact = 0
    reciprocal_rank = 0.0
    recall_at_k = {1: 0, 3: 0, 5: 0}
    total = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    calibration = []
    for record in records:
        candidates = _assignments(record, max_expansions)
        target = tuple(record["target_ids"])
        scored = []
        for assignment in candidates:
            ids = tuple(node.node_id for node in assignment)
            probability = min(max(model.predict_probability(assignment), 1e-15), 1 - 1e-15)
            scored.append((model.score(assignment), ids, probability, ids == target))
        scored.sort(key=lambda item: (-item[0], item[1]))
        rank = next((i + 1 for i, row in enumerate(scored) if row[3]), None)
        total += 1
        if rank == 1:
            exact += 1
        if rank is not None:
            reciprocal_rank += 1.0 / rank
        for k in recall_at_k:
            if rank is not None and rank <= k:
                recall_at_k[k] += 1
        for _, _, probability, positive in scored:
            target_value = 1.0 if positive else 0.0
            brier_sum += (probability - target_value) ** 2
            logloss_sum -= target_value * math.log(probability) + (1 - target_value) * math.log(1 - probability)
            calibration.append((probability, target_value))
    if not total:
        return {"examples": 0}
    calibration.sort(key=lambda x: x[0])
    ece = 0.0
    for bucket in range(10):
        lo = bucket * len(calibration) // 10
        hi = (bucket + 1) * len(calibration) // 10
        if hi > lo:
            rows = calibration[lo:hi]
            confidence = math.fsum(x[0] for x in rows) / len(rows)
            frequency = math.fsum(x[1] for x in rows) / len(rows)
            ece += len(rows) / len(calibration) * abs(confidence - frequency)
    candidate_count = len(calibration)
    return {
        "examples": total, "exact_match_accuracy": exact / total,
        "mrr": reciprocal_rank / total,
        "recall_at_1": recall_at_k[1] / total,
        "recall_at_3": recall_at_k[3] / total,
        "recall_at_5": recall_at_k[5] / total,
        "candidate_brier": brier_sum / candidate_count,
        "candidate_log_loss": logloss_sum / candidate_count,
        "candidate_ece_10": ece,
        "candidate_count": candidate_count,
    }


def run_comparison(dataset_path: str | Path, roles: Sequence[RoleSpec],
                   feature_dim: int, output_path: str | Path, *,
                   latent_dim: int = 8, seed: int = 0, epochs: int = 100,
                   learning_rate: float = 0.03, l2: float = 1e-4,
                   max_expansions: int = 4096):
    splits, manifest = load_dataset(dataset_path, roles, feature_dim)
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise LearnableSROKError("epochs must be positive")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise LearnableSROKError("seed must be non-negative")
    if isinstance(max_expansions, bool) or not isinstance(max_expansions, int) or max_expansions < 1:
        raise LearnableSROKError("max_expansions must be positive")
    train_rows = _training_rows(splits["train"], max_expansions)
    target_params = xiang_parameter_count(len(roles), feature_dim, latent_dim)
    hidden_dim = match_mlp_hidden_dim(len(roles), feature_dim, target_params)
    rank = match_tensor_rank(len(roles), feature_dim, target_params)
    models = {
        "learnable_xiang": LearnableXiangOperator(
            roles, feature_dim, XiangConfig(latent_dim, "learnable", seed)),
        "fixed_random_xiang": LearnableXiangOperator(
            roles, feature_dim, XiangConfig(latent_dim, "fixed_random", seed)),
        "parameter_matched_mlp": ParameterMatchedMLP(
            len(roles), feature_dim, hidden_dim, BaselineConfig(seed)),
        "parameter_matched_low_rank_tensor": ParameterMatchedLowRankTensor(
            len(roles), feature_dim, rank, BaselineConfig(seed)),
    }
    histories = {}
    for name, model in models.items():
        histories[name] = model.fit(
            train_rows, epochs=epochs, learning_rate=learning_rate, l2=l2,
        )
    reports = {}
    for name, model in models.items():
        reports[name] = {
            "parameter_count": getattr(model, "parameter_count", target_params),
            "training_steps": model.training_steps,
            "final_train_loss": histories[name][-1],
            "dev": _metrics(model, splits["dev"], max_expansions),
            "locked_test": _metrics(model, splits["locked_test"], max_expansions),
        }
    result = {
        "schema": "zhouyi-ai.n010-baseline-comparison-v1",
        "dataset_manifest": manifest,
        "config": {
            "latent_dim": latent_dim, "seed": seed, "epochs": epochs,
            "learning_rate": learning_rate, "l2": l2,
            "max_expansions": max_expansions,
            "train_relation_examples": len(train_rows),
            "mlp_hidden_dim": hidden_dim, "tensor_rank": rank,
            "parameter_target": target_params,
        },
        "models": reports,
        "locked_test_policy": "locked labels evaluated after all models are fitted; do not tune on this report",
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, indent=2,
                               ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")
    return result



def run_multi_seed_comparison(dataset_path: str | Path, roles: Sequence[RoleSpec],
                              feature_dim: int, output_path: str | Path, *,
                              seeds: Sequence[int], latent_dim: int = 8,
                              epochs: int = 100, learning_rate: float = 0.03,
                              l2: float = 1e-4, max_expansions: int = 4096):
    """Run independent seeds and aggregate paired per-seed model metrics."""
    seed_values = tuple(seeds)
    if not seed_values or any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
                              for seed in seed_values) or len(set(seed_values)) != len(seed_values):
        raise LearnableSROKError("seeds must be a non-empty sequence of unique non-negative integers")
    output = Path(output_path)
    runs = []
    for seed in seed_values:
        seed_path = output.with_name(f"{output.stem}.seed-{seed}{output.suffix}")
        runs.append(run_comparison(
            dataset_path, roles, feature_dim, seed_path,
            latent_dim=latent_dim, seed=seed, epochs=epochs,
            learning_rate=learning_rate, l2=l2,
            max_expansions=max_expansions,
        ))
    metric_names = (
        "exact_match_accuracy", "mrr", "recall_at_1", "recall_at_3",
        "recall_at_5", "candidate_brier", "candidate_log_loss",
        "candidate_ece_10",
    )
    aggregates = {}
    for model_name in runs[0]["models"]:
        aggregates[model_name] = {}
        for split_name in ("dev", "locked_test"):
            aggregates[model_name][split_name] = {}
            for metric in metric_names:
                values = [run["models"][model_name][split_name][metric] for run in runs]
                avg = math.fsum(values) / len(values)
                variance = (math.fsum((value - avg) ** 2 for value in values) /
                            (len(values) - 1)) if len(values) > 1 else 0.0
                sd = math.sqrt(variance)
                half_width = 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0
                aggregates[model_name][split_name][metric] = {
                    "mean": avg, "std": sd,
                    "ci95_normal": [max(0.0, avg - half_width), min(1.0, avg + half_width)],
                    "per_seed": values,
                }
    result = {
        "schema": "zhouyi-ai.n010-baseline-multiseed-v1",
        "dataset_manifest": runs[0]["dataset_manifest"],
        "seeds": list(seed_values), "seed_count": len(seed_values),
        "config": runs[0]["config"],
        "models": aggregates,
        "per_seed_reports": [
            {"seed": seed, "path": str(output.with_name(
                f"{output.stem}.seed-{seed}{output.suffix}"))}
            for seed in seed_values
        ],
        "interval_note": "normal-approximation 95% CI across independent seeds; use paired bootstrap for final claims",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2,
                                 ensure_ascii=False, allow_nan=False) + "\\n",
                      encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description="Compare N0.10 Xiang and matched baselines")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--feature-dim", required=True, type=int)
    parser.add_argument("--roles-json", required=True)
    parser.add_argument("--latent-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--max-expansions", type=int, default=4096)
    args = parser.parse_args()
    role_rows = json.loads(args.roles_json)
    roles = tuple(RoleSpec(x["name"], frozenset(x.get("allowed_types", [])),
                           frozenset(x.get("required_tags", []))) for x in role_rows)
    result = run_comparison(
        args.dataset, roles, args.feature_dim, args.output,
        latent_dim=args.latent_dim, seed=args.seed, epochs=args.epochs,
        learning_rate=args.learning_rate, l2=args.l2,
        max_expansions=args.max_expansions,
    )
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
