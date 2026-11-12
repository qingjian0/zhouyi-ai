"""N0.14: a compact learnable-frequency cyclic composition operator.

The model receives raw role phases recovered from the same N0.11 examples. It
uses a known rank-4 trigonometric tensor factorization, but learns the shared
frequency and four composition coefficients end-to-end. This is a structured
operator-learning diagnostic, not a raw-data representation learner.
"""
from __future__ import annotations

import argparse
import json
import math
from statistics import mean, stdev

from prototype.n09_learnable_srok import LearnableSROK, RoleSpec
from prototype.n11_cyclic_composition_ood import (
    ROLE_NAMES,
    evaluate as evaluate_srok,
    make_dataset,
    _validation_sign,
)

TAU = 2.0 * math.pi
INITIAL_OMEGA = 0.9


def extract_angles(row) -> tuple[float, float, float]:
    angles = []
    for index, node in enumerate(row.assignment):
        sine_index = 2 if index == 0 else 1
        angles.append(
            math.atan2(node.features[sine_index], node.features[0]) % TAU
        )
    return tuple(angles)


def tensor_features(
    angles: tuple[float, float, float],
    omega: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return four rank-1 terms and exact derivatives with respect to omega."""
    if not math.isfinite(omega) or omega <= 0:
        raise ValueError("omega must be finite and positive")
    a, b, c = angles
    aa, bb, cc = omega * a, omega * b, omega * c
    ca, sa = math.cos(aa), math.sin(aa)
    cb, sb = math.cos(bb), math.sin(bb)
    ccos, sc = math.cos(cc), math.sin(cc)
    features = (
        ca * cb * ccos,
        ca * sb * sc,
        sa * cb * sc,
        sa * sb * ccos,
    )
    dca, dsa = -a * sa, a * ca
    dcb, dsb = -b * sb, b * cb
    dcc, dsc = -c * sc, c * ccos
    derivatives = (
        dca * cb * ccos + ca * dcb * ccos + ca * cb * dcc,
        dca * sb * sc + ca * dsb * sc + ca * sb * dsc,
        dsa * cb * sc + sa * dcb * sc + sa * cb * dsc,
        dsa * sb * ccos + sa * dsb * ccos + sa * sb * dcc,
    )
    return features, derivatives


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(value, 60.0)))
    exp_value = math.exp(max(value, -60.0))
    return exp_value / (1.0 + exp_value)


def operator_logit(parameters: list[float],
                   angles: tuple[float, float, float]) -> float:
    omega = math.exp(parameters[5])
    features, _ = tensor_features(angles, omega)
    return (
        parameters[0] * features[0]
        - parameters[1] * features[1]
        - parameters[2] * features[2]
        - parameters[3] * features[3]
        + parameters[4]
    )


def fit_operator(
    rows: list[tuple[tuple[float, float, float], int]],
    *,
    epochs: int = 120,
    learning_rate: float = 0.01,
    l2: float = 1e-4,
) -> list[float]:
    """Fit four tensor coefficients, bias, and log-frequency with Adam."""
    if not rows:
        raise ValueError("training rows must not be empty")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be finite and positive")
    if not math.isfinite(l2) or l2 < 0:
        raise ValueError("l2 must be finite and non-negative")
    if any(len(angles) != 3 or label not in (0, 1)
           for angles, label in rows):
        raise ValueError("rows must contain three phases and binary labels")

    parameters = [0.1, 0.1, 0.1, 0.1, 0.0, math.log(INITIAL_OMEGA)]
    first_moment = [0.0] * 6
    second_moment = [0.0] * 6
    for step in range(1, epochs + 1):
        gradient = [0.0] * 6
        omega = math.exp(parameters[5])
        for angles, label in rows:
            features, derivatives = tensor_features(angles, omega)
            signed_features = (
                features[0], -features[1], -features[2], -features[3], 1.0
            )
            logit = sum(
                parameters[index] * signed_features[index]
                for index in range(5)
            )
            error = _sigmoid(logit) - label
            for index in range(5):
                gradient[index] += error * signed_features[index]
            dlogit_domega = (
                parameters[0] * derivatives[0]
                - parameters[1] * derivatives[1]
                - parameters[2] * derivatives[2]
                - parameters[3] * derivatives[3]
            )
            gradient[5] += error * dlogit_domega * omega

        scale = 1.0 / len(rows)
        for index in range(6):
            gradient[index] *= scale
            if index < 4:
                gradient[index] += l2 * parameters[index]
            first_moment[index] = (
                0.9 * first_moment[index] + 0.1 * gradient[index]
            )
            second_moment[index] = (
                0.999 * second_moment[index]
                + 0.001 * gradient[index] * gradient[index]
            )
            m_hat = first_moment[index] / (1.0 - 0.9 ** step)
            v_hat = second_moment[index] / (1.0 - 0.999 ** step)
            parameters[index] -= (
                learning_rate * m_hat / (math.sqrt(v_hat) + 1e-8)
            )
            if not math.isfinite(parameters[index]):
                raise ValueError("operator optimizer produced non-finite parameters")
        parameters[5] = min(
            math.log(3.0), max(math.log(0.1), parameters[5])
        )
    return parameters


def evaluate_operator(
    parameters: list[float],
    rows: list[tuple[tuple[float, float, float], int]],
    logit_sign: int = 1,
) -> dict[str, float]:
    if not rows:
        raise ValueError("evaluation rows must not be empty")
    if logit_sign not in (-1, 1):
        raise ValueError("logit_sign must be -1 or 1")
    tp = tn = fp = fn = 0
    total_bce = 0.0
    for angles, label in rows:
        logit = operator_logit(parameters, angles) * logit_sign
        prediction = 1 if logit >= 0 else 0
        if prediction == 1 and label == 1:
            tp += 1
        elif prediction == 0 and label == 0:
            tn += 1
        elif prediction == 1:
            fp += 1
        else:
            fn += 1
        total_bce += (
            max(logit, 0.0) - logit * label
            + math.log1p(math.exp(-abs(logit)))
        )
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "accuracy": (tp + tn) / len(rows),
        "balanced_accuracy": (sensitivity + specificity) / 2.0,
        "mean_bce": total_bce / len(rows),
    }


def _operator_validation_sign(parameters, rows):
    positive = evaluate_operator(parameters, rows, 1)
    negative = evaluate_operator(parameters, rows, -1)
    if negative["accuracy"] > positive["accuracy"]:
        return -1, negative
    return 1, positive


def run_seed(
    seed: int,
    train_count: int = 3000,
    validation_count: int = 750,
    test_count: int = 1500,
    epochs: int = 120,
) -> dict:
    train = make_dataset(train_count, seed * 1009 + 17, "train")
    validation = make_dataset(validation_count, seed * 1009 + 23, "train")
    test = make_dataset(test_count, seed * 1009 + 29, "test")
    train_rows = [(extract_angles(row), row.label) for row in train]
    validation_rows = [(extract_angles(row), row.label) for row in validation]
    test_rows = [(extract_angles(row), row.label) for row in test]

    parameters = fit_operator(train_rows, epochs=epochs)
    operator_sign, operator_validation = _operator_validation_sign(
        parameters, validation_rows
    )
    operator_test = evaluate_operator(parameters, test_rows, operator_sign)

    roles = tuple(RoleSpec(name, frozenset({name})) for name in ROLE_NAMES)
    srok = LearnableSROK(roles, feature_dim=5)
    srok.fit_binary(
        train, max_order=3, epochs=epochs, learning_rate=0.15, l2=1e-3
    )
    srok_sign, srok_validation = _validation_sign(srok, validation, 3)
    srok_test = evaluate_srok(srok, test, 3, logit_sign=srok_sign)

    return {
        "seed": seed,
        "train_examples": train_count,
        "validation_examples": validation_count,
        "test_examples": test_count,
        "epochs": epochs,
        "operator": {
            "parameter_count": len(parameters),
            "initial_omega": INITIAL_OMEGA,
            "learned_omega": math.exp(parameters[5]),
            "validation_logit_sign": operator_sign,
            "validation": operator_validation,
            "test": operator_test,
        },
        "srok": {
            "parameter_count": len(srok.weights),
            "validation_logit_sign": srok_sign,
            "validation": srok_validation,
            "test": srok_test,
        },
    }


def run(
    seeds: int = 5,
    start_seed: int = 7,
    train_count: int = 3000,
    validation_count: int = 750,
    test_count: int = 1500,
    epochs: int = 120,
) -> dict:
    if isinstance(seeds, bool) or not isinstance(seeds, int) or seeds < 2:
        raise ValueError("seeds must be at least 2")
    results = [
        run_seed(
            start_seed + offset, train_count, validation_count,
            test_count, epochs,
        )
        for offset in range(seeds)
    ]
    operator_accuracy = [row["operator"]["test"]["accuracy"] for row in results]
    srok_accuracy = [row["srok"]["test"]["accuracy"] for row in results]
    omegas = [row["operator"]["learned_omega"] for row in results]
    return {
        "experiment": "N0.14-learnable-frequency-cyclic-operator-v1",
        "seed_count": seeds,
        "configuration": {
            "start_seed": start_seed,
            "train_count": train_count,
            "validation_count": validation_count,
            "test_count": test_count,
            "epochs": epochs,
            "initial_omega": INITIAL_OMEGA,
        },
        "parameter_counts": {"learnable_operator": 6, "srok": 35},
        "summary": {
            "operator_test_accuracy": {
                "mean": mean(operator_accuracy),
                "sample_stddev": stdev(operator_accuracy),
            },
            "srok_test_accuracy": {
                "mean": mean(srok_accuracy),
                "sample_stddev": stdev(srok_accuracy),
            },
            "learned_omega": {
                "mean": mean(omegas),
                "sample_stddev": stdev(omegas),
                "min": min(omegas),
                "max": max(omegas),
            },
        },
        "per_seed": results,
        "limitations": [
            "The target family and rank-4 trigonometric factorization are known in advance.",
            "Only the shared frequency and four tensor coefficients plus bias are learned; this is not unconstrained representation learning.",
            "The initial frequency 0.9 is a near-target prior and is not a random-from-scratch initialization.",
            "The task is synthetic and does not establish semantic rule induction or natural-language reasoning.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=3000)
    parser.add_argument("--validation-samples", type=int, default=750)
    parser.add_argument("--test-samples", type=int, default=1500)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(
        args.seeds, args.start_seed, args.train_samples,
        args.validation_samples, args.test_samples, args.epochs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
