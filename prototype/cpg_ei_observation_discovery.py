"""Observation-only discovery baseline for mixed Boolean relation teachers.

The baseline does not receive teacher rules during inference. It infers relevant
variables from observed training pairs, enumerates operators on that support,
and evaluates the surviving hypotheses on development/locked states.
Teacher manifests are used only after inference to score recovery.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_relation_operators import (
    OPERATORS, RelationRule, evaluate_rule, rule_manifest,
)


def _infer_support(train_rows: list[dict], input_dim: int) -> tuple[int, ...]:
    observed = {tuple(row["state"]): row["target_value"] for row in train_rows}
    relevant = []
    for index in range(input_dim):
        bit = 1 << index
        found = False
        for state, target in observed.items():
            if state[index] != 0:
                continue
            counterpart = list(state)
            counterpart[index] = 1
            other = tuple(counterpart)
            if other in observed and observed[other] != target:
                found = True
                break
        if found:
            relevant.append(index)
    return tuple(relevant)


def _candidate_rules(relevant: tuple[int, ...], input_dim: int):
    n = len(relevant)
    if n < 2:
        return
    support = tuple(relevant)
    for operator in ("xor", "and", "or", "nand"):
        yield RelationRule(operator, support)
    if n == 2:
        yield RelationRule("implies", support)
        yield RelationRule("implies", tuple(reversed(support)))
    for threshold in range(1, n + 1):
        yield RelationRule("threshold", support, threshold=threshold)
    for context in relevant:
        operands = tuple(index for index in relevant if index != context)
        if len(operands) < 2:
            continue
        for context_value in (0, 1):
            yield RelationRule(
                "conditional_xor", operands,
                context_index=context, context_value=context_value,
            )


def _evaluate_candidate(rule: RelationRule, rows: list[dict]) -> tuple[int, ...]:
    return tuple(evaluate_rule(tuple(row["state"]), rule) for row in rows)


def _score_rule_group(
    train_rows: list[dict], development_rows: list[dict],
    locked_rows: list[dict], truth_spec: dict, input_dim: int,
) -> dict:
    inferred_support = _infer_support(train_rows, input_dim)
    candidates = []
    for rule in _candidate_rules(inferred_support, input_dim) or ():
        train_prediction = _evaluate_candidate(rule, train_rows)
        train_target = tuple(row["target_value"] for row in train_rows)
        if train_prediction != train_target:
            continue
        development_prediction = _evaluate_candidate(rule, development_rows)
        locked_prediction = _evaluate_candidate(rule, locked_rows)
        spec = rule_manifest(rule, input_dim)
        candidates.append({
            "spec": spec,
            "development_correct": sum(
                prediction == row["target_value"]
                for prediction, row in zip(development_prediction, development_rows)
            ),
            "locked_correct": sum(
                prediction == row["target_value"]
                for prediction, row in zip(locked_prediction, locked_rows)
            ),
            "development_prediction": development_prediction,
            "locked_prediction": locked_prediction,
        })

    truth_relevant = set(truth_spec["support"])
    if truth_spec["operator"] == "conditional_xor":
        truth_relevant.add(truth_spec["context_index"])
    true_spec = dict(truth_spec)
    true_spec["role_order"] = (
        list(truth_spec["support"]) if truth_spec["operator"] == "implies" else None
    )
    exact_candidate = any(
        item["spec"] == true_spec for item in candidates
    )
    candidate_ops = sorted({item["spec"]["operator"] for item in candidates})
    all_locked = [item["locked_prediction"] for item in candidates]
    consensus = bool(all_locked) and all(
        prediction == all_locked[0] for prediction in all_locked[1:]
    )
    locked_targets = tuple(row["target_value"] for row in locked_rows)
    consensus_correct = consensus and all_locked[0] == locked_targets
    best_locked = max(
        (item["locked_correct"] for item in candidates), default=0
    )
    return {
        "support_recovered": set(inferred_support) == truth_relevant,
        "inferred_support": list(inferred_support),
        "truth_support": sorted(truth_relevant),
        "candidate_count": len(candidates),
        "operator_identified": len(candidate_ops) == 1,
        "operator_candidates": candidate_ops,
        "true_operator_in_candidates": truth_spec["operator"] in candidate_ops,
        "exact_rule_in_candidates": exact_candidate,
        "development_consensus": bool(candidates) and all(
            item["development_prediction"] == candidates[0]["development_prediction"]
            for item in candidates[1:]
        ),
        "locked_consensus": consensus,
        "locked_consensus_correct": bool(consensus_correct),
        "best_locked_accuracy": best_locked / len(locked_rows) if locked_rows else None,
        "locked_size": len(locked_rows),
    }


def run_discovery_baseline(
    *, family_count: int = 400, input_dim: int = 8,
    output_dim: int = 8, seed: int = 20261114,
) -> dict:
    corpus = generate_mixed_corpus(
        family_count=family_count, input_dim=input_dim,
        output_dim=output_dim, seed=seed,
    )
    teachers = {teacher["family_id"]: teacher for teacher in corpus["teachers"]}
    grouped = defaultdict(list)
    for row in corpus["rows"]:
        grouped[row["family_id"]].append(row)

    results = []
    family_metrics = defaultdict(list)
    for family_id, rows in grouped.items():
        teacher = teachers[family_id]
        by_split = defaultdict(list)
        for row in rows:
            by_split[row["state_split"]].append(row)
        for output_index, truth_spec in enumerate(teacher["rules"]):
            split_rows = {}
            for split in ("train", "development", "locked"):
                split_rows[split] = [
                    {
                        "state": row["state"],
                        "target_value": row["target"][output_index],
                    }
                    for row in by_split[split]
                ]
            result = _score_rule_group(
                split_rows["train"], split_rows["development"],
                split_rows["locked"], truth_spec, input_dim,
            )
            result.update({
                "family_id": family_id,
                "family_split": rows[0]["family_split"],
                "output_index": output_index,
                "truth_operator": truth_spec["operator"],
            })
            results.append(result)
            family_metrics[rows[0]["family_split"]].append(result)

    def summarize(items: list[dict]) -> dict:
        count = len(items)
        if not count:
            return {"rule_count": 0}
        return {
            "rule_count": count,
            "support_recovery_rate": sum(x["support_recovered"] for x in items) / count,
            "operator_candidate_coverage": sum(x["true_operator_in_candidates"] for x in items) / count,
            "exact_rule_candidate_coverage": sum(x["exact_rule_in_candidates"] for x in items) / count,
            "single_operator_identification_rate": sum(x["operator_identified"] for x in items) / count,
            "locked_consensus_rate": sum(x["locked_consensus"] for x in items) / count,
            "locked_consensus_accuracy_rate": sum(x["locked_consensus_correct"] for x in items) / count,
            "mean_best_locked_accuracy": sum(x["best_locked_accuracy"] for x in items) / count,
            "mean_candidate_count": sum(x["candidate_count"] for x in items) / count,
            "zero_candidate_rate": sum(x["candidate_count"] == 0 for x in items) / count,
        }

    return {
        "benchmark": "zhouyi-cpg-ei-observation-discovery-baseline-v1",
        "method": "pairwise observed influence + exact candidate filtering",
        "inference_uses_teacher_manifest": False,
        "family_count": family_count,
        "input_dim": input_dim,
        "output_dim": output_dim,
        "rule_count": len(results),
        "overall": summarize(results),
        "by_family_split": {
            split: summarize(items) for split, items in sorted(family_metrics.items())
        },
        "by_operator": {
            operator: summarize([x for x in results if x["truth_operator"] == operator])
            for operator in OPERATORS
        },
        "limitations": [
            "Synthetic Boolean operators only; not a neural learner.",
            "Pairwise influence recovery can miss variables under finite observation.",
            "Candidate enumeration is restricted to the inferred support.",
            "Teacher manifests are used only for post-inference scoring.",
            "No claim of natural-language, Yi-Xue, causal, or real-world reasoning.",
        ],
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=400)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_discovery_baseline(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    summary = {key: value for key, value in report.items() if key != "results"}
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
