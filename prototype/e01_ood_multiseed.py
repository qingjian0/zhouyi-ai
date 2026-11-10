"""Run E01-C compositional OOD over multiple seeds and query sizes."""
from __future__ import annotations

import argparse
import json
import statistics

from prototype.e01_ood_composition import run_ood_experiment


def summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def run_multiseed(seed_count: int = 5, start_seed: int = 7) -> dict:
    if seed_count < 1:
        raise ValueError("seed_count must be at least 1")
    experiments = {}
    for cardinality in (2, 3):
        runs = [
            run_ood_experiment(
                seed=start_seed + offset,
                test_query_cardinality=cardinality,
            )
            for offset in range(seed_count)
        ]
        methods = runs[0]["metrics"].keys()
        metric_names = runs[0]["metrics"]["learned_ranker"].keys()
        experiments[str(cardinality)] = {
            "per_seed": runs,
            "aggregate": {
                method: {
                    metric: summary([run["metrics"][method][metric] for run in runs])
                    for metric in metric_names
                }
                for method in methods
            },
        }
    return {
        "experiment": "E01-C-compositional-OOD-multiseed",
        "seeds": [start_seed + offset for offset in range(seed_count)],
        "train_query_cardinality": 1,
        "train_samples_per_seed": 1600,
        "test_samples_per_seed": 500,
        "candidate_count": 7,
        "feature_dim": 6,
        "test_query_cardinalities": [2, 3],
        "experiments": experiments,
        "limitations": [
            "Synthetic binary-attribute conjunction task",
            "Does not test natural-language parsing",
            "Does not test dynamic hypergraph learning",
            "The additive compatibility rule is intentionally simple",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_multiseed(args.seeds, args.start_seed)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
