"""N0.11: higher-order cyclic composition under held-out phase-region shift.

Three independent phases compose by addition on the circle. The binary target
is cos(a+b+c) > 0. Training excludes a contiguous region of role A's phase;
testing uses only that unseen region. A Fourier/tensor-product encoding makes
the third-order interaction explicit. This is a controlled compositional OOD
diagnostic, not a natural-language benchmark or a claim of general reasoning.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from statistics import mean, stdev

from prototype.n09_learnable_srok import (
    LabeledStructure,
    LearnableSROK,
    Node,
    RoleSpec,
)

TAU = 2.0 * math.pi
ROLE_NAMES = ("phase_a", "phase_b", "phase_c")


def _role_features(angle: float, role_index: int) -> tuple[float, ...]:
    """Rank-4 factorization of cos(a+b+c), plus a constant bias coordinate."""
    cosine, sine = math.cos(angle), math.sin(angle)
    if role_index == 0:
        return (cosine, cosine, sine, sine, 1.0)
    if role_index == 1:
        return (cosine, sine, cosine, sine, 1.0)
    if role_index == 2:
        return (cosine, sine, sine, cosine, 1.0)
    raise ValueError("role_index must be 0, 1, or 2")


def make_dataset(count: int, seed: int, split: str) -> list[LabeledStructure]:
    """Generate disjoint phase regions: train A in [pi/2, 2pi), test A in [0, pi/2)."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if split not in ("train", "test"):
        raise ValueError("split must be 'train' or 'test'")
    rng = random.Random(seed)
    rows = []
    while len(rows) < count:
        angles = (rng.random() * TAU, rng.random() * TAU, rng.random() * TAU)
        held_out_region = angles[0] < math.pi / 2.0
        if (split == "test") != held_out_region:
            continue
        assignment = tuple(
            Node(
                node_id=f"{seed}-{len(rows)}-{role}",
                node_type=role,
                features=_role_features(angle, index),
                evidence_ids=(f"n11-{seed}-{len(rows)}-{role}",),
            )
            for index, (role, angle) in enumerate(zip(ROLE_NAMES, angles))
        )
        label = int(math.cos(sum(angles)) > 0.0)
        rows.append(LabeledStructure(assignment=assignment, label=label))
    return rows


def evaluate(
    model: LearnableSROK,
    data: list[LabeledStructure],
    max_order: int,
) -> dict[str, float]:
    if not data:
        raise ValueError("evaluation data must not be empty")
    tp = tn = fp = fn = 0
    total_bce = 0.0
    for row in data:
        prediction, logit = model.predict_binary(row.assignment, max_order=max_order)
        if prediction == 1 and row.label == 1:
            tp += 1
        elif prediction == 0 and row.label == 0:
            tn += 1
        elif prediction == 1:
            fp += 1
        else:
            fn += 1
        total_bce += (
            max(logit, 0.0) - logit * row.label
            + math.log1p(math.exp(-abs(logit)))
        )
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "accuracy": (tp + tn) / len(data),
        "balanced_accuracy": (sensitivity + specificity) / 2.0,
        "mean_bce": total_bce / len(data),
        "positive_rate": (tp + fn) / len(data),
    }


def run_seed(
    seed: int,
    train_count: int = 3000,
    test_count: int = 1500,
    epochs: int = 120,
) -> dict:
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    roles = tuple(RoleSpec(name, frozenset({name})) for name in ROLE_NAMES)
    train = make_dataset(train_count, seed * 1009 + 17, "train")
    test = make_dataset(test_count, seed * 1009 + 29, "test")
    models = {}
    for order in (1, 2, 3):
        model = LearnableSROK(roles, feature_dim=5)
        model.fit_binary(
            train,
            max_order=order,
            epochs=epochs,
            learning_rate=0.15,
            l2=1e-3,
        )
        models[order] = model
    return {
        "seed": seed,
        "data_seeds": {"train": seed * 1009 + 17, "test": seed * 1009 + 29},
        "train_examples": train_count,
        "test_examples": test_count,
        "epochs": epochs,
        "parameter_counts": {
            "unary_active": 15,
            "unary_pairwise_active": 30,
            "unary_pairwise_triple_active": 35,
            "full_model_total": 35,
        },
        "unary_only": evaluate(models[1], test, 1),
        "unary_pairwise": evaluate(models[2], test, 2),
        "unary_pairwise_triple": evaluate(models[3], test, 3),
        "triple_model_after_triple_mask": evaluate(models[3], test, 2),
    }


def run(
    seed_count: int = 5,
    start_seed: int = 7,
    train_count: int = 3000,
    test_count: int = 1500,
    epochs: int = 120,
) -> dict:
    if isinstance(seed_count, bool) or not isinstance(seed_count, int) or seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    results = [
        run_seed(start_seed + offset, train_count, test_count, epochs)
        for offset in range(seed_count)
    ]
    metrics = (
        "unary_only",
        "unary_pairwise",
        "unary_pairwise_triple",
        "triple_model_after_triple_mask",
    )
    summary = {}
    for key in metrics:
        for metric in ("accuracy", "balanced_accuracy", "mean_bce", "positive_rate"):
            values = [row[key][metric] for row in results]
            summary[f"{key}.{metric}"] = {
                "mean": mean(values),
                "sample_stddev": stdev(values),
            }
    return {
        "experiment": "N0.11-cyclic-composition-phase-region-OOD-v1",
        "target": "1[cos(a+b+c) > 0]",
        "distribution_shift": {
            "train_role_a_phase": "[pi/2, 2*pi)",
            "test_role_a_phase": "[0, pi/2)",
            "role_b_phase": "[0, 2*pi) in both splits",
            "role_c_phase": "[0, 2*pi) in both splits",
            "train_test_role_a_regions_are_disjoint": True,
        },
        "encoding": (
            "Five-dimensional role-specific Fourier factors. The four "
            "third-order products factor cos(a+b+c); the fifth coordinate "
            "provides a constant bias. This is an explicit compositional prior."
        ),
        "seed_count": seed_count,
        "configuration": {
            "start_seed": start_seed,
            "train_count": train_count,
            "test_count": test_count,
            "epochs": epochs,
            "feature_dim": 5,
        },
        "summary": summary,
        "per_seed": results,
        "limitations": [
            "Synthetic continuous-phase task with a known analytic target.",
            "The Fourier factorization is supplied as an inductive bias; this does not discover the representation from raw data.",
            "The OOD shift holds out a phase region for one role, not an unseen semantic rule family.",
            "The ablations share one model family but are not parameter-matched to MLP, GNN, or Transformer baselines.",
            "No natural-language, causal, or general-intelligence claim is supported.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=3000)
    parser.add_argument("--test-samples", type=int, default=1500)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(
        args.seeds, args.start_seed, args.train_samples,
        args.test_samples, args.epochs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
