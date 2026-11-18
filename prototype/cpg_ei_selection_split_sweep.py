"""Measure how proposal-selection sample size affects CPG-EI motif selection."""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from typing import Iterable, Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, evaluate
from prototype.cpg_ei_joint_proposals import grow_relation_graph_joint_motifs
from prototype.cpg_ei_selection_sweep import (
    RULE_FAMILIES,
    exact_support,
    make_examples,
    _support_metrics,
)

DEFAULT_SEEDS = (11, 23, 47, 89, 131)
# Keep the locked test fixed at 12 states while increasing proposal evidence.
SPLIT_CONFIGS = ((40, 12, 12), (32, 20, 12), (24, 28, 12))


def partition_states(seed: int, train_size: int, proposal_size: int, locked_size: int):
    sizes = (train_size, proposal_size, locked_size)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in sizes):
        raise ValueError("all split sizes must be positive integers")
    if sum(sizes) != 64:
        raise ValueError("split sizes must partition all 64 six-bit states")
    states = list(itertools.product((0, 1), repeat=6))
    random.Random(seed).shuffle(states)
    train_end = train_size
    proposal_end = train_end + proposal_size
    return (
        tuple(states[:train_end]),
        tuple(states[train_end:proposal_end]),
        tuple(states[proposal_end:]),
    )


def _parse_seeds(value: str):
    try:
        seeds = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def _summarize(rows: list[dict]) -> dict:
    def mean(key: str) -> float:
        return sum(float(row[key]) for row in rows) / len(rows)

    ood = [
        score
        for row in rows
        for score in row["ood_bit_accuracy_by_family"].values()
    ]
    return {
        "experiments": len(rows),
        "mean_support_precision": mean("support_precision"),
        "mean_support_recall": mean("support_recall"),
        "mean_locked_test_bit_accuracy": mean("locked_test_bit_accuracy"),
        "mean_ood_bit_accuracy": sum(ood) / len(ood),
        "mean_selected_motifs": mean("selected_motif_count"),
        "mean_candidate_fits": mean("candidate_fits"),
        "mean_training_passes": mean("training_passes"),
        "exact_support_recovery_count": sum(
            row["support_precision"] == 1.0 and row["support_recall"] == 1.0
            for row in rows
        ),
    }


def run_sweep(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    epochs: int = 12,
    max_motifs: int = 3,
) -> dict:
    if not seeds or epochs < 1 or not 1 <= max_motifs <= 20:
        raise ValueError("seeds, epochs, or motif budget are invalid")

    records = []
    for train_size, proposal_size, locked_size in SPLIT_CONFIGS:
        for seed in seeds:
            train_states, proposal_states, locked_states = partition_states(
                seed, train_size, proposal_size, locked_size
            )
            state_sets = tuple(map(set, (train_states, proposal_states, locked_states)))
            if any(
                state_sets[i] & state_sets[j]
                for i in range(3)
                for j in range(i + 1, 3)
            ):
                raise AssertionError("train/proposal/locked partitions overlap")

            for family, triples in RULE_FAMILIES.items():
                train = make_examples(train_states, triples)
                proposal = make_examples(proposal_states, triples)
                locked = make_examples(locked_states, triples)
                for protocol in ("proposal_split", "legacy_train_ranked"):
                    model = CpgEiTransitionModel.create(active_relation_indices=set())
                    kwargs = {"proposal_examples": proposal} if protocol == "proposal_split" else {}
                    result = grow_relation_graph_joint_motifs(
                        model,
                        train,
                        locked,
                        **kwargs,
                        max_motifs=max_motifs,
                        epochs_per_candidate=epochs,
                        gate_l1=0.001,
                        edge_group_l1=0.001,
                    )
                    support = _support_metrics(result["active_edges"], exact_support(triples))
                    ood = {
                        other_family: evaluate(
                            model, make_examples(locked_states, other_triples)
                        )["bit_accuracy"]
                        for other_family, other_triples in RULE_FAMILIES.items()
                        if other_family != family
                    }
                    row = {
                        "train_size": train_size,
                        "proposal_size": proposal_size,
                        "locked_size": locked_size,
                        "seed": seed,
                        "train_family": family,
                        "selection_protocol": protocol,
                        "selected_motif_count": len(result["selected_motifs"]),
                        "candidate_fits": result["candidate_fits_total"],
                        "training_passes": epochs * (1 + result["candidate_fits_total"]),
                        "locked_test_bit_accuracy": result["validation"]["bit_accuracy"],
                        "locked_test_bce": result["validation_binary_cross_entropy"],
                        "ood_bit_accuracy_by_family": ood,
                        **support,
                    }
                    metrics = [
                        row["locked_test_bit_accuracy"],
                        row["locked_test_bce"],
                        *ood.values(),
                    ]
                    if not all(math.isfinite(value) for value in metrics):
                        raise AssertionError("non-finite split-size metric")
                    records.append(row)

    aggregate = {}
    for train_size, proposal_size, locked_size in SPLIT_CONFIGS:
        split_key = f"{train_size}/{proposal_size}/{locked_size}"
        aggregate[split_key] = {}
        for protocol in ("proposal_split", "legacy_train_ranked"):
            rows = [
                row for row in records
                if (row["train_size"], row["proposal_size"], row["locked_size"])
                == (train_size, proposal_size, locked_size)
                and row["selection_protocol"] == protocol
            ]
            aggregate[split_key][protocol] = _summarize(rows)

    return {
        "benchmark": "cpg-ei-proposal-split-size-v1",
        "seeds": list(seeds),
        "rule_families": list(RULE_FAMILIES),
        "split_configs": [
            {"train": train, "proposal_selection": proposal, "locked_test": locked}
            for train, proposal, locked in SPLIT_CONFIGS
        ],
        "optimizer": {"epochs_per_candidate": epochs, "max_motifs": max_motifs},
        "aggregate_by_split_and_protocol": aggregate,
        "claim_boundary": (
            "Finite synthetic six-bit rule families only. Split-size sensitivity "
            "does not establish open-ended relation induction or natural-language reasoning."
        ),
        "records": records,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--max-motifs", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_sweep(seeds=args.seeds, epochs=args.epochs, max_motifs=args.max_motifs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
