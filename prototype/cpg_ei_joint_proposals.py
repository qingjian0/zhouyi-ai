"""Bounded joint-motif proposals for synergistic CPG-EI relations.

The proposal unit is a four-edge motif induced by one 3-line subset:
its three pairwise conjunctions plus the matching third-order hyperedge.
This is a deliberately bounded search space (C(6, 3) = 20 motifs), not
unrestricted combinatorial search. Candidate groups are trained jointly and
ranked on a separate proposal-selection split when supplied. A final locked
set is evaluated only after selection; omitting the split preserves legacy
training-loss ranking and must be treated as exploratory.
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
    min_training_improvement: float = 1e-5,
    proposal_examples: Sequence[Example] | None = None,
    optimizer: str = "sgd",
) -> dict:
    """Select bounded four-edge motifs by joint fit, not marginal edge scores.

    Each round evaluates every not-yet-selected 3-line motif from an identical
    copy of the current model. The whole group is enabled and optimized
    together on train_examples; the candidate with the lowest proposal-split BCE
    is retained. If proposal_examples is omitted, train_examples is used for
    ranking for backward compatibility (exploratory mode only).
    """
    if not train_examples or not validation_examples:
        raise ValueError("train and locked-test examples must be non-empty")
    proposal_rows = train_examples if proposal_examples is None else proposal_examples
    if not proposal_rows:
        raise ValueError("proposal_examples must be non-empty when supplied")
    if not 1 <= max_motifs <= 20 or epochs_per_candidate < 1:
        raise ValueError("invalid joint-motif search schedule")
    if min_training_improvement < 0.0:
        raise ValueError("min_training_improvement must be non-negative")

    selected: list[tuple[int, ...]] = []
    trace = []
    current = copy.deepcopy(model)
    current.train(
        train_examples,
        epochs=epochs_per_candidate,
        learning_rate=learning_rate,
        gate_l1=gate_l1,
        edge_group_l1=edge_group_l1,
        optimizer=optimizer,
    )
    current_loss = _binary_cross_entropy(current, proposal_rows)

    total_candidate_fits = 0
    for round_index in range(1, max_motifs + 1):
        round_candidate_fits = 0
        best_model = None
        best_motif = None
        best_loss = current_loss
        for motif in _three_line_motifs():
            if motif in selected:
                continue
            round_candidate_fits += 1
            total_candidate_fits += 1
            candidate = copy.deepcopy(current)
            candidate.active_relation_indices.update(motif)
            candidate.train(
                train_examples,
                epochs=epochs_per_candidate,
                learning_rate=learning_rate,
                gate_l1=gate_l1,
                edge_group_l1=edge_group_l1,
                optimizer=optimizer,
            )
            # Candidate weights are fitted only on train_examples. Candidate
            # ranking uses proposal_rows; validation_examples is never consulted
            # until the final locked evaluation below.
            score = _binary_cross_entropy(candidate, proposal_rows)
            if score < best_loss - 1e-12:
                best_loss = score
                best_model = candidate
                best_motif = motif

        improvement = current_loss - best_loss
        if best_model is None or improvement <= min_training_improvement:
            trace.append({
                "round": round_index,
                "selected_motif": None,
                "proposal_selection_bce_before": current_loss,
                "proposal_selection_bce_after": current_loss,
                "proposal_selection_bce_improvement": 0.0,
                "candidate_fits": round_candidate_fits,
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
            "proposal_selection_bce_before": current_loss + improvement,
            "proposal_selection_bce_after": current_loss,
            "proposal_selection_bce_improvement": improvement,
            "candidate_fits": round_candidate_fits,
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
        "training_binary_cross_entropy": _binary_cross_entropy(model, train_examples),
        "proposal_selection_binary_cross_entropy": current_loss,
        "proposal_selection_examples": len(proposal_rows),
        "validation_binary_cross_entropy": _binary_cross_entropy(model, validation_examples),
        "candidate_motif_universe_size": len(_three_line_motifs()),
        "candidate_fits_total": total_candidate_fits,
    }
