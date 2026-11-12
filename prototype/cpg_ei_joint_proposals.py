"""Bounded joint-motif proposals for synergistic CPG-EI relations.

The proposal unit is a four-edge motif induced by one 3-line subset:
its three pairwise conjunctions plus the matching third-order hyperedge.
This is a deliberately bounded search space (C(6, 3) = 20 motifs), not
unrestricted combinatorial search. Candidate groups are trained jointly and
ranked on held-out validation log loss so individually weak edges can be
selected as a coherent structure.
"""
from __future__ import annotations

import copy
import itertools
import math
from typing import Sequence

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel,
    Example,
    FEATURE_NAMES,
    evaluate,
)


def _binary_cross_entropy(
    model: CpgEiTransitionModel, examples: Sequence[Example]
) -> float:
    if not examples:
        raise ValueError("examples must not be empty")
    total = 0.0
    for row in examples:
        for logit, target in zip(model.logits(row.state), row.target):
            total += max(logit, 0.0) - logit * target + math.log1p(
                math.exp(-abs(logit))
            )
    return total / (len(examples) * 6.0)


def _three_line_motifs() -> tuple[tuple[int, ...], ...]:
    motifs = []
    for triple in itertools.combinations(range(6), 3):
        names = [
            "hyperedge_2_" + "_".join(map(str, pair))
            for pair in itertools.combinations(triple, 2)
        ]
        names.append("hyperedge_3_" + "_".join(map(str, triple)))
        motifs.append(tuple(FEATURE_NAMES.index(name) for name in names))
    return tuple(motifs)


def grow_relation_graph_joint_motifs(
    model: CpgEiTransitionModel,
    train_examples: Sequence[Example],
    validation_examples: Sequence[Example],
    *,
    max_motifs: int = 3,
    epochs_per_candidate: int = 50,
    learning_rate: float = 0.35,
    gate_l1: float = 0.01,
    edge_group_l1: float = 0.03,
    min_validation_improvement: float = 1e-5,
) -> dict:
    """Select bounded four-edge motifs by joint fit, not marginal edge scores.

    Each round evaluates every not-yet-selected 3-line motif from an identical
    copy of the current model. The whole group is enabled and optimized
    together; the candidate with the lowest validation BCE is retained.
    """
    if not train_examples or not validation_examples:
        raise ValueError("train and validation examples must be non-empty")
    if not 1 <= max_motifs <= 20 or epochs_per_candidate < 1:
        raise ValueError("invalid joint-motif search schedule")
    if min_validation_improvement < 0.0:
        raise ValueError("min_validation_improvement must be non-negative")

    selected: list[tuple[int, ...]] = []
    trace = []
    current = copy.deepcopy(model)
    current.train(
        train_examples,
        epochs=epochs_per_candidate,
        learning_rate=learning_rate,
        gate_l1=gate_l1,
        edge_group_l1=edge_group_l1,
    )
    current_loss = _binary_cross_entropy(current, validation_examples)

    for round_index in range(1, max_motifs + 1):
        best_model = None
        best_motif = None
        best_loss = current_loss
        for motif in _three_line_motifs():
            if motif in selected:
                continue
            candidate = copy.deepcopy(current)
            candidate.active_relation_indices.update(motif)
            candidate.train(
                train_examples,
                epochs=epochs_per_candidate,
                learning_rate=learning_rate,
                gate_l1=gate_l1,
                edge_group_l1=edge_group_l1,
            )
            score = _binary_cross_entropy(candidate, validation_examples)
            if score < best_loss - 1e-12:
                best_loss = score
                best_model = candidate
                best_motif = motif

        improvement = current_loss - best_loss
        if best_model is None or improvement <= min_validation_improvement:
            trace.append({
                "round": round_index,
                "selected_motif": None,
                "validation_bce_before": current_loss,
                "validation_bce_after": current_loss,
                "validation_bce_improvement": 0.0,
            })
            break

        current = best_model
        current_loss = best_loss
        selected.append(best_motif)
        trace.append({
            "round": round_index,
            "selected_motif": [
                FEATURE_NAMES[index] for index in best_motif
            ],
            "validation_bce_before": current_loss + improvement,
            "validation_bce_after": current_loss,
            "validation_bce_improvement": improvement,
        })

    # Copy the selected model state back into the caller-owned instance.
    model.weights = current.weights
    model.gate_logits = current.gate_logits
    model.active_relation_indices = current.active_relation_indices
    return {
        "selected_motifs": [
            [FEATURE_NAMES[index] for index in motif] for motif in selected
        ],
        "trace": trace,
        "active_edges": [
            FEATURE_NAMES[index]
            for index in sorted(model.active_relation_indices)
        ],
        "active_edge_count": len(model.active_relation_indices),
        "validation": evaluate(model, validation_examples),
        "validation_binary_cross_entropy": current_loss,
        "candidate_motif_universe_size": len(_three_line_motifs()),
        "candidate_fits_per_round": len(_three_line_motifs()),
    }
