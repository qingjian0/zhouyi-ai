"""Optional NumPy minibatch backend for the CPG-EI logistic relation learner.

The numerical update matches RelationalTransitionModel.train: full-batch
binary cross-entropy gradient descent, the same intercept-excluded L2 penalty,
and float64 parameters. NumPy is optional; the reference Python backend remains
the dependency-free default.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Sequence

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, encode_relations,
)


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise RuntimeError(
            "NumPy backend requires optional dependency numpy; install numpy>=1.26"
        ) from exc
    return np


def _matrix_loss(np, features, targets, weights) -> float:
    logits = features @ weights.T
    return float(np.mean(np.logaddexp(0.0, logits) - targets * logits))


def fit_with_early_stopping_numpy(
    model: RelationalTransitionModel,
    training: Sequence[TransitionExample],
    development: Sequence[TransitionExample],
    *,
    max_epochs: int = 120,
    patience: int = 12,
    min_delta: float = 1e-5,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    """Fit with cached float64 feature matrices and full-batch NumPy gradients."""
    np = _require_numpy()
    if not training or not development:
        raise ValueError("training and development examples must both be non-empty")
    numeric = (min_delta, learning_rate, l2)
    if (
        isinstance(max_epochs, bool) or not isinstance(max_epochs, int) or max_epochs < 1
        or isinstance(patience, bool) or not isinstance(patience, int) or patience < 1
        or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in numeric
        )
        or min_delta < 0 or learning_rate <= 0 or l2 < 0
    ):
        raise ValueError("invalid early-stopping or optimizer configuration")

    for row in (*training, *development):
        model._validate_example(row)

    # Feature encoding is performed once per split, rather than once per epoch.
    x_train = np.asarray(
        [encode_relations(row.state, model.supports) for row in training],
        dtype=np.float64,
    )
    y_train = np.asarray([row.target for row in training], dtype=np.float64)
    x_development = np.asarray(
        [encode_relations(row.state, model.supports) for row in development],
        dtype=np.float64,
    )
    y_development = np.asarray(
        [row.target for row in development], dtype=np.float64
    )
    weights = np.asarray(model.weights, dtype=np.float64).copy()
    best_loss = _matrix_loss(np, x_development, y_development, weights)
    best_epoch = 0
    best_weights = weights.copy()
    epochs_without_improvement = 0
    epochs_run = 0
    train_losses: list[float] = []

    for epoch in range(1, max_epochs + 1):
        logits = x_train @ weights.T
        probabilities = np.exp(-np.logaddexp(0.0, -logits))
        train_losses.append(
            float(np.mean(np.logaddexp(0.0, logits) - y_train * logits))
        )
        gradients = ((probabilities - y_train).T @ x_train) / len(training)
        if weights.shape[1] > 1 and l2:
            gradients[:, 1:] += l2 * weights[:, 1:]
        weights -= learning_rate * gradients
        epochs_run = epoch

        development_loss = _matrix_loss(
            np, x_development, y_development, weights
        )
        if development_loss < best_loss - min_delta:
            best_loss = development_loss
            best_epoch = epoch
            best_weights = weights.copy()
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.weights = best_weights.tolist()
    weights_digest = hashlib.sha256(
        json.dumps(model.weights, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "epochs_run": epochs_run,
        "best_epoch": best_epoch,
        "best_development_log_loss": best_loss,
        "initial_train_loss": train_losses[0] if train_losses else None,
        "last_train_loss_before_restore": train_losses[-1] if train_losses else None,
        "stopped_early": epochs_run < max_epochs,
        "selected_weights_sha256": weights_digest,
        "optimizer_backend": "numpy-float64-cached-full-batch",
        "training_feature_rows_encoded": len(training),
        "development_feature_rows_encoded": len(development),
    }
