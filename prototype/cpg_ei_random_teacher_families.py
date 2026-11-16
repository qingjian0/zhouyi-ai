"""Generalization across independently sampled six-line parity teacher families."""
from __future__ import annotations

import itertools
import json
import math
import random

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, FEATURE_NAMES, evaluate
from prototype.cpg_ei_conditional_motif_proposals import rank_conditional_motifs


ALL_TRIPLES = tuple(itertools.combinations(range(6), 3))


def make_teacher(family_seed: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(sorted(random.Random(family_seed).sample(ALL_TRIPLES, 3)))


def make_splits(
    triples: tuple[tuple[int, int, int], ...], split_seed: int
) -> tuple[list[Example], list[Example], list[Example]]:
    states = list(itertools.product((0, 1), repeat=6))
    random.Random(split_seed).shuffle(states)

    def label(state):
        return tuple(
            sum(state[index] for index in triples[head // 2]) % 2
            for head in range(6)
        )

    rows = [Example(tuple(state), label(state)) for state in states]
    return rows[:32], rows[32:48], rows[48:]


def support_for(triples: tuple[tuple[int, int, int], ...]) -> set[str]:
    support = set()
    for triple in triples:
        support.add("hyperedge_3_" + "_".join(map(str, triple)))
        support.update(
            "hyperedge_2_" + "_".join(map(str, pair))
            for pair in itertools.combinations(triple, 2)
        )
    return support


def _fit(train, evaluation_rows, family_seed, learning_rate, epochs, support):
    proposal = rank_conditional_motifs(train, max_motifs=3)
    selected = {
        name for item in proposal["selected"] for name in item["feature_names"]
    }
    motifs = [tuple(item["lines"]) for item in proposal["selected"]]
    model = CpgEiTransitionModel.create(
        active_relation_indices={FEATURE_NAMES.index(name) for name in selected}
    )
    losses = model.train(
        train, epochs=epochs, learning_rate=learning_rate,
        gate_l1=0.0, edge_group_l1=0.0,
    )
    metrics = evaluate(model, evaluation_rows)
    overlap = len(selected & support)
    return {
        "family_seed": family_seed,
        "selected_motifs": [list(x) for x in motifs],
        "selected_relation_count": len(selected),
        "support_precision": overlap / len(selected) if selected else 0.0,
        "support_recall": overlap / len(support),
        "exact_support_recovery": selected == support,
        "bit_accuracy": metrics["bit_accuracy"],
        "exact_state_accuracy": metrics["exact_state_accuracy"],
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "finite_loss": all(math.isfinite(x) for x in losses),
    }


def run_benchmark(
    *,
    family_seeds: tuple[int, ...] = tuple(range(101, 111)),
    learning_rate: float = 4.2,
    epochs: int = 600,
) -> dict:
    if not family_seeds or len(set(family_seeds)) != len(family_seeds):
        raise ValueError("family_seeds must be non-empty and unique")
    if learning_rate <= 0 or not math.isfinite(learning_rate) or epochs < 1:
        raise ValueError("invalid optimizer configuration")

    records = []
    audits = []
    for family_seed in family_seeds:
        triples = make_teacher(family_seed)
        train, dev, locked = make_splits(triples, family_seed + 10000)
        train_states = {row.state for row in train}
        dev_states = {row.state for row in dev}
        locked_states = {row.state for row in locked}
        audits.append({
            "family_seed": family_seed,
            "teacher_triples": [list(x) for x in triples],
            "train_dev_overlap": len(train_states & dev_states),
            "train_locked_overlap": len(train_states & locked_states),
            "dev_locked_overlap": len(dev_states & locked_states),
            "union_states": len(train_states | dev_states | locked_states),
        })

        # Fixed configuration is carried forward from the state-disjoint
        # benchmark; dev is diagnostic only, not used to retune this sweep.
        dev_record = _fit(train, dev, family_seed, learning_rate, epochs, support_for(triples))
        locked_record = _fit(
            train + dev, locked, family_seed, learning_rate, epochs, support_for(triples)
        )
        records.append({
            "family_seed": family_seed,
            "teacher_triples": [list(x) for x in triples],
            "development": dev_record,
            "locked_test": locked_record,
        })

    if any(
        a["train_dev_overlap"] or a["train_locked_overlap"]
        or a["dev_locked_overlap"] or a["union_states"] != 64
        for a in audits
    ):
        raise AssertionError("state-disjoint invariant violated")

    locked = [row["locked_test"] for row in records]
    return {
        "benchmark": "cpg-ei-random-teacher-families-v1",
        "teacher_family_count": len(records),
        "independent_teacher_generation": "three distinct random triples sampled from 20 possible triples per family seed",
        "input_domain": "complete six-bit state space, partitioned 32/16/16 per family",
        "optimizer": {"name": "existing_full_batch_sgd", "learning_rate": learning_rate, "epochs": epochs},
        "split_audits": audits,
        "summary": {
            "exact_support_recovery_count": sum(x["exact_support_recovery"] for x in locked),
            "mean_support_precision": sum(x["support_precision"] for x in locked) / len(locked),
            "mean_support_recall": sum(x["support_recall"] for x in locked) / len(locked),
            "mean_locked_bit_accuracy": sum(x["bit_accuracy"] for x in locked) / len(locked),
            "min_locked_bit_accuracy": min(x["bit_accuracy"] for x in locked),
            "mean_locked_exact_state_accuracy": sum(x["exact_state_accuracy"] for x in locked) / len(locked),
            "all_losses_finite": all(x["finite_loss"] for x in locked),
        },
        "records": records,
        "claim_boundary": (
            "Ten independently sampled three-triple teachers within a finite six-line GF(2) family. "
            "Each teacher is evaluated on a state-disjoint partition of the 64-state domain. "
            "This does not establish arbitrary-arity or open-world discovery, natural-language "
            "reasoning, or general superiority to Transformer models."
        ),
    }


def main() -> None:
    print(json.dumps(run_benchmark(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
