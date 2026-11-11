"""N0.10 higher-order-necessary parity benchmark and attribution audit.

Each role contributes one independent Rademacher feature. The target is the
three-way parity x0*x1*x2. Unary and pairwise feature marginals are independent
of the label; only the explicit triple interaction identifies it. This is a
controlled mechanism diagnostic, not a natural-language or real-world benchmark.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from itertools import product
from statistics import mean, stdev

from prototype.n09_learnable_srok import (
    LabeledStructure,
    LearnableSROK,
    Node,
    RoleSpec,
)


def make_dataset(count: int, seed: int) -> list[LabeledStructure]:
    if (isinstance(count, bool) or not isinstance(count, int)
            or count < 1 or count % 8 != 0):
        raise ValueError("count must be a positive multiple of 8")
    rng = random.Random(seed)
    roles = ("r0", "r1", "r2")
    patterns = list(product((-1.0, 1.0), repeat=3))
    values_list = []
    while len(values_list) < count:
        cycle = list(patterns)
        rng.shuffle(cycle)
        values_list.extend(cycle)
    data = []
    for index, values in enumerate(values_list[:count]):
        assignment = tuple(
            Node(
                node_id=f"{seed}-{index}-{role}",
                node_type=role,
                features=(value,),
                evidence_ids=(f"ev-{seed}-{index}-{role}",),
            )
            for role, value in zip(roles, values)
        )
        label = 1 if values[0] * values[1] * values[2] > 0 else 0
        data.append(LabeledStructure(assignment=assignment, label=label))
    return data


def evaluate(model: LearnableSROK, data: list[LabeledStructure],
             max_order: int) -> dict[str, float]:
    correct = 0
    total_loss = 0.0
    for row in data:
        prediction, logit = model.predict_binary(
            row.assignment, max_order=max_order
        )
        correct += int(prediction == row.label)
        # Numerically stable binary cross-entropy from the raw logit.
        total_loss += (
            max(logit, 0.0) - logit * row.label
            + math.log1p(math.exp(-abs(logit)))
        )
    return {
        "accuracy": correct / len(data),
        "mean_bce": total_loss / len(data),
    }


def run_seed(seed: int, train_count: int = 3000, test_count: int = 1504,
             epochs: int = 120) -> dict:
    roles = tuple(
        RoleSpec(name, frozenset({name}))
        for name in ("r0", "r1", "r2")
    )
    train = make_dataset(train_count, seed * 1009 + 17)
    test = make_dataset(test_count, seed * 1009 + 29)
    models = {}
    for order in (1, 2, 3):
        model = LearnableSROK(roles, feature_dim=1)
        model.fit_binary(
            train, max_order=order, epochs=epochs,
            learning_rate=0.15, l2=1e-3,
        )
        models[order] = model
    return {
        "seed": seed,
        "data_seeds": {
            "train": seed * 1009 + 17,
            "test": seed * 1009 + 29,
        },
        "train_examples": train_count,
        "test_examples": test_count,
        "epochs": epochs,
        "active_parameter_counts": {
            "unary": 3,
            "pairwise": 6,
            "third_order": 7,
        },
        "unary_only": evaluate(models[1], test, 1),
        "unary_pairwise": evaluate(models[2], test, 2),
        "unary_pairwise_triple": evaluate(models[3], test, 3),
        # Attribution intervention: retain the trained unary and pairwise
        # contributions, mask only the explicit third-order feature block.
        "triple_model_after_triple_mask": evaluate(models[3], test, 2),
        "final_train_bce": {
            "unary": history_loss(models[1], train, 1),
            "pairwise": history_loss(models[2], train, 2),
            "third_order": history_loss(models[3], train, 3),
        },
    }


def history_loss(model: LearnableSROK, data: list[LabeledStructure],
                 max_order: int) -> float:
    total = 0.0
    for row in data:
        _, logit = model.predict_binary(row.assignment, max_order=max_order)
        total += (
            max(logit, 0.0) - logit * row.label
            + math.log1p(math.exp(-abs(logit)))
        )
    return total / len(data)


def run(seed_count: int = 5, start_seed: int = 7,
        train_count: int = 3000, test_count: int = 1504,
        epochs: int = 120) -> dict:
    if isinstance(seed_count, bool) or not isinstance(seed_count, int) or seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    results = [
        run_seed(start_seed + offset, train_count, test_count, epochs)
        for offset in range(seed_count)
    ]
    metric_keys = (
        "unary_only", "unary_pairwise", "unary_pairwise_triple",
        "triple_model_after_triple_mask",
    )
    summary = {}
    for key in metric_keys:
        for metric in ("accuracy", "mean_bce"):
            values = [row[key][metric] for row in results]
            summary[f"{key}.{metric}"] = {
                "mean": mean(values),
                "sample_stddev": stdev(values),
            }
    return {
        "experiment": "N0.10-higher-order-necessary-parity-v1",
        "task": "three-way parity; label = x0*x1*x2",
        "seed_count": seed_count,
        "configuration": {
            "start_seed": start_seed,
            "train_count": train_count,
            "test_count": test_count,
            "epochs": epochs,
        },
        "summary": summary,
        "per_seed": results,
        "attribution": (
            "Unary and pairwise models are tested on independent random data. "
            "The triple model is additionally evaluated with only its triple "
            "feature block masked; unary and pairwise contributions remain intact."
        ),
        "limitations": [
            "Synthetic IID mechanism diagnostic with a known parity rule.",
            "Does not establish open-ended higher-order reasoning or semantic understanding.",
            "Does not establish superiority over parameter-matched MLP/Graph/Hypergraph baselines.",
            "The same task family is used across seeds; this is not rule-family OOD.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=3000)
    parser.add_argument("--test-samples", type=int, default=1504)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seeds, args.start_seed, args.train_samples,
                 args.test_samples, args.epochs)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
