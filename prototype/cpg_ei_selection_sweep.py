"""Multi-seed CPG-EI candidate-selection benchmark with a locked evaluation split."""
from __future__ import annotations
import argparse, itertools, json, math, random
from typing import Iterable, Sequence
from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, FEATURE_NAMES, evaluate
from prototype.cpg_ei_joint_proposals import grow_relation_graph_joint_motifs

RULE_FAMILIES = {
    "A": ((0, 1, 2), (1, 3, 4), (2, 4, 5)),
    "B": ((0, 2, 4), (1, 2, 5), (0, 3, 5)),
    "C": ((0, 1, 5), (1, 2, 3), (2, 4, 5)),
}
DEFAULT_SEEDS = (11, 23, 47, 89, 131)

def partition_states(seed: int):
    """Partition all 64 six-bit inputs into disjoint 40/12/12 sets."""
    states = list(itertools.product((0, 1), repeat=6))
    random.Random(seed).shuffle(states)
    return tuple(tuple(part) for part in (states[:40], states[40:52], states[52:64]))

def make_examples(states, triples):
    return [Example(state, tuple(sum(state[i] for i in triples[h // 2]) % 2 for h in range(6))) for state in states]

def exact_support(triples):
    support = set()
    for triple in triples:
        support.add("hyperedge_3_" + "_".join(map(str, triple)))
        support.update("hyperedge_2_" + "_".join(map(str, pair)) for pair in itertools.combinations(triple, 2))
    return support

def _support_metrics(active_edges: Sequence[str], expected: set[str]):
    discovered = set(active_edges)
    true_positive = len(discovered & expected)
    return {
        "support_precision": true_positive / len(discovered) if discovered else 0.0,
        "support_recall": true_positive / len(expected),
        "active_edge_count": len(discovered),
    }

def run_sweep(*, seeds: Sequence[int] = DEFAULT_SEEDS, epochs: int | Sequence[int] = (12, 120), max_motifs: int = 3) -> dict:
    """Fit on train, rank on proposal split, and report locked/OOD results."""
    epoch_budgets = (epochs,) if isinstance(epochs, int) else tuple(epochs)
    if not seeds or not epoch_budgets or any(value < 1 for value in epoch_budgets) or not 1 <= max_motifs <= 20:
        raise ValueError("seeds, epochs, or motif budget are invalid")
    records = []
    for seed in seeds:
        train_states, proposal_states, locked_states = partition_states(seed)
        parts = tuple(set(x) for x in (train_states, proposal_states, locked_states))
        if any(parts[i] & parts[j] for i in range(3) for j in range(i + 1, 3)):
            raise AssertionError("train/proposal/locked partitions overlap")
        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            proposal = make_examples(proposal_states, triples)
            locked = make_examples(locked_states, triples)
            oracle_indices = {FEATURE_NAMES.index(name) for name in exact_support(triples)}
            for epoch_budget in epoch_budgets:
              for protocol in ("proposal_split", "legacy_train_ranked"):
                model = CpgEiTransitionModel.create(active_relation_indices=set())
                kwargs = {"proposal_examples": proposal} if protocol == "proposal_split" else {}
                result = grow_relation_graph_joint_motifs(
                    model, train, locked, **kwargs,
                    max_motifs=max_motifs, epochs_per_candidate=epoch_budget,
                    gate_l1=0.001, edge_group_l1=0.001,
                )
                support = _support_metrics(result["active_edges"], exact_support(triples))
                oracle_model = CpgEiTransitionModel.create(active_relation_indices=oracle_indices)
                oracle_model.train(
                    train, epochs=epoch_budget, gate_l1=0.001, edge_group_l1=0.001,
                )
                oracle_locked = evaluate(oracle_model, locked)["bit_accuracy"]
                oracle_ood = {}
                for other_family, other_triples in RULE_FAMILIES.items():
                    if other_family != family:
                        oracle_ood[other_family] = evaluate(
                            oracle_model, make_examples(locked_states, other_triples)
                        )["bit_accuracy"]
                ood = {}
                for other_family, other_triples in RULE_FAMILIES.items():
                    if other_family != family:
                        ood[other_family] = evaluate(
                            model, make_examples(locked_states, other_triples)
                        )["bit_accuracy"]
                record = {
                    "seed": seed, "train_family": family,
                    "selection_protocol": protocol,
                    "epochs_per_candidate": epoch_budget,
                    "train_examples": len(train),
                    "proposal_examples": len(proposal) if protocol == "proposal_split" else 0,
                    "locked_test_examples": len(locked),
                    "selected_motif_count": len(result["selected_motifs"]),
                    "candidate_fits": result["candidate_fits_total"],
                    "training_passes": epoch_budget * (1 + result["candidate_fits_total"]),
                    "selection_bce": result["proposal_selection_binary_cross_entropy"],
                    "selection_metric_source": "proposal" if protocol == "proposal_split" else "train",
                    "locked_test_bce": result["validation_binary_cross_entropy"],
                    "locked_test_bit_accuracy": result["validation"]["bit_accuracy"],
                    "ood_bit_accuracy_by_family": ood,
                    "oracle_locked_test_bit_accuracy": oracle_locked,
                    "oracle_ood_bit_accuracy_by_family": oracle_ood,
                    **support,
                }
                values = [
                    record["selection_bce"], record["locked_test_bce"],
                    record["locked_test_bit_accuracy"], record["oracle_locked_test_bit_accuracy"],
                    *ood.values(), *oracle_ood.values(),
                ]
                if not all(math.isfinite(value) for value in values):
                    raise AssertionError("non-finite selection benchmark metric")
                records.append(record)
    def summarize(rows):
        def mean(key):
            return sum(float(row[key]) for row in rows) / len(rows)
        ood_values = [
            value for row in rows
            for value in row["ood_bit_accuracy_by_family"].values()
        ]
        return {
            "experiments": len(rows),
            "mean_support_precision": mean("support_precision"),
            "mean_support_recall": mean("support_recall"),
            "mean_locked_test_bit_accuracy": mean("locked_test_bit_accuracy"),
            "mean_oracle_locked_test_bit_accuracy": mean("oracle_locked_test_bit_accuracy"),
            "mean_ood_bit_accuracy": sum(ood_values) / len(ood_values),
            "mean_oracle_ood_bit_accuracy": sum(
                value for row in rows
                for value in row["oracle_ood_bit_accuracy_by_family"].values()
            ) / (2 * len(rows)),
            "mean_selected_motifs": mean("selected_motif_count"),
            "mean_training_passes": mean("training_passes"),
            "exact_support_recovery_count": sum(
                row["support_precision"] == 1.0 and row["support_recall"] == 1.0
                for row in rows
            ),
        }
    by_protocol_and_budget = {
        f"{protocol}@{epoch_budget}": summarize([
            row for row in records
            if row["selection_protocol"] == protocol
            and row["epochs_per_candidate"] == epoch_budget
        ])
        for epoch_budget in epoch_budgets
        for protocol in ("proposal_split", "legacy_train_ranked")
    }
    return {
        "benchmark": "cpg-ei-proposal-selection-multiseed-v1",
        "seeds": list(seeds), "rule_families": list(RULE_FAMILIES),
        "split_sizes": {"train": 40, "proposal_selection": 12, "locked_test": 12},
        "optimizer": {"epochs_per_candidate": list(epoch_budgets), "max_motifs": max_motifs},
        "aggregate_by_protocol_and_budget": by_protocol_and_budget,
        "claim_boundary": "Synthetic finite six-bit rule families only; not open-ended relation induction or natural-language reasoning.",
        "records": records,
    }

def _parse_epochs(value: str):
    try:
        budgets = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("epochs must be comma-separated positive integers") from exc
    if not budgets or any(budget < 1 for budget in budgets):
        raise argparse.ArgumentTypeError("epochs must be comma-separated positive integers")
    return budgets


def _parse_seeds(value: str):
    try:
        seeds = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--epochs", type=_parse_epochs, default=(12, 120))
    parser.add_argument("--max-motifs", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_sweep(seeds=args.seeds, epochs=args.epochs, max_motifs=args.max_motifs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())