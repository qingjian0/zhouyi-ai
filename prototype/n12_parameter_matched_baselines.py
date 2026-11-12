"""N0.12 parameter-budget baselines for N0.11 cyclic phase OOD transfer.

Compare the 35-parameter SROK tensor-factor model with small MLPs that receive
the same six sin/cos inputs but do not receive explicit triple-product
features. Hidden widths 4 and 5 bracket the SROK parameter budget; width 12
is a higher-capacity reference. Validation is in-distribution; test is the
held-out phase region from N0.11.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from statistics import mean, stdev

from prototype.n09_learnable_srok import LearnableSROK, RoleSpec
from prototype.n11_cyclic_composition_ood import (
    ROLE_NAMES,
    evaluate as evaluate_srok,
    make_dataset,
    _validation_sign,
)


def _mlp_inputs(row) -> tuple[float, ...]:
    values = []
    for index, node in enumerate(row.assignment):
        sine_index = 2 if index == 0 else 1
        values.extend((node.features[0], node.features[sine_index]))
    return tuple(values)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(value, 60.0)))
    exp_value = math.exp(max(value, -60.0))
    return exp_value / (1.0 + exp_value)


def _mlp_logit(parameters: list[float], inputs: tuple[float, ...],
               hidden: int) -> float:
    first_bias = 6 * hidden
    second_weights = 7 * hidden
    output_bias = 8 * hidden
    activations = []
    for j in range(hidden):
        value = parameters[first_bias + j]
        for i in range(6):
            value += parameters[i * hidden + j] * inputs[i]
        activations.append(math.tanh(value))
    result = parameters[output_bias]
    for j in range(hidden):
        result += parameters[second_weights + j] * activations[j]
    return result


def fit_mlp(
    rows: list[tuple[tuple[float, ...], int]],
    *,
    hidden: int,
    seed: int,
    epochs: int = 120,
    learning_rate: float = 0.01,
    l2: float = 1e-4,
) -> list[float]:
    """Train a one-hidden-layer tanh MLP using deterministic full-batch Adam."""
    if isinstance(hidden, bool) or not isinstance(hidden, int) or hidden < 1:
        raise ValueError("hidden must be a positive integer")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if not rows:
        raise ValueError("training rows must not be empty")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be finite and positive")
    if not math.isfinite(l2) or l2 < 0:
        raise ValueError("l2 must be finite and non-negative")
    if any(len(inputs) != 6 or label not in (0, 1)
           for inputs, label in rows):
        raise ValueError("MLP rows require six inputs and binary labels")

    rng = random.Random(seed)
    parameter_count = 8 * hidden + 1
    parameters = [rng.gauss(0.0, 0.2) for _ in range(6 * hidden)]
    parameters.extend([0.0] * hidden)
    parameters.extend(rng.gauss(0.0, 0.2) for _ in range(hidden))
    parameters.append(0.0)
    if len(parameters) != parameter_count:
        raise RuntimeError("MLP parameter layout mismatch")

    first_moment = [0.0] * parameter_count
    second_moment = [0.0] * parameter_count
    for step in range(1, epochs + 1):
        gradient = [0.0] * parameter_count
        for inputs, label in rows:
            preactivations = []
            activations = []
            for j in range(hidden):
                value = parameters[6 * hidden + j]
                for i in range(6):
                    value += parameters[i * hidden + j] * inputs[i]
                preactivations.append(value)
                activations.append(math.tanh(value))
            logit = parameters[8 * hidden]
            for j in range(hidden):
                logit += parameters[7 * hidden + j] * activations[j]
            error = _sigmoid(logit) - label

            gradient[8 * hidden] += error
            for j in range(hidden):
                gradient[7 * hidden + j] += error * activations[j]
                delta = (
                    error * parameters[7 * hidden + j]
                    * (1.0 - activations[j] * activations[j])
                )
                gradient[6 * hidden + j] += delta
                for i in range(6):
                    gradient[i * hidden + j] += delta * inputs[i]

        scale = 1.0 / len(rows)
        for index in range(parameter_count):
            # L2 applies to weights, not biases.
            is_bias = (
                6 * hidden <= index < 7 * hidden
                or index == 8 * hidden
            )
            gradient[index] = (
                gradient[index] * scale
                + (0.0 if is_bias else l2 * parameters[index])
            )
            first_moment[index] = 0.9 * first_moment[index] + 0.1 * gradient[index]
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
                raise ValueError("MLP optimizer produced non-finite parameters")
    return parameters


def evaluate_mlp(
    parameters: list[float],
    rows: list[tuple[tuple[float, ...], int]],
    *,
    hidden: int,
    logit_sign: int = 1,
) -> dict[str, float]:
    if not rows:
        raise ValueError("evaluation rows must not be empty")
    if logit_sign not in (-1, 1):
        raise ValueError("logit_sign must be -1 or 1")
    tp = tn = fp = fn = 0
    total_bce = 0.0
    for inputs, label in rows:
        logit = _mlp_logit(parameters, inputs, hidden) * logit_sign
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
        "positive_rate": (tp + fn) / len(rows),
    }


def _mlp_validation_sign(parameters, rows, hidden):
    positive = evaluate_mlp(parameters, rows, hidden=hidden, logit_sign=1)
    negative = evaluate_mlp(parameters, rows, hidden=hidden, logit_sign=-1)
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
    train_mlp = [(_mlp_inputs(row), row.label) for row in train]
    validation_mlp = [(_mlp_inputs(row), row.label) for row in validation]
    test_mlp = [(_mlp_inputs(row), row.label) for row in test]

    roles = tuple(RoleSpec(name, frozenset({name})) for name in ROLE_NAMES)
    srok = LearnableSROK(roles, feature_dim=5)
    srok.fit_binary(
        train, max_order=3, epochs=epochs, learning_rate=0.15, l2=1e-3
    )
    srok_sign, srok_validation = _validation_sign(srok, validation, 3)
    srok_test = evaluate_srok(srok, test, 3, logit_sign=srok_sign)

    mlp_results = {}
    for hidden in (4, 5, 12):
        parameters = fit_mlp(
            train_mlp, hidden=hidden, seed=seed * 1009 + 101 + hidden,
            epochs=epochs,
        )
        sign, validation_result = _mlp_validation_sign(
            parameters, validation_mlp, hidden
        )
        mlp_results[str(hidden)] = {
            "parameter_count": len(parameters),
            "validation_logit_sign": sign,
            "validation": validation_result,
            "test": evaluate_mlp(
                parameters, test_mlp, hidden=hidden, logit_sign=sign
            ),
        }

    return {
        "seed": seed,
        "train_examples": train_count,
        "validation_examples": validation_count,
        "test_examples": test_count,
        "epochs": epochs,
        "srok": {
            "parameter_count": len(srok.weights),
            "validation_logit_sign": srok_sign,
            "validation": srok_validation,
            "test": srok_test,
        },
        "mlp": mlp_results,
        "parameter_budget_note": (
            "SROK has 35 parameters; MLP-4 has 33 (closest match), "
            "MLP-5 has 41 (nearby upper bracket), and MLP-12 has 97."
        ),
    }


def run(
    seed_count: int = 5,
    start_seed: int = 7,
    train_count: int = 3000,
    validation_count: int = 750,
    test_count: int = 1500,
    epochs: int = 120,
) -> dict:
    if isinstance(seed_count, bool) or not isinstance(seed_count, int) or seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    results = [
        run_seed(
            start_seed + offset, train_count, validation_count, test_count, epochs
        )
        for offset in range(seed_count)
    ]
    model_names = ("srok", "mlp_4", "mlp_5", "mlp_12")
    summary = {}
    for name in model_names:
        if name == "srok":
            metric_rows = [row["srok"]["test"] for row in results]
        else:
            hidden = name.split("_")[1]
            metric_rows = [row["mlp"][hidden]["test"] for row in results]
        for metric in ("accuracy", "balanced_accuracy", "mean_bce"):
            values = [row[metric] for row in metric_rows]
            summary[f"{name}.{metric}"] = {
                "mean": mean(values),
                "sample_stddev": stdev(values),
            }
    return {
        "experiment": "N0.12-parameter-budget-mlp-baselines-v1",
        "seed_count": seed_count,
        "configuration": {
            "start_seed": start_seed,
            "train_count": train_count,
            "validation_count": validation_count,
            "test_count": test_count,
            "epochs": epochs,
            "input": "six sin/cos coordinates; same N0.11 phase splits",
        },
        "parameter_counts": {"srok": 35, "mlp_4": 33, "mlp_5": 41, "mlp_12": 97},
        "summary": summary,
        "per_seed": results,
        "limitations": [
            "Synthetic known-rule phase task with explicit Fourier input features.",
            "SROK receives an explicit third-order tensor factorization; MLPs receive the same six raw sin/cos inputs.",
            "MLP widths are fixed in advance and are not exhaustively hyperparameter-tuned.",
            "This compares one small tanh MLP family, not all possible neural architectures.",
            "No natural-language or general-intelligence claim is supported.",
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
