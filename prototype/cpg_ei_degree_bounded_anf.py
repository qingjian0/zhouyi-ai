"""Degree-bounded ANF identifiability under partial Boolean observations.

The exact truth table is used only for a clearly labelled oracle comparison.
All rank, consistency and uniqueness calculations use training observations.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from prototype.cpg_ei_anf_identifiability import (
    _state_mask, truth_table_to_anf,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def degree_bounded_basis(input_dim: int, max_degree: int) -> tuple[int, ...]:
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    if (isinstance(max_degree, bool) or not isinstance(max_degree, int)
            or not 0 <= max_degree <= input_dim):
        raise ValueError("max_degree must be between zero and input_dim")
    return tuple(mask for mask in range(1 << input_dim)
                 if mask.bit_count() <= max_degree)


def solve_gf2_restricted_basis(
    input_dim: int,
    observations: Iterable[tuple[Iterable[int], int]],
    basis_masks: Iterable[int],
) -> dict:
    """Solve the affine GF(2) system in an explicit monomial basis."""
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    basis = tuple(basis_masks)
    if (not basis or len(set(basis)) != len(basis)
            or any(isinstance(mask, bool) or not isinstance(mask, int)
                   or mask < 0 or mask >= (1 << input_dim) for mask in basis)):
        raise ValueError("basis_masks must be unique valid monomial masks")
    positions = {mask: index for index, mask in enumerate(basis)}
    width = len(basis)
    rows = []
    count = 0
    for state, target in observations:
        values = tuple(state)
        state_mask = _state_mask(values)
        if len(values) != input_dim or target not in (0, 1):
            raise ValueError("invalid observation")
        features = 0
        for monomial_mask, column in positions.items():
            if (monomial_mask & state_mask) == monomial_mask:
                features |= 1 << column
        rows.append(features | (int(target) << width))
        count += 1
    if not rows:
        raise ValueError("at least one observation is required")

    pivot_columns = []
    pivot_row = 0
    for column in range(width):
        selected = next((i for i in range(pivot_row, len(rows))
                         if (rows[i] >> column) & 1), None)
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        pivot = rows[pivot_row]
        for i in range(len(rows)):
            if i != pivot_row and ((rows[i] >> column) & 1):
                rows[i] ^= pivot
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(rows):
            break

    coefficient_mask = (1 << width) - 1
    inconsistent = any((row & coefficient_mask) == 0
                       and ((row >> width) & 1) for row in rows)
    rank = len(pivot_columns)
    pivot_set = set(pivot_columns)
    free_columns = [i for i in range(width) if i not in pivot_set]
    if inconsistent:
        return {
            "consistent": False, "observation_count": count,
            "coefficient_count": width, "rank": rank, "nullity": None,
            "unique": False, "particular_solution": None,
            "nullspace_basis": [], "coefficient_status": [],
        }

    pivot_rows = {column: rows[i] for i, column in enumerate(pivot_columns)}
    particular = 0
    for column, row in pivot_rows.items():
        if (row >> width) & 1:
            particular |= 1 << column
    nullspace = []
    for free in free_columns:
        vector = 1 << free
        for pivot, row in pivot_rows.items():
            if (row >> free) & 1:
                vector |= 1 << pivot
        nullspace.append(vector)
    statuses = []
    for column in range(width):
        variable = any((vector >> column) & 1 for vector in nullspace)
        value = (particular >> column) & 1
        statuses.append("ambiguous" if variable else
                        ("forced_one" if value else "forced_zero"))
    return {
        "consistent": True, "observation_count": count,
        "coefficient_count": width, "rank": rank,
        "nullity": width - rank, "unique": rank == width,
        "particular_solution": [(particular >> i) & 1 for i in range(width)],
        "nullspace_basis": nullspace, "coefficient_status": statuses,
    }


def run_degree_bounded_identifiability(corpus: dict) -> dict:
    manifest = corpus["manifest"]
    input_dim, output_dim = manifest["input_dim"], manifest["output_dim"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        grouped[row["family_id"]].append(row)
    family_results = []
    summaries = []
    family_degree_results = {family_id: [] for family_id in sorted(grouped)}
    for degree in range(input_dim + 1):
        basis = degree_bounded_basis(input_dim, degree)
        results = []
        for family_id in sorted(grouped):
            rows = grouped[family_id]
            ordered = sorted(rows, key=lambda row: _state_mask(row["state"]))
            training = [row for row in rows if row["state_split"] == "train"]
            for output in range(output_dim):
                oracle = truth_table_to_anf(
                    input_dim, [row["target"][output] for row in ordered]
                )
                oracle_degree = max(
                    (mask.bit_count() for mask, bit in enumerate(oracle) if bit),
                    default=0,
                )
                observations = [(row["state"], row["target"][output])
                                for row in training]
                system = solve_gf2_restricted_basis(input_dim, observations, basis)
                result = {
                    "family_id": family_id, "output_index": output,
                    "family_split": rows[0]["family_split"],
                    "training_observations": len(training),
                    "basis_size": len(basis), "rank": system["rank"],
                    "nullity": system["nullity"],
                    "consistent": system["consistent"],
                    "unique": system["unique"],
                    "oracle_degree": oracle_degree,
                    "oracle_in_basis": oracle_degree <= degree,
                }
                results.append(result)
                family_degree_results[family_id].append({
                    key: value for key, value in result.items()
                    if key not in ("family_id", "family_split")
                })
        consistent = [r for r in results if r["consistent"]]
        summaries.append({
            "max_degree": degree, "basis_size": len(basis),
            "output_systems": len(results),
            "mean_rank": sum(r["rank"] for r in results) / len(results),
            "consistent_system_count": len(consistent),
            "mean_nullity_among_consistent": (
                sum(r["nullity"] for r in consistent) / len(consistent)
                if consistent else None
            ),
            "consistent_rate": len(consistent) / len(results),
            "unique_rate": sum(r["unique"] for r in results) / len(results),
            "oracle_in_basis_rate": sum(r["oracle_in_basis"] for r in results) / len(results),
            "unique_and_oracle_in_basis_rate": sum(
                r["unique"] and r["oracle_in_basis"] for r in results
            ) / len(results),
        })
    for family_id in sorted(grouped):
        rows = grouped[family_id]
        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "by_degree": family_degree_results[family_id],
        })
    return {
        "benchmark_id": "zhouyi-cpg-ei-degree-bounded-anf-identifiability-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "dataset": {
            "seed": manifest["seed"], "families": manifest["family_count"],
            "rows": manifest["row_count"], "input_dim": input_dim,
            "output_dim": output_dim,
            "state_split_per_family": manifest["state_split_per_family"],
        },
        "basis": "All Boolean monomials with degree <= d, including constant",
        "observation_policy": "GF(2) systems use training observations only; development and locked labels never enter rank, consistency or uniqueness calculations.",
        "degree_summaries": summaries,
        "family_results": family_results,
        "claim_boundary": "Finite synthetic Boolean ANF identifiability under declared degree-bounded hypothesis classes only. Oracle degrees are report-only. This is not learned cross-family transfer, open-world discovery, causal discovery, Yi-Xue understanding or natural-language reasoning.",
    }


def write_json_report(report: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_degree_bounded_identifiability(corpus)
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
