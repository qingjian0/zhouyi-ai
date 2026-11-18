"""Run E01-B across multiple deterministic seeds and summarize metrics."""
from __future__ import annotations

import argparse
import json
import statistics

from prototype.e01_learned_ranker import run_experiment


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def run_multiseed(seed_count: int = 5, start_seed: int = 7) -> dict:
    if seed_count < 1:
        raise ValueError("seed_count must be at least 1")
    runs = [run_experiment(seed=start_seed + offset) for offset in range(seed_count)]
    methods = runs[0]["metrics"].keys()
    metric_names = runs[0]["metrics"]["learned_ranker"].keys()
    aggregate = {
        method: {
            metric: summarize([run["metrics"][method][metric] for run in runs])
            for metric in metric_names
        }
        for method in methods
    }
    return {
        "experiment": "E01-B-multiseed",
        "seed_count": seed_count,
        "seeds": [start_seed + offset for offset in range(seed_count)],
        "per_seed": runs,
        "aggregate": aggregate,
        "protocol": {
            "train_samples_per_seed": 1200,
            "test_samples_per_seed": 400,
            "candidate_count": 7,
            "feature_dim": 6,
            "selected_per_example": 3,
            "training_epochs": 180,
            "model": "linear logistic scorer over query-elementwise-feature interactions",
        },
        "limitations": [
            "Synthetic controlled task only",
            "No natural-language parsing",
            "No dynamic hypergraph learning",
            "No comparison with Transformer or diffusion models",
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
