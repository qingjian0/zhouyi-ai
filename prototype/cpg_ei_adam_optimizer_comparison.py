"""Compare SGD and Adam on oracle-known CPG-EI parity support.

Five seeds and three finite parity families are used. Only the 40 training
states update parameters. Locked states are evaluation-only and never rank
optimizer configurations. The true support is supplied to isolate optimization.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from typing import Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, FEATURE_NAMES, evaluate
from prototype.cpg_ei_selection_sweep import (
    RULE_FAMILIES,
    exact_support,
    make_examples,
    partition_states,
)

DEFAULT_SEEDS = (11, 23, 47, 89, 131)
SGD_RATES = (2.1, 4.2, 6.0, 12.0)
ADAM_RATES = (0.003, 0.01, 0.03, 0.1)
REGULARIZERS = {
    "default": {"l2": 1e-4, "gate_l1": 1e-4, "edge_group_l1": 0.0},
    "search": {"l2": 1e-4, "gate_l1": 1e-3, "edge_group_l1": 1e-3},
}


def mean_bce(model: CpgEiTransitionModel, rows) -> float:
    examples = tuple(rows)
    if not examples:
        raise ValueError("evaluation rows must not be empty")
    total = 0.0
    for row in examples:
        for logit, label in zip(model.logits(row.state), row.target):
            total += max(logit, 0.0) - logit * label + math.log1p(math.exp(-abs(logit)))
    return total / (len(examples) * 6.0)


def run_comparison(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    epochs: int = 800,
    sgd_rates: Sequence[float] = SGD_RATES,
    adam_rates: Sequence[float] = ADAM_RATES,
) -> dict:
    if not seeds or epochs < 1 or not sgd_rates or not adam_rates:
        raise ValueError("seeds, rates and positive epochs are required")
    for rates in (sgd_rates, adam_rates):
        if any(not math.isfinite(rate) or rate <= 0 for rate in rates):
            raise ValueError("learning rates must be positive finite numbers")
        if len(set(rates)) != len(rates):
            raise ValueError("learning rates must be unique within each optimizer")

    all_states = tuple(itertools.product((0, 1), repeat=6))
    records = []
    configurations = (
        [("sgd", rate) for rate in sgd_rates]
        + [("adam", rate) for rate in adam_rates]
    )
    for seed in seeds:
        train_states, _, locked_states = partition_states(seed)
        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            locked = make_examples(locked_states, triples)
            full = make_examples(all_states, triples)
            support = {
                FEATURE_NAMES.index(name) for name in exact_support(triples)
            }
            for regularizer, penalties in REGULARIZERS.items():
                for optimizer, rate in configurations:
                    model = CpgEiTransitionModel.create(
                        active_relation_indices=support
                    )
                    initial_bce = mean_bce(model, train)
                    model.train(
                        train,
                        epochs=epochs,
                        learning_rate=rate,
                        optimizer=optimizer,
                        **penalties,
                    )
                    row = {
                        "seed": seed,
                        "family": family,
                        "regularizer": regularizer,
                        "optimizer": optimizer,
                        "learning_rate": rate,
                        "epochs": epochs,
                        "initial_train_bce": initial_bce,
                        "final_train_bce": mean_bce(model, train),
                        "train_bit_accuracy": evaluate(model, train)["bit_accuracy"],
                        "locked_bit_accuracy": evaluate(model, locked)["bit_accuracy"],
                        "full_64_state_bit_accuracy": evaluate(model, full)["bit_accuracy"],
                        "support_source": "oracle_known_support",
                        "gradient_data": "train_40_only",
                        "locked_examples": len(locked),
                    }
                    metrics = (
                        row["initial_train_bce"], row["final_train_bce"],
                        row["train_bit_accuracy"], row["locked_bit_accuracy"],
                        row["full_64_state_bit_accuracy"],
                    )
                    if not all(math.isfinite(value) for value in metrics):
                        raise AssertionError("non-finite optimizer comparison metric")
                    records.append(row)

    grouped = defaultdict(list)
    for row in records:
        grouped[(row["optimizer"], row["learning_rate"], row["regularizer"])].append(row)
    summary = []
    for (optimizer, rate, regularizer), rows in sorted(grouped.items()):
        summary.append({
            "optimizer": optimizer,
            "learning_rate": rate,
            "regularizer": regularizer,
            "experiments": len(rows),
            "mean_final_train_bce": sum(x["final_train_bce"] for x in rows) / len(rows),
            "mean_train_bit_accuracy": sum(x["train_bit_accuracy"] for x in rows) / len(rows),
            "mean_locked_bit_accuracy": sum(x["locked_bit_accuracy"] for x in rows) / len(rows),
            "mean_full_64_state_bit_accuracy": sum(x["full_64_state_bit_accuracy"] for x in rows) / len(rows),
        })

    best_train_config = min(
        summary,
        key=lambda x: (
            x["mean_final_train_bce"],
            -x["mean_train_bit_accuracy"],
            x["optimizer"],
            x["regularizer"],
            x["learning_rate"],
        ),
    )
    return {
        "benchmark": "cpg-ei-known-support-sgd-vs-adam-v1",
        "seeds": list(seeds),
        "families": list(RULE_FAMILIES),
        "train_examples": 40,
        "locked_test_examples": 12,
        "epochs": epochs,
        "sgd_rates": list(sgd_rates),
        "adam_rates": list(adam_rates),
        "regularizers": REGULARIZERS,
        "summary": summary,
        "best_train_config": best_train_config,
        "records": records,
        "selection_metric": "mean_final_train_bce_only",
        "locked_and_full_metrics_used_for_selection": False,
        "claim_boundary": (
            "Synthetic six-bit parity diagnostic with oracle-supplied support; "
            "does not establish open-world relation discovery or language reasoning."
        ),
    }


def _ints(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_ints, default=DEFAULT_SEEDS)
    parser.add_argument("--epochs", type=int, default=800)
    args = parser.parse_args(argv)
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    print(json.dumps(
        run_comparison(seeds=args.seeds, epochs=args.epochs),
        ensure_ascii=False, sort_keys=True, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
