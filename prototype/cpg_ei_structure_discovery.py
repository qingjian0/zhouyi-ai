"""Greedy residual-driven growth and pruning of CPG-EI relation edges.

The candidate universe is finite (all pairwise and third-order subsets of six
lines); only the active topology is learned. This is a controlled structure-
discovery benchmark, not open-ended graph induction.
"""
from __future__ import annotations

import math
from typing import Sequence

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel,
    Example,
    FEATURE_NAMES,
    encode_state,
    evaluate,
)


def _orthonormal_active_basis(
    examples: Sequence[Example], active_indices: set[int]
) -> list[list[float]]:
    columns = []
    for feature_index in sorted(set(range(7)) | active_indices):
        columns.append([encode_state(row.state)[feature_index] for row in examples])
    basis: list[list[float]] = []
    for vector in columns:
        residual = vector[:]
        for unit in basis:
            projection = sum(a * b for a, b in zip(residual, unit))
            residual = [a - projection * b for a, b in zip(residual, unit)]
        norm = math.sqrt(sum(value * value for value in residual))
        if norm > 1e-9:
            basis.append([value / norm for value in residual])
    return basis


def _prune_zero_weight_edges(
    model: CpgEiTransitionModel, *, threshold: float
) -> tuple[int, ...]:
    removed = []
    for feature_index in sorted(model.active_relation_indices):
        group_norm = math.sqrt(sum(
            model.weights[head_index][feature_index] ** 2
            for head_index in range(6)
        ))
        if group_norm <= threshold:
            model.active_relation_indices.remove(feature_index)
            removed.append(feature_index)
    return tuple(removed)


def grow_relation_graph(
    model: CpgEiTransitionModel,
    train_examples: Sequence[Example],
    validation_examples: Sequence[Example],
    *,
    rounds: int = 5,
    edges_per_round: int = 3,
    epochs_per_round: int = 100,
    learning_rate: float = 0.35,
    gate_l1: float = 0.01,
    edge_group_l1: float = 0.03,
    prune_threshold: float = 1e-5,
    normalize_candidate_scores: bool = False,
) -> dict:
    """Train, prune weak active edges, then add top residual-correlated candidates."""
    if not train_examples or not validation_examples:
        raise ValueError("train and validation examples must be non-empty")
    if rounds < 1 or not 1 <= edges_per_round <= 35 or epochs_per_round < 1:
        raise ValueError("invalid structure-discovery schedule")
    if prune_threshold < 0.0:
        raise ValueError("prune_threshold must be non-negative")

    trace = []
    candidate_indices = set(range(7, len(FEATURE_NAMES)))
    for round_index in range(1, rounds + 1):
        model.train(
            train_examples,
            epochs=epochs_per_round,
            learning_rate=learning_rate,
            gate_l1=gate_l1,
            edge_group_l1=edge_group_l1,
        )
        removed = _prune_zero_weight_edges(model, threshold=prune_threshold)
        basis = _orthonormal_active_basis(
            train_examples, model.active_relation_indices
        )
        errors = [
            tuple(
                probability - target
                for probability, target in zip(
                    model.predict_proba(row.state), row.target
                )
            )
            for row in train_examples
        ]
        scores: dict[int, float] = {}
        for feature_index in sorted(candidate_indices - model.active_relation_indices):
            residual = [
                encode_state(row.state)[feature_index]
                for row in train_examples
            ]
            for unit in basis:
                projection = sum(a * b for a, b in zip(residual, unit))
                residual = [a - projection * b for a, b in zip(residual, unit)]
            correlations = [
                sum(error[head] * residual[row_index]
                    for row_index, error in enumerate(errors))
                for head in range(6)
            ]
            score = sum(abs(value) for value in correlations)
            if normalize_candidate_scores:
                residual_norm = math.sqrt(sum(value * value for value in residual))
                if residual_norm <= 1e-9:
                    continue
                score /= residual_norm
            if score > 1e-10:
                scores[feature_index] = score
        validation_before_add = evaluate(model, validation_examples)
        added = tuple(sorted(
            sorted(scores, key=lambda index: (-scores[index], index))[:edges_per_round]
        ))
        model.active_relation_indices.update(added)
        trace.append({
            "round": round_index,
            "added_edges": [FEATURE_NAMES[index] for index in added],
            "pruned_edges": [FEATURE_NAMES[index] for index in removed],
            "active_edge_count_after_add": len(model.active_relation_indices),
            "validation_before_add": validation_before_add,
        })

    model.train(
        train_examples,
        epochs=epochs_per_round,
        learning_rate=learning_rate,
        gate_l1=gate_l1,
        edge_group_l1=edge_group_l1,
    )
    final_pruned = _prune_zero_weight_edges(model, threshold=prune_threshold)
    return {
        "trace": trace,
        "final_pruned_edges": [FEATURE_NAMES[index] for index in final_pruned],
        "active_edges": [
            FEATURE_NAMES[index] for index in sorted(model.active_relation_indices)
        ],
        "active_edge_count": len(model.active_relation_indices),
        "validation": evaluate(model, validation_examples),
    }
