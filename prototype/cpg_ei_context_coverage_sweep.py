"""Controlled sampling sweep for conditional-relation support identifiability.

This benchmark isolates the effect of counterfactual context coverage on the
pairwise observed-influence support proposer. It is a synthetic diagnostic,
not a learned model or an open-world reasoning result.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path

from prototype.cpg_ei_observation_discovery import (
    _infer_support,
    _support_identifiability_audit,
)


def _rows(input_dim: int = 4) -> list[dict]:
    result = []
    for state in itertools.product((0, 1), repeat=input_dim):
        x0, x1, _x2, context = state
        target = (x0 ^ x1) if context == 1 else 0
        result.append({"state": list(state), "target_value": target})
    return result


def run_context_coverage_sweep(
    *, seeds: tuple[int, ...] = (11, 23, 47, 89, 131),
    sample_fractions: tuple[float, ...] = (0.125, 0.25, 0.5, 0.75, 1.0),
) -> dict:
    full_rows = _rows()
    truth_support = (0, 1, 3)
    buckets: dict[str, list[dict]] = defaultdict(list)

    for fraction in sample_fractions:
        if not 0 < fraction <= 1:
            raise ValueError("sample fractions must be in (0, 1]")
        sample_size = max(1, round(len(full_rows) * fraction))
        for seed in seeds:
            ordered = list(full_rows)
            random.Random(seed).shuffle(ordered)
            sample = ordered[:sample_size]
            audit = _support_identifiability_audit(sample, 4)
            inferred = set(_infer_support(sample, 4))
            expected = set(truth_support)
            precision = len(inferred & expected) / len(inferred) if inferred else 1.0
            recall = len(inferred & expected) / len(expected)
            mean_coverage = sum(
                item["context_coverage"] for item in audit["variables"]
            ) / 4
            buckets[str(fraction)].append({
                "seed": seed,
                "sample_size": sample_size,
                "support_precision": precision,
                "support_recall": recall,
                "mean_context_coverage": mean_coverage,
                "unresolved_variable_count": len(audit["unresolved_variable_indices"]),
            })

    # Adversarial sample: every state has context == 0, so the conditional
    # relation is never activated. This is intentionally not random sampling.
    inactive = [row for row in full_rows if row["state"][3] == 0]
    inactive_audit = _support_identifiability_audit(inactive, 4)
    inactive_inferred = _infer_support(inactive, 4)

    summary = {}
    for fraction, observations in buckets.items():
        summary[fraction] = {
            "runs": len(observations),
            "mean_support_precision": sum(x["support_precision"] for x in observations) / len(observations),
            "mean_support_recall": sum(x["support_recall"] for x in observations) / len(observations),
            "mean_context_coverage": sum(x["mean_context_coverage"] for x in observations) / len(observations),
            "mean_unresolved_variable_count": sum(x["unresolved_variable_count"] for x in observations) / len(observations),
        }

    return {
        "benchmark": "zhouyi-cpg-ei-conditional-context-coverage-sweep-v1",
        "input_dim": 4,
        "truth_operator": "conditional_xor",
        "truth_support": list(truth_support),
        "sample_fractions": list(sample_fractions),
        "seeds": list(seeds),
        "by_sample_fraction": summary,
        "adversarial_inactive_context": {
            "sample_size": len(inactive),
            "observed_context_coverage_for_x0": inactive_audit["variables"][0]["context_coverage"],
            "inferred_support": list(inactive_inferred),
            "truth_support": list(truth_support),
            "support_recall": len(set(inactive_inferred) & set(truth_support)) / len(truth_support),
            "x0_status": inactive_audit["variables"][0]["status"],
            "x3_status": inactive_audit["variables"][3]["status"],
        },
        "claim_boundary": (
            "Synthetic finite Boolean sampling diagnostic only; no claim of "
            "learned relation discovery, causal inference, natural-language "
            "reasoning, Yi-Xue understanding, or real-world transfer."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_context_coverage_sweep()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
