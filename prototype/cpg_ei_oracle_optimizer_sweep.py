"""Known-support CPG-EI optimizer sweep on finite parity rule families.

This diagnostic isolates optimizer/regularization behavior from support search.
The true support is supplied to the model, but all fitting uses train states only.
Locked states are never used for gradient updates or hyperparameter selection.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from typing import Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, FEATURE_NAMES, evaluate
from prototype.cpg_ei_selection_sweep import RULE_FAMILIES, make_examples, partition_states, exact_support

DEFAULT_SEEDS = (11, 47)
DEFAULT_LEARNING_RATES = (0.05, 0.15, 0.35, 0.7)
REGULARIZERS = {
    "default": {"l2": 1e-4, "gate_l1": 1e-4, "edge_group_l1": 0.0},
    "search": {"l2": 1e-4, "gate_l1": 1e-3, "edge_group_l1": 1e-3},
}


def run_optimizer_sweep(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    learning_rates: Sequence[float] = DEFAULT_LEARNING_RATES,
    epochs: int = 800,
) -> dict:
    if not seeds or not learning_rates or epochs < 1:
        raise ValueError("seeds, learning_rates, and epochs must be non-empty/positive")
    if any(not math.isfinite(rate) or rate <= 0.0 for rate in learning_rates):
        raise ValueError("learning rates must be finite and positive")
    if len(set(learning_rates)) != len(learning_rates):
        raise ValueError("learning rates must be unique")

    records = []
    all_states = tuple(itertools.product((0, 1), repeat=6))
    for seed in seeds:
        train_states, _, locked_states = partition_states(seed)
        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            locked = make_examples(locked_states, triples)
            full = make_examples(all_states, triples)
            support_indices = {
                FEATURE_NAMES.index(name) for name in exact_support(triples)
            }
            for regularizer, penalties in REGULARIZERS.items():
                for learning_rate in learning_rates:
                    model = CpgEiTransitionModel.create(
                        active_relation_indices=support_indices
                    )
                    losses = model.train(
                        train,
                        epochs=epochs,
                        learning_rate=learning_rate,
                        **penalties,
                    )
                    train_metrics = evaluate(model, train)
                    locked_metrics = evaluate(model, locked)
                    full_metrics = evaluate(model, full)
                    record = {
                        "seed": seed,
                        "family": family,
                        "regularizer": regularizer,
                        "learning_rate": learning_rate,
                        "epochs": epochs,
                        "train_bit_accuracy": train_metrics["bit_accuracy"],
                        "locked_bit_accuracy": locked_metrics["bit_accuracy"],
                        "full_64_state_bit_accuracy": full_metrics["bit_accuracy"],
                        "final_train_bce": losses[-1],
                        "initial_train_bce": losses[0],
                        "support_source": "oracle_known_support",
                        "gradient_data": "train_40_only",
                        "locked_examples": len(locked),
                    }
                    numeric = [
                        record[key] for key in (
                            "train_bit_accuracy", "locked_bit_accuracy",
                            "full_64_state_bit_accuracy", "final_train_bce",
                            "initial_train_bce",
                        )
                    ]
                    if not all(math.isfinite(value) for value in numeric):
                        raise AssertionError("non-finite optimizer sweep metric")
                    records.append(record)

    grouped = defaultdict(list)
    for row in records:
        grouped[(row["regularizer"], row["learning_rate"])].append(row)
    summary = []
    for (regularizer, learning_rate), rows in sorted(grouped.items()):
        summary.append({
            "regularizer": regularizer,
            "learning_rate": learning_rate,
            "experiments": len(rows),
            "mean_train_bit_accuracy": sum(r["train_bit_accuracy"] for r in rows) / len(rows),
            "mean_locked_bit_accuracy": sum(r["locked_bit_accuracy"] for r in rows) / len(rows),
            "mean_full_64_state_bit_accuracy": sum(r["full_64_state_bit_accuracy"] for r in rows) / len(rows),
            "mean_final_train_bce": sum(r["final_train_bce"] for r in rows) / len(rows),
        })
    best_locked = max(summary, key=lambda row: (row["mean_locked_bit_accuracy"], -row["mean_final_train_bce"]))
    best_full = max(summary, key=lambda row: (row["mean_full_64_state_bit_accuracy"], -row["mean_final_train_bce"]))
    return {
        "benchmark": "cpg-ei-known-support-optimizer-sweep-v1",
        "seeds": list(seeds),
        "families": list(RULE_FAMILIES),
        "train_examples": 40,
        "locked_test_examples": 12,
        "epochs": epochs,
        "learning_rates": list(learning_rates),
        "regularizers": REGULARIZERS,
        "summary": summary,
        "best_locked_config": best_locked,
        "best_full_64_state_config": best_full,
        "records": records,
        "claim_boundary": (
            "Synthetic six-bit parity diagnostic with oracle-supplied support. "
            "No open-world relation discovery, language reasoning, or production "
            "training-readiness claim."
        ),
    }


def _ints(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return result


def _floats(value: str) -> tuple[float, ...]:
    try:
        result = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not result or any(not math.isfinite(x) or x <= 0 for x in result):
        raise argparse.ArgumentTypeError("learning rates must be positive finite numbers")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_ints, default=DEFAULT_SEEDS)
    parser.add_argument("--learning-rates", type=_floats, default=DEFAULT_LEARNING_RATES)
    parser.add_argument("--epochs", type=int, default=800)
    args = parser.parse_args(argv)
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    report = run_optimizer_sweep(
        seeds=args.seeds, learning_rates=args.learning_rates, epochs=args.epochs
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
