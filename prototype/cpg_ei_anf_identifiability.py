"""ANF truth-table oracle and GF(2) partial-observation identifiability audit.

The complete truth table is used only for an explicit oracle reference. The
partial-observation solver receives only the selected observations and reports
the affine solution space; it never treats one arbitrary solution as unique.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def _state_mask(state: Iterable[int]) -> int:
    values = tuple(state)
    if not values or any(bit not in (0, 1) for bit in values):
        raise ValueError("state must be a non-empty binary vector")
    return sum(int(bit) << index for index, bit in enumerate(values))


def truth_table_to_anf(input_dim: int, outputs: Iterable[int]) -> tuple[int, ...]:
    """Return GF(2) ANF coefficients indexed by little-endian variable masks."""
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    values = list(outputs)
    expected = 1 << input_dim
    if len(values) != expected or any(value not in (0, 1) for value in values):
        raise ValueError("outputs must contain exactly 2**input_dim binary values")
    coefficients = [int(value) for value in values]
    for variable_bit in range(input_dim):
        for mask in range(expected):
            if mask & (1 << variable_bit):
                coefficients[mask] ^= coefficients[mask ^ (1 << variable_bit)]
    return tuple(coefficients)


def evaluate_anf(state: Iterable[int], coefficients: Iterable[int]) -> int:
    state_tuple = tuple(state)
    state_bits = _state_mask(state_tuple)
    coeffs = tuple(coefficients)
    if not coeffs or any(value not in (0, 1) for value in coeffs):
        raise ValueError("coefficients must be a non-empty binary vector")
    if len(coeffs) != 1 << len(state_tuple):
        raise ValueError("coefficient count must equal 2**input_dim")
    result = 0
    for monomial_mask, coefficient in enumerate(coeffs):
        if coefficient and (monomial_mask & state_bits) == monomial_mask:
            result ^= 1
    return result


def _monomial_feature_mask(state: Iterable[int], input_dim: int) -> int:
    state_tuple = tuple(state)
    state_bits = _state_mask(state_tuple)
    if len(state_tuple) != input_dim:
        raise ValueError("state dimension mismatch")
    result = 0
    for monomial_mask in range(1 << input_dim):
        if (monomial_mask & state_bits) == monomial_mask:
            result |= 1 << monomial_mask
    return result


def solve_gf2_affine_system(
    input_dim: int,
    observations: Iterable[tuple[Iterable[int], int]],
    *,
    max_degree: int | None = None,
) -> dict:
    """Solve observed ANF equations in the complete or degree-limited basis."""
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    if max_degree is not None and (
        isinstance(max_degree, bool) or not isinstance(max_degree, int)
        or max_degree < 0 or max_degree > input_dim
    ):
        raise ValueError("max_degree must be an integer in [0, input_dim]")
    basis_masks = tuple(
        mask for mask in range(1 << input_dim)
        if max_degree is None or mask.bit_count() <= max_degree
    )
    coefficient_count = len(basis_masks)
    rows = []
    for state, target in observations:
        state_tuple = tuple(state)
        if (len(state_tuple) != input_dim or any(bit not in (0, 1) for bit in state_tuple)
                or target not in (0, 1)):
            raise ValueError("invalid observation")
        state_bits = _state_mask(state_tuple)
        feature_mask = 0
        for column, monomial_mask in enumerate(basis_masks):
            if (monomial_mask & state_bits) == monomial_mask:
                feature_mask |= 1 << column
        rows.append(feature_mask | (int(target) << coefficient_count))
    if not rows:
        raise ValueError("at least one observation is required")

    pivot_columns = []
    pivot_row = 0
    for column in range(coefficient_count):
        selected = next(
            (index for index in range(pivot_row, len(rows))
             if (rows[index] >> column) & 1),
            None,
        )
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        pivot_value = rows[pivot_row]
        for index in range(len(rows)):
            if index != pivot_row and ((rows[index] >> column) & 1):
                rows[index] ^= pivot_value
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == len(rows):
            break

    coefficient_mask = (1 << coefficient_count) - 1
    inconsistent = any(
        (row & coefficient_mask) == 0 and ((row >> coefficient_count) & 1)
        for row in rows
    )
    rank = len(pivot_columns)
    free_columns = [column for column in range(coefficient_count)
                    if column not in set(pivot_columns)]
    if inconsistent:
        return {
            "consistent": False,
            "observation_count": len(rows),
            "coefficient_count": coefficient_count,
            "basis_monomial_masks": list(basis_masks),
            "max_degree": max_degree,
            "rank": rank,
            "nullity": None,
            "unique": False,
            "pivot_columns": pivot_columns,
            "free_columns": free_columns,
            "particular_solution": None,
            "nullspace_basis": [],
            "coefficient_status": [],
        }

    particular = 0
    pivot_row_by_column = {
        column: rows[index] for index, column in enumerate(pivot_columns)
    }
    for column, row in pivot_row_by_column.items():
        if (row >> coefficient_count) & 1:
            particular |= 1 << column

    nullspace = []
    for free_column in free_columns:
        vector = 1 << free_column
        for pivot_column, row in pivot_row_by_column.items():
            if (row >> free_column) & 1:
                vector |= 1 << pivot_column
        nullspace.append(vector)

    statuses = []
    for column in range(coefficient_count):
        can_vary = any((vector >> column) & 1 for vector in nullspace)
        value = (particular >> column) & 1
        statuses.append(
            "ambiguous" if can_vary else ("forced_one" if value else "forced_zero")
        )
    return {
        "consistent": True,
        "observation_count": len(rows),
        "coefficient_count": coefficient_count,
        "basis_monomial_masks": list(basis_masks),
        "max_degree": max_degree,
        "rank": rank,
        "nullity": coefficient_count - rank,
        "unique": rank == coefficient_count,
        "pivot_columns": pivot_columns,
        "free_columns": free_columns,
        "particular_solution": [
            (particular >> index) & 1 for index in range(coefficient_count)
        ],
        "nullspace_basis": nullspace,
        "coefficient_status": statuses,
    }


def _support_variables(coefficients: Iterable[int], input_dim: int) -> list[int]:
    selected = [
        mask for mask, coefficient in enumerate(coefficients)
        if coefficient and mask != 0
    ]
    return sorted({
        variable for mask in selected
        for variable in range(input_dim) if (mask >> variable) & 1
    })


def _anf_summary(coefficients: tuple[int, ...], input_dim: int) -> dict:
    terms = [mask for mask, value in enumerate(coefficients) if value]
    degrees = [mask.bit_count() for mask in terms]
    return {
        "nonzero_term_count": len(terms),
        "degree": max(degrees, default=0),
        "support_variables": _support_variables(coefficients, input_dim),
        "monomial_masks": terms,
    }


def _variable_identifiability(system: dict, input_dim: int) -> dict:
    if not system["consistent"]:
        return {"definitely_relevant": [], "possibly_relevant": list(range(input_dim)),
                "definitely_irrelevant": []}
    statuses = system["coefficient_status"]
    basis_masks = system["basis_monomial_masks"]
    definitely_relevant = []
    possibly_relevant = []
    definitely_irrelevant = []
    for variable in range(input_dim):
        involved_statuses = [
            statuses[column]
            for column, monomial_mask in enumerate(basis_masks)
            if monomial_mask and ((monomial_mask >> variable) & 1)
        ]
        if any(status == "forced_one" for status in involved_statuses):
            definitely_relevant.append(variable)
        elif any(status == "ambiguous" for status in involved_statuses):
            possibly_relevant.append(variable)
        else:
            definitely_irrelevant.append(variable)
    return {
        "definitely_relevant": definitely_relevant,
        "possibly_relevant": possibly_relevant,
        "definitely_irrelevant": definitely_irrelevant,
    }


def run_anf_identifiability_audit(corpus: dict) -> dict:
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        grouped[row["family_id"]].append(row)

    family_results = []
    total_rank = 0
    total_nullity = 0
    total_outputs = 0
    unique_count = 0
    for family_id in sorted(grouped):
        rows = grouped[family_id]
        all_rows = sorted(rows, key=lambda row: _state_mask(row["state"]))
        train_rows = [row for row in rows if row["state_split"] == "train"]
        output_results = []
        for output_index in range(output_dim):
            truth = [row["target"][output_index] for row in all_rows]
            exact_coefficients = truth_table_to_anf(input_dim, truth)
            # The solver sees only train observations. Full labels are used only
            # to compute the separately labelled truth-table oracle reference.
            observations = [
                (row["state"], row["target"][output_index]) for row in train_rows
            ]
            system = solve_gf2_affine_system(input_dim, observations)
            identifiability = _variable_identifiability(system, input_dim)
            exact_summary = _anf_summary(exact_coefficients, input_dim)
            total_rank += system["rank"]
            total_nullity += system["nullity"] or 0
            total_outputs += 1
            unique_count += int(system["unique"])
            output_results.append({
                "output_index": output_index,
                "training_observations": len(observations),
                "system_rank": system["rank"],
                "system_nullity": system["nullity"],
                "unique_anf_from_training": system["unique"],
                "truth_table_oracle": exact_summary,
                "training_identifiability": identifiability,
                "oracle_support_is_contained_in_possible_support": all(
                    variable in (
                        identifiability["definitely_relevant"]
                        + identifiability["possibly_relevant"]
                    )
                    for variable in exact_summary["support_variables"]
                ),
            })
        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "output_results": output_results,
        })

    return {
        "benchmark_id": "zhouyi-cpg-ei-anf-identifiability-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "dataset": {
            "seed": manifest["seed"],
            "families": manifest["family_count"],
            "rows": manifest["row_count"],
            "input_dim": input_dim,
            "output_dim": output_dim,
            "state_split_per_family": manifest["state_split_per_family"],
        },
        "basis": {
            "type": "complete Boolean ANF over GF(2)",
            "coefficient_count_including_constant": 1 << input_dim,
            "monomial_order": "little-endian variable bit masks; bit i denotes x_i",
        },
        "training_identifiability_summary": {
            "output_systems": total_outputs,
            "mean_rank": total_rank / total_outputs,
            "mean_nullity": total_nullity / total_outputs,
            "unique_training_anf_rate": unique_count / total_outputs,
        },
        "oracle_boundary": (
            "The full truth table is used only to compute exact ANF reference "
            "coefficients. The GF(2) system is built exclusively from training "
            "observations. The oracle does not feed coefficients or teacher rules "
            "into the partial-observation solver or any learner."
        ),
        "claim_boundary": (
            "Exact algebraic representation and linear identifiability diagnostics "
            "for finite synthetic Boolean truth tables only. This is not a learned "
            "model, cross-family transfer, open-world induction, causal discovery, "
            "Yi-Xue understanding, or natural-language reasoning."
        ),
        "degree_sweep": run_anf_degree_sweep(corpus),
        "family_results": family_results,
    }




def run_anf_degree_sweep(corpus: dict) -> dict:
    """Measure representation and training identifiability at each ANF degree."""
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        grouped[row["family_id"]].append(row)

    degree_results = []
    for max_degree in range(input_dim + 1):
        systems = []
        for family_id in sorted(grouped):
            rows = grouped[family_id]
            all_rows = sorted(rows, key=lambda row: _state_mask(row["state"]))
            train_rows = [row for row in rows if row["state_split"] == "train"]
            for output_index in range(output_dim):
                oracle = truth_table_to_anf(
                    input_dim, [row["target"][output_index] for row in all_rows]
                )
                oracle_degree = max(
                    (mask.bit_count() for mask, value in enumerate(oracle) if value),
                    default=0,
                )
                representable = oracle_degree <= max_degree
                observations = [
                    (row["state"], row["target"][output_index])
                    for row in train_rows
                ]
                system = solve_gf2_affine_system(
                    input_dim, observations, max_degree=max_degree
                )
                identifiability = _variable_identifiability(system, input_dim)
                oracle_support = _support_variables(oracle, input_dim)
                possible_support = (
                    identifiability["definitely_relevant"]
                    + identifiability["possibly_relevant"]
                )
                systems.append({
                    "family_id": family_id,
                    "output_index": output_index,
                    "oracle_degree": oracle_degree,
                    "oracle_representable": representable,
                    "training_system_consistent": system["consistent"],
                    "rank": system["rank"],
                    "nullity": system["nullity"],
                    "unique": system["unique"],
                    "oracle_support": oracle_support,
                    "possible_support": sorted(possible_support),
                    "oracle_support_contained": (
                        all(variable in possible_support for variable in oracle_support)
                        if representable and system["consistent"] else None
                    ),
                })
        consistent_systems = [
            item for item in systems if item["training_system_consistent"]
        ]
        degree_results.append({
            "max_degree": max_degree,
            "basis_coefficient_count": sum(
                1 for mask in range(1 << input_dim)
                if mask.bit_count() <= max_degree
            ),
            "output_system_count": len(systems),
            "consistent_system_count": len(consistent_systems),
            "inconsistent_system_count": len(systems) - len(consistent_systems),
            "oracle_representability_rate": sum(
                item["oracle_representable"] for item in systems
            ) / len(systems),
            "training_consistency_rate": sum(
                item["training_system_consistent"] for item in systems
            ) / len(systems),
            "unique_training_solution_rate": sum(
                item["unique"] for item in systems
            ) / len(systems),
            "mean_training_rank": sum(item["rank"] for item in systems) / len(systems),
            "mean_training_nullity": (
                sum(item["nullity"] for item in consistent_systems)
                / len(consistent_systems) if consistent_systems else None
            ),
            "oracle_support_containment_rate_when_representable": (
                sum(item["oracle_support_contained"] is True for item in systems)
                / max(1, sum(item["oracle_support_contained"] is not None for item in systems))
            ),
            "per_output": systems,
        })
    return {
        "basis_definition": "ANF monomials with degree <= max_degree, including constant",
        "degree_results": degree_results,
        "interpretation": (
            "Degree restriction reduces the coefficient space but may exclude "
            "higher-degree teacher functions. Rates are computed on the same "
            "training partition; full truth tables are used only for the labelled "
            "oracle degree/representability reference."
        ),
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
    from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_anf_identifiability_audit(corpus)
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
