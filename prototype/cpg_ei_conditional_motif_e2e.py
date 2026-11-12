"""End-to-end validation of conditional motif proposals in the CPG-EI learner.

The proposer sees training rows only. Its selected motif features initialize the
active topology; the trainable transition model then learns on the same training
partition and is evaluated on an independently sampled held-out partition.
"""
from __future__ import annotations

import itertools
import json
import math
import random

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel,
    Example,
    FEATURE_NAMES,
    evaluate,
)
from prototype.cpg_ei_conditional_motif_proposals import rank_conditional_motifs


PARITY_TRIPLES = ((0, 1, 2), (1, 3, 4), (2, 4, 5))


def make_parity_dataset(count: int, seed: int) -> list[Example]:
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        state = tuple(rng.randrange(2) for _ in range(6))
        target = tuple(
            sum(state[index] for index in PARITY_TRIPLES[head // 2]) % 2
            for head in range(6)
        )
        rows.append(Example(state, target))
    return rows


def expected_support() -> set[str]:
    support = set()
    for triple in PARITY_TRIPLES:
        support.add("hyperedge_3_" + "_".join(map(str, triple)))
        support.update(
            "hyperedge_2_" + "_".join(map(str, pair))
            for pair in itertools.combinations(triple, 2)
        )
    return support


def run_experiment(
    *,
    seeds: tuple[int, ...] = (11, 23, 37, 53, 71),
    train_samples: int = 512,
    test_samples: int = 256,
    epochs: int = 300,
    learning_rate: float = 0.35,
) -> dict:
    if not seeds or train_samples < 1 or test_samples < 1 or epochs < 1:
        raise ValueError("seeds and sample/epoch counts must be positive")
    teacher_support = expected_support()
    records = []

    for seed in seeds:
        train = make_parity_dataset(train_samples, seed)
        test = make_parity_dataset(test_samples, seed + 10000)

        # Strict boundary: only train is passed to the proposal ranker.
        proposal = rank_conditional_motifs(train, max_motifs=3)
        selected_motifs = [tuple(item["lines"]) for item in proposal["selected"]]
        selected_features = {
            name
            for item in proposal["selected"]
            for name in item["feature_names"]
        }
        active_indices = {
            FEATURE_NAMES.index(name) for name in selected_features
        }

        model = CpgEiTransitionModel.create(
            active_relation_indices=active_indices
        )
        losses = model.train(
            train,
            epochs=epochs,
            learning_rate=learning_rate,
            gate_l1=0.0,
            edge_group_l1=0.0,
        )
        metrics = evaluate(model, test)
        overlap = len(selected_features & teacher_support)
        records.append({
            "seed": seed,
            "selected_motifs": [list(lines) for lines in selected_motifs],
            "selected_relation_count": len(selected_features),
            "support_precision": overlap / len(selected_features) if selected_features else 0.0,
            "support_recall": overlap / len(teacher_support),
            "exact_support_recovery": selected_features == teacher_support,
            "heldout_bit_accuracy": metrics["bit_accuracy"],
            "heldout_exact_state_accuracy": metrics["exact_state_accuracy"],
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "finite_loss": all(math.isfinite(value) for value in losses),
        })

    return {
        "benchmark": "cpg-ei-conditional-motif-end-to-end-v1",
        "seeds": list(seeds),
        "train_samples": train_samples,
        "heldout_samples": test_samples,
        "epochs": epochs,
        "optimizer": {"name": "existing_full_batch_sgd", "learning_rate": learning_rate},
        "proposal_boundary": "conditional motif ranking uses training rows only",
        "summary": {
            "exact_support_recovery_count": sum(
                row["exact_support_recovery"] for row in records
            ),
            "mean_heldout_bit_accuracy": sum(
                row["heldout_bit_accuracy"] for row in records
            ) / len(records),
            "min_heldout_bit_accuracy": min(
                row["heldout_bit_accuracy"] for row in records
            ),
            "mean_heldout_exact_state_accuracy": sum(
                row["heldout_exact_state_accuracy"] for row in records
            ) / len(records),
            "all_losses_finite": all(row["finite_loss"] for row in records),
        },
        "records": records,
        "claim_boundary": (
            "Finite six-line GF(2) parity benchmark only. This validates a bounded "
            "motif proposal-to-learner path, not arbitrary-arity discovery, "
            "open-world relation induction, natural-language reasoning, or "
            "general superiority to Transformer models."
        ),
    }


def main() -> None:
    print(json.dumps(run_experiment(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
