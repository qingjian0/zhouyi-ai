"""Exhaustive finite-hypothesis baseline for mixed Boolean relation discovery.

This is a transparent symbolic baseline, not a learned neural model. It searches
an explicitly declared hypothesis space, selects using train then development
states, and reports locked states only after selection.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.cpg_ei_relation_operators import (
    OPERATORS, RelationRule, evaluate_rule, rule_manifest,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def enumerate_rule_hypotheses(input_dim: int) -> tuple[RelationRule, ...]:
    """Enumerate the benchmark's complete declared operator/support hypothesis space."""
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 3:
        raise ValueError("input_dim must be an integer >= 3")
    rules: list[RelationRule] = []
    for arity in range(2, min(6, input_dim) + 1):
        for support in itertools.combinations(range(input_dim), arity):
            rules.extend((
                RelationRule("xor", support),
                RelationRule("and", support),
                RelationRule("or", support),
                RelationRule("nand", support),
            ))
            for threshold in range(1, arity + 1):
                rules.append(RelationRule("threshold", support, threshold=threshold))
            for context_index in range(input_dim):
                if context_index in support:
                    continue
                for context_value in (0, 1):
                    rules.append(RelationRule(
                        "conditional_xor", support,
                        context_index=context_index, context_value=context_value,
                    ))
    for antecedent in range(input_dim):
        for consequent in range(input_dim):
            if antecedent != consequent:
                rules.append(RelationRule("implies", (antecedent, consequent)))
    return tuple(rules)


def _rule_key(rule: RelationRule) -> tuple[Any, ...]:
    return (
        rule.operator, rule.support, rule.threshold,
        rule.context_index, rule.context_value,
    )


def _state_index(state: tuple[int, ...]) -> int:
    return int("".join(str(bit) for bit in state), 2)


def _mask_for_rows(rows: list[dict], split: str) -> int:
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


def _truth_mask(rule: RelationRule, input_dim: int) -> int:
    mask = 0
    for state in itertools.product((0, 1), repeat=input_dim):
        if evaluate_rule(state, rule):
            mask |= 1 << _state_index(state)
    return mask


def _discover_one(
    rows: list[dict], output_index: int, candidates: tuple[tuple[RelationRule, int], ...],
    input_dim: int, teacher_rule: dict,
) -> dict[str, Any]:
    train_mask = _mask_for_rows(rows, "train")
    dev_mask = _mask_for_rows(rows, "development")
    locked_mask = _mask_for_rows(rows, "locked")
    target_mask = _target_mask(rows, output_index)

    # Training error is primary. Development error only resolves train-equivalent
    # candidates; the locked partition never participates in selection.
    scored = []
    best_train = None
    for rule, prediction_mask in candidates:
        train_error = ((prediction_mask ^ target_mask) & train_mask).bit_count()
        if best_train is None or train_error < best_train:
            best_train = train_error
            scored = [(rule, prediction_mask, train_error)]
        elif train_error == best_train:
            scored.append((rule, prediction_mask, train_error))

    best_dev = min(
        ((prediction_mask ^ target_mask) & dev_mask).bit_count()
        for _, prediction_mask, _ in scored
    )
    finalists = [
        (rule, prediction_mask, train_error)
        for rule, prediction_mask, train_error in scored
        if ((prediction_mask ^ target_mask) & dev_mask).bit_count() == best_dev
    ]
    selected_rule, selected_mask, train_error = min(
        finalists, key=lambda item: _rule_key(item[0])
    )

    locked_total = locked_mask.bit_count()
    locked_errors = ((selected_mask ^ target_mask) & locked_mask).bit_count()
    full_errors = (selected_mask ^ target_mask).bit_count()
    selected_spec = rule_manifest(selected_rule, input_dim)
    selected_equivalence_size = sum(
        prediction_mask == selected_mask for _, prediction_mask in candidates
    )
    teacher_object = RelationRule(
        teacher_rule["operator"], tuple(teacher_rule["support"]),
        threshold=teacher_rule["threshold"],
        context_index=teacher_rule["context_index"],
        context_value=(teacher_rule["context_value"]
                       if teacher_rule["context_value"] is not None else 1),
    )
    teacher_mask = _truth_mask(teacher_object, input_dim)
    teacher_equivalence_size = sum(
        prediction_mask == teacher_mask for _, prediction_mask in candidates
    )
    return {
        "train_errors": train_error,
        "development_errors": best_dev,
        "locked_bit_accuracy": (
            1.0 - locked_errors / locked_total if locked_total else None
        ),
        "full_truth_table_exact": full_errors == 0,
        "operator_recovered": selected_rule.operator == teacher_rule["operator"],
        "exact_rule_recovered": selected_spec == teacher_rule,
        "train_minimizer_count": len(scored),
        "development_tie_count": len(finalists),
        "selected_function_equivalence_class_size": selected_equivalence_size,
        "selected_function_structurally_identifiable": selected_equivalence_size == 1,
        "teacher_function_equivalence_class_size": teacher_equivalence_size,
        "teacher_function_structurally_identifiable": teacher_equivalence_size == 1,
        "selected_rule": selected_spec,
    }


