"""Known-support CPG-EI optimizer sweep on finite parity rule families.

This diagnostic isolates optimizer/regularization behavior from support search.
The true support is supplied to the model, but all fitting uses train states only.
Locked states are evaluation-only and never select a configuration.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from typing import Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, FEATURE_NAMES, evaluate
from prototype.cpg_ei_selection_sweep import RULE_FAMILIES, make_examples, partition_states, exact_support

DEFAULT_SEEDS = (11, 47)
DEFAULT_LEARNING_RATES = (0.05, 0.15, 0.35, 0.7)
REGULARIZERS = {
    "default": {"l2": 1e-4, "gate_l1": 1e-4, "edge_group_l1": 0.0},
    "search": {"l2": 1e-4, "gate_l1": 1e-3, "edge_group_l1": 1e-3},
}


def _mean_bce(model: CpgEiTransitionModel, examples) -> float:
    """Evaluate mean BCE on the supplied rows using the model's current weights."""
    rows = list(examples)
    if not rows:
        raise ValueError("evaluation data must not be empty")
    total = 0.0
    for row in rows:
        for logit, label in zip(model.logits(row.state), row.target):
            total += max(logit, 0.0) - logit * label + math.log1p(math.exp(-abs(logit)))
    return total / (len(rows) * 6.0)


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
                    initial_train_bce = _mean_bce(model, train)
                    model.train(
                        train,
                        epochs=epochs,
                        learning_rate=learning_rate,
                        **penalties,
                    )
                    # Re-evaluate after the final update. The optimizer's per-epoch
                    # trace is accumulated during the update pass and is not a
                    # post-update objective for the resulting model parameters.
                    final_train_bce = _mean_bce(model, train)
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
                        "final_train_bce": final_train_bce,
                        "initial_train_bce": initial_train_bce,
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

    # Configuration selection is train-only. Locked and full-domain metrics are
    # reported for diagnosis, never used to rank or choose hyperparameters.
    best_train_config = min(
        summary,
        key=lambda row: (
            row["mean_final_train_bce"],
            -row["mean_train_bit_accuracy"],
            row["regularizer"],
            row["learning_rate"],
        ),
    )
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
        "best_train_config": best_train_config,
        "records": records,
        "selection_metric": "mean_final_train_bce_only",
        "locked_and_full_metrics_used_for_selection": False,
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
