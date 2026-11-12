"""N0.13 robustness sweep across held-out phase windows and semantic roles.

This extends N0.11 beyond one fixed phase interval. For each of three roles
and four disjoint quarter-circle windows, train/validation exclude that
role-window and test contains only it. Compare unary, pairwise, and triple
SROK feature orders over multiple seeds.
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
from prototype.n11_cyclic_composition_ood import (
    ROLE_NAMES,
    _role_features,
    evaluate,
    _validation_sign,
)

TAU = 2.0 * math.pi
WINDOW_STARTS = (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0)


def make_dataset(
    count: int,
    seed: int,
    split: str,
    heldout_role: int,
    heldout_start: float,
    heldout_width: float = math.pi / 2.0,
) -> list[LabeledStructure]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if split not in ("train", "validation", "test"):
        raise ValueError("split must be train, validation, or test")
    if (isinstance(heldout_role, bool) or not isinstance(heldout_role, int)
            or heldout_role not in (0, 1, 2)):
        raise ValueError("heldout_role must be 0, 1, or 2")
    if not math.isfinite(heldout_start):
        raise ValueError("heldout_start must be finite")
    if not math.isfinite(heldout_width) or not 0.0 < heldout_width < TAU:
        raise ValueError("heldout_width must be between 0 and 2*pi")
    start = heldout_start % TAU
    rng = random.Random(seed)
    rows = []
    while len(rows) < count:
        angles = tuple(rng.random() * TAU for _ in range(3))
        offset = (angles[heldout_role] - start) % TAU
        in_heldout_window = offset < heldout_width
        if (split == "test") != in_heldout_window:
            continue
        index = len(rows)
        assignment = tuple(
            Node(
                node_id=f"{seed}-{index}-{role}",
                node_type=role,
                features=_role_features(angle, role_index),
                evidence_ids=(f"n13-{seed}-{index}-{role}",),
            )
            for role_index, (role, angle) in enumerate(zip(ROLE_NAMES, angles))
        )
        rows.append(LabeledStructure(
            assignment=assignment,
            label=int(math.cos(sum(angles)) > 0.0),
        ))
    return rows


def run_condition(
    seed: int,
    heldout_role: int,
    heldout_start: float,
    train_count: int = 600,
    validation_count: int = 300,
    test_count: int = 300,
    epochs: int = 80,
) -> dict:
    train = make_dataset(
        train_count, seed * 1009 + 17, "train", heldout_role, heldout_start
    )
    validation = make_dataset(
        validation_count, seed * 1009 + 23, "validation",
        heldout_role, heldout_start,
    )
    test = make_dataset(
        test_count, seed * 1009 + 29, "test", heldout_role, heldout_start
    )
    roles = tuple(RoleSpec(name, frozenset({name})) for name in ROLE_NAMES)
    models = {}
    signs = {}
    validation_results = {}
    for order in (1, 2, 3):
        model = LearnableSROK(roles, feature_dim=5)
        model.fit_binary(
            train, max_order=order, epochs=epochs,
            learning_rate=0.15, l2=1e-3,
        )
        sign, val_result = _validation_sign(model, validation, order)
        models[order] = model
        signs[order] = sign
        validation_results[order] = val_result
    return {
        "seed": seed,
        "heldout_role": ROLE_NAMES[heldout_role],
        "heldout_role_index": heldout_role,
        "heldout_start_radians": heldout_start,
        "train_examples": train_count,
        "validation_examples": validation_count,
        "test_examples": test_count,
        "epochs": epochs,
        "validation": {
            "unary": validation_results[1],
            "pairwise": validation_results[2],
            "triple": validation_results[3],
        },
        "validation_logit_sign": {
            "unary": signs[1], "pairwise": signs[2], "triple": signs[3],
        },
        "unary_only": evaluate(models[1], test, 1, signs[1]),
        "unary_pairwise": evaluate(models[2], test, 2, signs[2]),
        "unary_pairwise_triple": evaluate(models[3], test, 3, signs[3]),
        "triple_model_after_triple_mask": evaluate(models[3], test, 2, signs[3]),
    }


def _metric_summary(rows: list[dict], key: str) -> dict:
    values = [row[key]["accuracy"] for row in rows]
    return {
        "accuracy_mean": mean(values),
        "accuracy_sample_stddev": stdev(values) if len(values) > 1 else 0.0,
        "balanced_accuracy_mean": mean(
            row[key]["balanced_accuracy"] for row in rows
        ),
    }


def run(
    seeds: int = 3,
    start_seed: int = 7,
    train_count: int = 600,
    validation_count: int = 300,
    test_count: int = 300,
    epochs: int = 80,
) -> dict:
    if isinstance(seeds, bool) or not isinstance(seeds, int) or seeds < 2:
        raise ValueError("seeds must be at least 2")
    conditions = []
    per_seed = []
    for role_index in range(3):
        for window_index, window_start in enumerate(WINDOW_STARTS):
            rows = [
                run_condition(
                    start_seed + seed_offset,
                    role_index,
                    window_start,
                    train_count,
                    validation_count,
                    test_count,
                    epochs,
                )
                for seed_offset in range(seeds)
            ]
            per_seed.extend(rows)
            conditions.append({
                "heldout_role": ROLE_NAMES[role_index],
                "heldout_start_radians": window_start,
                "seed_count": seeds,
                "unary": _metric_summary(rows, "unary_only"),
                "pairwise": _metric_summary(rows, "unary_pairwise"),
                "triple": _metric_summary(rows, "unary_pairwise_triple"),
                "triple_masked": _metric_summary(
                    rows, "triple_model_after_triple_mask"
                ),
            })
    return {
        "experiment": "N0.13-phase-window-role-robustness-v1",
        "target": "1[cos(a+b+c) > 0]",
        "condition_count": len(conditions),
        "seed_count_per_condition": seeds,
        "total_runs": len(per_seed),
        "configuration": {
            "start_seed": start_seed,
            "train_count": train_count,
            "validation_count": validation_count,
            "test_count": test_count,
            "epochs": epochs,
            "heldout_width_radians": math.pi / 2.0,
            "heldout_roles": list(ROLE_NAMES),
            "heldout_window_starts": list(WINDOW_STARTS),
        },
        "condition_summary": conditions,
        "overall": {
            "unary": _metric_summary(per_seed, "unary_only"),
            "pairwise": _metric_summary(per_seed, "unary_pairwise"),
            "triple": _metric_summary(per_seed, "unary_pairwise_triple"),
            "triple_masked": _metric_summary(
                per_seed, "triple_model_after_triple_mask"
            ),
            "minimum_condition_triple_accuracy": min(
                row["triple"]["accuracy_mean"] for row in conditions
            ),
        },
        "per_seed": per_seed,
        "limitations": [
            "Synthetic analytic phase-composition task; the target rule is known.",
            "Fourier/tensor-product representation is supplied as an inductive bias.",
            "The sweep varies one role and one quarter-circle region at a time; it is not semantic rule-family OOD.",
            "Three seeds per condition are a robustness screen, not a precise population estimate.",
            "No natural-language or general-intelligence claim is supported.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=600)
    parser.add_argument("--validation-samples", type=int, default=300)
    parser.add_argument("--test-samples", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(
        args.seeds, args.start_seed, args.train_samples,
        args.validation_samples, args.test_samples, args.epochs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
