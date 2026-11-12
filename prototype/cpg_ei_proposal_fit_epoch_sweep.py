"""Measure CPG-EI proposal-selection sensitivity to candidate fit epochs."""
from __future__ import annotations

import argparse
import json
from typing import Iterable, Sequence

from prototype.cpg_ei_selection_sweep import DEFAULT_SEEDS, run_sweep

DEFAULT_EPOCHS = (12, 25, 50)


def _parse_int_list(value: str, label: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be comma-separated integers") from exc
    if not values or any(value < 1 for value in values) or len(set(values)) != len(values):
        raise argparse.ArgumentTypeError(f"{label} must contain unique positive integers")
    return values


def run_epoch_sweep(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    epochs: Sequence[int] = DEFAULT_EPOCHS,
    max_motifs: int = 3,
) -> dict:
    if not seeds or not epochs or any(value < 1 for value in epochs):
        raise ValueError("seeds and positive epoch counts are required")
    reports = {}
    records = []
    for fit_epochs in epochs:
        report = run_sweep(seeds=seeds, epochs=fit_epochs, max_motifs=max_motifs)
        reports[str(fit_epochs)] = report["aggregate_by_protocol"]
        records.extend(
            {"epochs_per_candidate": fit_epochs, **row}
            for row in report["records"]
        )
    return {
        "benchmark": "cpg-ei-proposal-fit-epoch-sensitivity-v1",
        "seeds": list(seeds),
        "epochs_per_candidate": list(epochs),
        "split_sizes": {"train": 40, "proposal_selection": 12, "locked_test": 12},
        "rule_families": ["A", "B", "C"],
        "optimizer": {"max_motifs": max_motifs},
        "aggregate_by_epoch_and_protocol": reports,
        "records": records,
        "claim_boundary": (
            "Finite synthetic six-bit rule families only. Fit-epoch sensitivity "
            "does not establish open-ended relation induction or natural-language reasoning."
        ),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--epochs", default=",".join(map(str, DEFAULT_EPOCHS)))
    parser.add_argument("--max-motifs", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    seeds = _parse_int_list(args.seeds, "seeds")
    epochs = _parse_int_list(args.epochs, "epochs")
    report = run_epoch_sweep(seeds=seeds, epochs=epochs, max_motifs=args.max_motifs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
