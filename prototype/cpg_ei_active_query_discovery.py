"""Active-query finite-hypothesis discovery with a paired random-query control.

Queries are selected from each teacher's training-state pool using candidate
disagreement only. Development labels break ties after acquisition; locked
labels are report-only. Teacher manifests are used only for post-hoc scoring.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import (
    _rule_key,
    _truth_mask,
    enumerate_rule_hypotheses,
)
from prototype.cpg_ei_relation_operators import RelationRule, rule_manifest


def _state_index(state: tuple[int, ...]) -> int:
    return int("".join(str(bit) for bit in state), 2)


def _split_mask(rows: list[dict], split: str) -> int:
    mask = 0
    for row in rows:
        if row["state_split"] == split:
            mask |= 1 << _state_index(tuple(row["state"]))
    return mask


def _target_mask(rows: list[dict], output_index: int) -> int:
    mask = 0
    for row in rows:
        if row["target"][output_index]:
            mask |= 1 << _state_index(tuple(row["state"]))
    return mask


def _compress_truth_mask(full_mask: int, train_states: list[tuple[int, ...]]) -> int:
    pattern = 0
    for position, state in enumerate(train_states):
        if (full_mask >> _state_index(state)) & 1:
            pattern |= 1 << position
    return pattern


def _max_disagreement_position(
    patterns: Iterable[int], available_positions: list[int]
) -> int | None:
    """Select the most balanced candidate split using bit-sliced population counts."""
    unique_patterns = tuple(set(patterns))
    hypothesis_count = len(unique_patterns)
    if hypothesis_count < 2 or not available_positions:
        return None

    plane_count = max(1, hypothesis_count.bit_length())
    planes = [0] * plane_count
    for pattern in unique_patterns:
        carry = pattern
        bit_index = 0
        while carry and bit_index < len(planes):
            previous = planes[bit_index]
            planes[bit_index] = previous ^ carry
            carry = previous & carry
            bit_index += 1
        if carry:
            raise AssertionError("bit-sliced disagreement counter overflow")

    best_position = None
    best_score = 0
    for position in available_positions:
        ones = sum(
            ((plane >> position) & 1) << bit_index
            for bit_index, plane in enumerate(planes)
        )
        score = min(ones, hypothesis_count - ones)
        if score > best_score:
            best_score = score
            best_position = position
    return best_position


def _active_query_order(
    pattern_to_candidates: dict[int, list[tuple[RelationRule, int]]],
    train_labels: list[int],
) -> list[int]:
    survivors = set(pattern_to_candidates)
    available = list(range(len(train_labels)))
    selected = []
    while available:
        position = _max_disagreement_position(survivors, available)
        if position is None:
            break
        selected.append(position)
        label = train_labels[position]
        survivors = {
            pattern for pattern in survivors
            if ((pattern >> position) & 1) == label
        }
        available.remove(position)
        if not survivors:
            raise AssertionError("the teacher rule must remain in the version space")
    return selected


def _filter_version_space(
    initial_patterns: Iterable[int],
    query_order: list[int],
    labels: list[int],
    budget: int,
) -> tuple[set[int], list[int]]:
    survivors = set(initial_patterns)
    used = query_order[:budget]
    for position in used:
        label = labels[position]
        survivors = {
            pattern for pattern in survivors
            if ((pattern >> position) & 1) == label
        }
    return survivors, used


def _select_candidate(
    survivors: set[int],
    pattern_to_candidates: dict[int, list[tuple[RelationRule, int]]],
    dev_mask: int,
    target_mask: int,
    locked_mask: int,
    teacher_rule: dict,
    input_dim: int,
) -> dict[str, Any]:
    finalists = []
    best_dev_error = None
    for pattern in survivors:
        for rule, full_mask in pattern_to_candidates[pattern]:
            dev_error = ((full_mask ^ target_mask) & dev_mask).bit_count()
            if best_dev_error is None or dev_error < best_dev_error:
                best_dev_error = dev_error
                finalists = [(rule, full_mask)]
            elif dev_error == best_dev_error:
                finalists.append((rule, full_mask))
    if not finalists:
        raise AssertionError("version space unexpectedly became empty")
    selected_rule, selected_mask = min(
        finalists, key=lambda item: _rule_key(item[0])
    )
    locked_total = locked_mask.bit_count()
    locked_errors = ((selected_mask ^ target_mask) & locked_mask).bit_count()
    distinct_functions = {
        full_mask
        for pattern in survivors
        for _, full_mask in pattern_to_candidates[pattern]
    }
    structural_count = sum(
        len(pattern_to_candidates[pattern]) for pattern in survivors
    )
    teacher_object = RelationRule(
        teacher_rule["operator"], tuple(teacher_rule["support"]),
        threshold=teacher_rule["threshold"],
        context_index=teacher_rule["context_index"],
        context_value=(
            teacher_rule["context_value"]
            if teacher_rule["context_value"] is not None else 1
        ),
    )
    # Teacher manifests are consulted only after selection, for evaluation.
    teacher_mask = _truth_mask(teacher_object, input_dim)
    selected_spec = rule_manifest(selected_rule, input_dim)
    return {
        "development_errors": best_dev_error,
        "locked_bit_accuracy": (
            1.0 - locked_errors / locked_total if locked_total else None
        ),
        "full_truth_table_function_recovered": selected_mask == teacher_mask,
        "operator_recovered": selected_rule.operator == teacher_rule["operator"],
        "exact_rule_recovered": selected_spec == teacher_rule,
        "selected_rule": selected_spec,
        "train_pattern_version_space_size": len(survivors),
        "full_function_version_space_size": len(distinct_functions),
        "structural_hypothesis_count": structural_count,
    }


def _summarize(rows: list[dict]) -> dict:
    count = len(rows)
    return {
        "output_count": count,
        "mean_query_count": sum(row["query_count"] for row in rows) / count,
        "mean_train_pattern_version_space_size": sum(
            row["train_pattern_version_space_size"] for row in rows
        ) / count,
        "mean_full_function_version_space_size": sum(
            row["full_function_version_space_size"] for row in rows
        ) / count,
        "mean_structural_hypothesis_count": sum(
            row["structural_hypothesis_count"] for row in rows
        ) / count,
        "mean_locked_bit_accuracy": sum(
            row["locked_bit_accuracy"] for row in rows
        ) / count,
        "full_function_recovery_rate": sum(
            row["full_truth_table_function_recovered"] for row in rows
        ) / count,
        "operator_recovery_rate": sum(
            row["operator_recovered"] for row in rows
        ) / count,
        "exact_rule_recovery_rate": sum(
            row["exact_rule_recovered"] for row in rows
        ) / count,
    }


def run_active_query_benchmark(
    corpus: dict,
    *,
    query_budgets: tuple[int, ...] = (8, 16, 32, 64, 128),
    seed: int = 20261115,
) -> dict:
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    if (
        not query_budgets
        or tuple(sorted(set(query_budgets))) != query_budgets
        or any(isinstance(budget, bool) or not isinstance(budget, int) or budget < 1
               for budget in query_budgets)
    ):
        raise ValueError("query_budgets must be a non-empty sorted tuple of positive integers")

    candidates = tuple(
        (rule, _truth_mask(rule, input_dim))
        for rule in enumerate_rule_hypotheses(input_dim)
    )
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)
    teachers = {item["family_id"]: item for item in corpus["teachers"]}

    method_rows: dict[str, dict[int, list[dict]]] = {
        method: {budget: [] for budget in query_budgets}
        for method in ("active", "random")
    }
    family_results = []
    for family_index, family_id in enumerate(sorted(rows_by_family)):
        rows = rows_by_family[family_id]
        train_rows = sorted(
            [row for row in rows if row["state_split"] == "train"],
            key=lambda row: _state_index(tuple(row["state"])),
        )
        train_states = [tuple(row["state"]) for row in train_rows]
        if max(query_budgets) > len(train_rows):
            raise ValueError("query budget exceeds available training-state pool")
        teacher = teachers[family_id]
        dev_mask = _split_mask(rows, "development")
        locked_mask = _split_mask(rows, "locked")
        family_outputs = []
        for output_index in range(output_dim):
            target_mask = _target_mask(rows, output_index)
            teacher_rule = teacher["rules"][output_index]
            pattern_to_candidates: dict[
                int, list[tuple[RelationRule, int]]
            ] = defaultdict(list)
            for rule, full_mask in candidates:
                pattern = _compress_truth_mask(full_mask, train_states)
                pattern_to_candidates[pattern].append((rule, full_mask))
            train_labels = [row["target"][output_index] for row in train_rows]
            active_order = _active_query_order(pattern_to_candidates, train_labels)
            random_order = list(range(len(train_rows)))
            random.Random(
                seed + family_index * 1009 + output_index * 9176
            ).shuffle(random_order)

            budget_results = []
            for budget in query_budgets:
                active_survivors, active_used = _filter_version_space(
                    pattern_to_candidates, active_order, train_labels, budget
                )
                random_survivors, random_used = _filter_version_space(
                    pattern_to_candidates, random_order, train_labels, budget
                )
                active_result = _select_candidate(
                    active_survivors, pattern_to_candidates, dev_mask,
                    target_mask, locked_mask, teacher_rule, input_dim,
                )
                random_result = _select_candidate(
                    random_survivors, pattern_to_candidates, dev_mask,
                    target_mask, locked_mask, teacher_mask, teacher_rule, input_dim,
                )
                active_record = {
                    "family_id": family_id,
                    "output_index": output_index,
                    "method": "active",
                    "budget": budget,
                    "query_count": len(active_used),
                    "query_state_indices": [
                        _state_index(train_states[position]) for position in active_used
                    ],
                    **active_result,
                }
                random_record = {
                    "family_id": family_id,
                    "output_index": output_index,
                    "method": "random",
                    "budget": budget,
                    "query_count": len(random_used),
                    "query_state_indices": [
                        _state_index(train_states[position]) for position in random_used
                    ],
                    **random_result,
                }
                method_rows["active"][budget].append(active_record)
                method_rows["random"][budget].append(random_record)
                budget_results.append({
                    "budget": budget,
                    "active": active_record,
                    "random": random_record,
                })
            family_outputs.append({
                "output_index": output_index,
                "active_query_order": [
                    _state_index(train_states[position]) for position in active_order
                ],
                "random_query_order": [
                    _state_index(train_states[position]) for position in random_order
                ],
                "budget_results": budget_results,
            })
        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "output_results": family_outputs,
        })

    summary = {
        method: {
            str(budget): _summarize(records)
            for budget, records in by_budget.items()
        }
        for method, by_budget in method_rows.items()
    }
    return {
        "benchmark_id": "zhouyi-cpg-ei-active-query-discovery-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "seed": seed,
        "query_budgets": list(query_budgets),
        "candidate_hypothesis_count": len(candidates),
        "query_policy": (
            "At each step choose an unqueried training state maximizing the "
            "balanced split of distinct candidate predictions; stop when no "
            "remaining training state distinguishes the surviving version space."
        ),
        "selection_protocol": (
            "Query labels update the version space; development labels only break "
            "ties among surviving candidates; locked labels are report-only."
        ),
        "teacher_manifest_boundary": (
            "Teacher manifests are used only after candidate selection to score "
            "operator/rule/function recovery. They do not determine queries, "
            "filter candidates, or choose the selected rule."
        ),
        "family_split_interpretation": (
            "Family split is a reporting stratum, not zero-shot transfer. Each "
            "family receives its own active/random training queries."
        ),
        "summary": summary,
        "family_results": family_results,
        "claim_boundary": (
            "Finite synthetic Boolean active-query diagnosis over the declared "
            "finite operator grammar. This is not causal discovery, open-world "
            "induction, cross-family meta-learning, Yi-Xue understanding, "
            "natural-language reasoning, or evidence of Transformer superiority."
        ),
    }


def write_json_report(report: dict, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--query-seed", type=int, default=20261115)
    parser.add_argument("--query-budgets", type=int, nargs="+", default=[8, 16, 32, 64, 128])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_active_query_benchmark(
        corpus, query_budgets=tuple(args.query_budgets), seed=args.query_seed
    )
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps({
        "corpus_sha256": report["corpus_sha256"],
        "candidate_hypothesis_count": report["candidate_hypothesis_count"],
        "query_budgets": report["query_budgets"],
        "summary": report["summary"],
        "claim_boundary": report["claim_boundary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