def run_discovery_benchmark(corpus: dict) -> dict[str, Any]:
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    candidates = tuple(
        (rule, _truth_mask(rule, input_dim))
        for rule in enumerate_rule_hypotheses(input_dim)
    )
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)
    teachers = {item["family_id"]: item for item in corpus["teachers"]}

    family_results = []
    for family_id in sorted(rows_by_family):
        family_rows = rows_by_family[family_id]
        teacher = teachers[family_id]
        output_results = [
            _discover_one(
                family_rows, output_index, candidates, input_dim,
                teacher["rules"][output_index],
            )
            for output_index in range(manifest["output_dim"])
        ]
        family_results.append({
            "family_id": family_id,
            "family_split": family_rows[0]["family_split"],
            "output_results": output_results,
        })

    def summarize(selected: list[dict]) -> dict[str, Any]:
        outputs = [item for family in selected for item in family["output_results"]]
        if not outputs:
            return {"families": 0, "outputs": 0}
        count = len(outputs)
        return {
            "families": len(selected),
            "outputs": count,
            "mean_locked_bit_accuracy": sum(
                item["locked_bit_accuracy"] for item in outputs
                if item["locked_bit_accuracy"] is not None
            ) / sum(item["locked_bit_accuracy"] is not None for item in outputs),
            "full_truth_table_exact_rate": sum(
                item["full_truth_table_exact"] for item in outputs
            ) / count,
            "operator_recovery_rate": sum(
                item["operator_recovered"] for item in outputs
            ) / count,
            "exact_rule_recovery_rate": sum(
                item["exact_rule_recovered"] for item in outputs
            ) / count,
            "mean_train_minimizer_count": sum(
                item["train_minimizer_count"] for item in outputs
            ) / count,
            "mean_development_tie_count": sum(
                item["development_tie_count"] for item in outputs
            ) / count,
            "teacher_function_identifiability_rate": sum(
                item["teacher_function_structurally_identifiable"] for item in outputs
            ) / count,
            "mean_teacher_function_equivalence_class_size": sum(
                item["teacher_function_equivalence_class_size"] for item in outputs
            ) / count,
        }

    by_split = {
        split: summarize([
            item for item in family_results if item["family_split"] == split
        ])
        for split in ("train", "development", "locked")
    }
    return {
        "benchmark_id": "zhouyi-cpg-ei-mixed-operator-discovery-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "candidate_hypothesis_count": len(candidates),
        "candidate_space_operators": list(OPERATORS),
        "selection_protocol": (
            "minimum train error; development error breaks train ties; "
            "locked states are report-only"
        ),
        "family_split_interpretation": (
            "The family split is a reporting stratum, not a zero-shot transfer test: "
            "every family, including the locked family stratum, receives its own "
            "train and development states for per-family symbolic adaptation. "
            "Only state_split=locked is held out from candidate selection."
        ),
        "candidate_truth_function_count": len({mask for _, mask in candidates}),
        "candidate_structural_alias_count": (
            len(candidates) - len({mask for _, mask in candidates})
        ),
        "family_split_results": by_split,
        "family_results": family_results,
        "claim_boundary": (
            "Exhaustive symbolic finite-hypothesis baseline over the declared "
            "synthetic Boolean rule space. It is not neural training, open-world "
            "relation induction, natural-language reasoning, or a Transformer comparison."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=400)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    result = run_discovery_benchmark(corpus)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        key: value for key, value in result.items()
        if key not in ("family_results",)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
