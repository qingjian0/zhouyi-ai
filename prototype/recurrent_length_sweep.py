"""Held-out distractor-length sweep for P5-B recurrent mechanisms."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from statistics import fmean, pstdev

from prototype.recurrent_benchmark import BenchmarkConfig, run_benchmark


def run_length_sweep(
    config: BenchmarkConfig,
    eval_gap_lengths: tuple[int, ...] = (4, 8, 16, 32, 64, 128),
    seeds: tuple[int, ...] | None = None,
) -> dict:
    if config.task not in ("delayed_copy", "distractor_recall"):
        raise ValueError("length sweep requires delayed_copy or distractor_recall")
    if not eval_gap_lengths:
        raise ValueError("eval_gap_lengths must be non-empty")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in eval_gap_lengths):
        raise ValueError("all evaluation gap lengths must be positive integers")
    if len(set(eval_gap_lengths)) != len(eval_gap_lengths):
        raise ValueError("evaluation gap lengths must be unique")

    all_results = []
    for gap in eval_gap_lengths:
        report = run_benchmark(
            replace(config, eval_gap_length=gap),
            seeds=seeds,
        )
        for row in report["results"]:
            all_results.append({
                "eval_gap_length": gap,
                **row,
            })

    model_names = sorted({row["model"] for row in all_results})
    summaries = []
    for model in model_names:
        for gap in eval_gap_lengths:
            rows = [
                row for row in all_results
                if row["model"] == model and row["eval_gap_length"] == gap
            ]
            accuracies = [row["accuracy"] for row in rows]
            losses = [row["binary_cross_entropy"] for row in rows]
            summaries.append({
                "model": model,
                "eval_gap_length": gap,
                "seeds": len(rows),
                "accuracy_mean": fmean(accuracies),
                "accuracy_population_stddev": pstdev(accuracies),
                "binary_cross_entropy_mean": fmean(losses),
                "chunk_state_parity_all": all(row["chunk_state_parity"] for row in rows),
                "parameter_counts": sorted({row["parameter_count"] for row in rows}),
            })

    return {
        "schema_version": 1,
        "scope": "synthetic_binary_recurrent_heldout_length_sweep",
        "claim_boundary": (
            "Synthetic delayed-copy/distractor recall only; not natural language, "
            "not million-token context, and not mobile feasibility."
        ),
        "config": asdict(config),
        "eval_gap_lengths": list(eval_gap_lengths),
        "seeds": list(seeds or (config.seed, config.seed + 1, config.seed + 2)),
        "summary": summaries,
        "raw_results": all_results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("delayed_copy", "distractor_recall"),
                        default="delayed_copy")
    parser.add_argument("--train-examples", type=int, default=128)
    parser.add_argument("--eval-examples", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--payload-length", type=int, default=5)
    parser.add_argument("--train-gap-length", type=int, default=16)
    parser.add_argument("--eval-gap-lengths", default="4,8,16,32,64,128")
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        lengths = tuple(int(part.strip()) for part in args.eval_gap_lengths.split(","))
    except ValueError as exc:
        parser.error(f"invalid --eval-gap-lengths: {exc}")
    config = BenchmarkConfig(
        task=args.task,
        train_examples=args.train_examples,
        eval_examples=args.eval_examples,
        epochs=args.epochs,
        seed=args.seed,
        payload_length=args.payload_length,
        gap_length=args.train_gap_length,
        learning_rate=args.learning_rate,
    )
    report = run_length_sweep(config, lengths)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output == "-":
        print(rendered)
    else:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
