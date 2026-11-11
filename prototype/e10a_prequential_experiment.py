"""Prequential experiment for E10-A's finite relational version-space DSL.

This is a same-process research harness. The learner API receives only Support,
Query, and one revealed label at a time; evaluator truth is retained by the
runner, not passed to the learner. This is data-flow discipline, not OS isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
from pathlib import Path
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_subprocess_learner import SubprocessRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_prequential_ledger import PrequentialLedger
from prototype.e10_shared_protocol_adapter import E10SharedProtocolAdapter
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


MODES = ("FROZEN", "BATCH_REFIT", "INCREMENTAL_FILTER")


def run(seed: int = 17, *, mode: str = "INCREMENTAL_FILTER",
        instances_per_template: int = 6,
        learner_backend: str = "in_process") -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if learner_backend not in {"in_process", "subprocess"}:
        raise ValueError("learner_backend must be in_process or subprocess")
    support, query, evaluator_truth = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    learner = (
        SubprocessRelationalVersionSpace() if learner_backend == "subprocess"
        else FiniteRelationalVersionSpace()
    ).fit(support)
    truth_by_id = {
        row["observation_id"]: row["valid"]
        for row in evaluator_truth["query_truth"]
    }
    query_object_map = {row["object_id"]: row for row in query["objects"]}

    episode_id = f"e10a-{seed}-{mode.lower()}"
    ledger = PrequentialLedger(episode_id=episode_id)
    with tempfile.TemporaryDirectory() as temp_dir:
        store = SQLiteEvidenceStore(Path(temp_dir) / "events.sqlite3")
        adapter = E10SharedProtocolAdapter(
            ledger, store, episode_id=episode_id,
            initial_version_id="e10-v0",
            initial_structure=learner.snapshot(),
        )
        covered = 0
        correct = 0
        abstentions = 0
        revisions = 0
        update_operations = 0
        prediction_rule_match_operations = 0
        version = 0
        prediction_rows = []

        for step, observation in enumerate(query["observations"], start=1):
            # Reveal only the current observation's participants, never the
            # complete future Query object pool.
            current_objects = [
                query_object_map[object_id]
                for object_id in observation["participants"]
            ]
            prediction = learner.predict(observation, current_objects)
            prediction_rule_match_operations += prediction["compute_cost"]["rule_match_evaluations"]
            prediction_id = f"prediction-{step:05d}"
            adapter.commit_prediction(
                prediction_id=prediction_id,
                observation_id=observation["observation_id"],
                observation_payload={
                    "observation": observation,
                    "participant_objects": current_objects,
                },
                model_version=f"e10a-{mode.lower()}-v{version}",
                candidate_set_hash=prediction["candidate_set_hash"],
                decision_status=prediction["decision_status"],
                prediction=prediction["prediction"],
                confidence=prediction["confidence"],
                compute_cost=prediction["compute_cost"],
            )

            # Evaluator truth is looked up only after the durable prediction commit.
            label = truth_by_id[observation["observation_id"]]
            reveal_id = f"reveal-{step:05d}"
            adapter.reveal_evidence(
                reveal_id=reveal_id,
                prediction_id=prediction_id,
                target=label,
                reveal_source="object-disjoint-evaluator",
            )

            if prediction["decision_status"] == "PREDICT":
                covered += 1
                correct += int(prediction["prediction"] is label)
            else:
                abstentions += 1

            before_version = f"e10-v{version}"
            update = learner.update(
                observation, label, current_objects, mode=mode
            )
            update_operations += update["candidate_operations"]
            if update["changed"]:
                revisions += 1
            version += 1
            after_version = f"e10-v{version}"
            adapter.append_revision(
                revision_id=f"revision-{step:05d}",
                operation=update["operation"],
                evidence_ids=[reveal_id],
                before_version_ids=[before_version],
                after_version_id=after_version,
                after_structure=learner.snapshot(),
                rationale_code="prequential-query-evidence",
                actual_compute={
                    "candidate_operations": update["candidate_operations"],
                    "candidate_count_before": update["before_candidate_count"],
                    "candidate_count_after": update["after_candidate_count"],
                },
            )
            prediction_rows.append({
                "observation_id": observation["observation_id"],
                "decision_status": prediction["decision_status"],
                "prediction": prediction["prediction"],
                "agreement_score": prediction["agreement_score"],
                "target": label,
                "correct_when_covered": (
                    prediction["prediction"] is label
                    if prediction["decision_status"] == "PREDICT" else None
                ),
                "candidate_count": prediction["compute_cost"]["candidate_count"],
                "version_space_after": update["after_candidate_count"],
            })

        total = len(prediction_rows)
        final_snapshot = learner.snapshot()
        final_spaces = final_snapshot["version_spaces"]
        final_space_hashes = {
            relation: hashlib.sha256(json.dumps(rules, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
            for relation, rules in sorted(final_spaces.items())
        }
        result = {
            "task": "E10-A finite relational version-space prequential experiment",
            "seed": seed,
            "mode": mode,
            "learner_backend": learner_backend,
            "generator": "e10a-object-disjoint-task-v1",
            "learner_dsl": "one categorical feature + unordered distinct role-value set + one context equality",
            "support_observations": len(support["observations"]),
            "query_observations": total,
            "coverage": covered / total if total else 0.0,
            "selective_accuracy": correct / covered if covered else None,
            "strict_accuracy_abstentions_count_wrong": correct / total if total else 0.0,
            "abstention_rate": abstentions / total if total else 0.0,
            "revision_count_with_version_space_change": revisions,
            "candidate_generation_evaluations": final_snapshot["report"]["candidate_generation_evaluations"],
            "prediction_rule_match_operations": prediction_rule_match_operations,
            "candidate_update_operations": update_operations,
            "final_version_space_counts": {
                key: len(value) for key, value in final_spaces.items()
            },
            "final_version_space_hashes": final_space_hashes,
            "persisted_event_count": len(adapter.replay()),
            "prediction_trace": prediction_rows,
            "limitations": [
                "The hypothesis language is deliberately matched to the finite synthetic generator family.",
                "Role order is not identifiable because participant order is shuffled; the learner predicts an unordered role-value set.",
                "BATCH_REFIT and INCREMENTAL_FILTER should converge to the same exact version space; their comparison is about update work, not predictive quality.",
                "The harness is same-process and does not establish evaluator/learner security isolation.",
                "This is not open-world concept discovery or general relation-operator invention.",
            ],
        }
        store.close()
        if learner_backend == "subprocess":
            learner.close()
    return result


def run_all(seed: int = 17, *, instances_per_template: int = 6,
            learner_backend: str = "in_process") -> dict[str, Any]:
    results = [
        run(seed, mode=mode, instances_per_template=instances_per_template,
            learner_backend=learner_backend)
        for mode in MODES
    ]
    return {
        "experiment": "E10-A object-disjoint prequential finite-DSL comparison",
        "seed": seed,
        "arms": results,
        "comparisons": {
            "incremental_equals_batch_final_version_space": (
                results[1]["final_version_space_hashes"]
                == results[2]["final_version_space_hashes"]
            ),
            "frozen_candidate_update_operations": results[0]["candidate_update_operations"],
            "batch_candidate_update_operations": results[1]["candidate_update_operations"],
            "incremental_candidate_update_operations": results[2]["candidate_update_operations"],
        },
    }


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "population_stddev": None,
                "min": None, "max": None}
    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "population_stddev": statistics.pstdev(clean),
        "min": min(clean),
        "max": max(clean),
    }


def run_sweep(start_seed: int = 17, *, seeds: int = 10,
              instances_per_template: int = 6) -> dict[str, Any]:
    """Run all update arms across consecutive seeds and summarize distributions."""
    if not isinstance(seeds, int) or isinstance(seeds, bool) or seeds < 1:
        raise ValueError("seeds must be a positive integer")
    seed_results = [
        run_all(start_seed + offset, instances_per_template=instances_per_template)
        for offset in range(seeds)
    ]
    metrics = (
        "coverage", "selective_accuracy",
        "strict_accuracy_abstentions_count_wrong", "abstention_rate",
        "revision_count_with_version_space_change",
        "candidate_generation_evaluations",
        "prediction_rule_match_operations", "candidate_update_operations",
    )
    arm_summaries = {}
    for mode in MODES:
        arm_rows = [
            next(arm for arm in item["arms"] if arm["mode"] == mode)
            for item in seed_results
        ]
        arm_summaries[mode] = {
            metric: _distribution([row[metric] for row in arm_rows])
            for metric in metrics
        }
        arm_summaries[mode]["final_version_space_counts"] = [
            row["final_version_space_counts"] for row in arm_rows
        ]
        arm_summaries[mode]["final_version_space_hashes"] = [
            row["final_version_space_hashes"] for row in arm_rows
        ]

    per_seed_checks = [
        {
            "seed": item["seed"],
            "batch_equals_incremental_exact_version_space": (
                item["arms"][1]["final_version_space_hashes"]
                == item["arms"][2]["final_version_space_hashes"]
            ),
            "batch_update_operations": item["comparisons"]["batch_candidate_update_operations"],
            "incremental_update_operations": item["comparisons"]["incremental_candidate_update_operations"],
        }
        for item in seed_results
    ]
    batch_total = sum(
        item["comparisons"]["batch_candidate_update_operations"] for item in seed_results
    )
    incremental_total = sum(
        item["comparisons"]["incremental_candidate_update_operations"] for item in seed_results
    )
    return {
        "experiment": "E10-A multi-seed object-disjoint prequential finite-DSL sweep",
        "start_seed": start_seed,
        "seeds": seeds,
        "instances_per_template": instances_per_template,
        "arms": arm_summaries,
        "comparisons": {
            "batch_equals_incremental_exact_version_space_all_seeds": all(
                row["batch_equals_incremental_exact_version_space"]
                for row in per_seed_checks
            ),
            "per_seed": per_seed_checks,
            "aggregate_incremental_to_batch_update_operation_ratio": (
                incremental_total / batch_total if batch_total else None
            ),
            "aggregate_batch_update_operations": batch_total,
            "aggregate_incremental_update_operations": incremental_total,
            "interpretation": (
                "Exact-space equality is an invariant check. Operation ratios compare "
                "measured candidate/example checks; they do not imply accuracy superiority."
            ),
        },
        "seed_results": seed_results,
        "limitations": [
            "Seeds are consecutive deterministic generator seeds, not a proof of population-level performance.",
            "The finite DSL remains matched to the synthetic generator family.",
            "No neural or program-synthesis baseline is included in this sweep.",
            "The runner remains same-process; this is not evaluator/learner security isolation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--instances-per-template", type=int, default=6)
    parser.add_argument("--mode", choices=(*MODES, "all"), default="all")
    parser.add_argument("--learner-backend", choices=("in_process", "subprocess"), default="in_process")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--start-seed", type=int, default=17)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.sweep:
        result = run_sweep(args.start_seed, seeds=args.seeds,
                           instances_per_template=args.instances_per_template)
    elif args.mode == "all":
        result = run_all(args.seed, instances_per_template=args.instances_per_template,
                         learner_backend=args.learner_backend)
    else:
        result = run(args.seed, mode=args.mode,
                     instances_per_template=args.instances_per_template,
                     learner_backend=args.learner_backend)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)


if __name__ == "__main__":
    main()
