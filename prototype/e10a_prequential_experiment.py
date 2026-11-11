"""Prequential experiment for E10-A's finite relational version-space DSL.

This is a same-process research harness. The learner API receives only Support,
Query, and one revealed label at a time; evaluator truth is retained by the
runner, not passed to the learner. This is data-flow discipline, not OS isolation.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task
from prototype.e10a_prequential_ledger import PrequentialLedger
from prototype.e10_shared_protocol_adapter import E10SharedProtocolAdapter
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


MODES = ("FROZEN", "BATCH_REFIT", "INCREMENTAL_FILTER")


def run(seed: int = 17, *, mode: str = "INCREMENTAL_FILTER",
        instances_per_template: int = 6) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    support, query, evaluator_truth = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    learner = FiniteRelationalVersionSpace().fit(support)
    truth_by_id = {
        row["observation_id"]: row["valid"]
        for row in evaluator_truth["query_truth"]
    }
    query_objects = query["objects"]
    query_object_map = {row["object_id"]: row for row in query_objects}

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
        version = 0
        prediction_rows = []

        for step, observation in enumerate(query["observations"], start=1):
            prediction = learner.predict(observation, query_objects)
            prediction_id = f"prediction-{step:05d}"
            adapter.commit_prediction(
                prediction_id=prediction_id,
                observation_id=observation["observation_id"],
                observation_payload={
                    "observation": observation,
                    "participant_objects": [
                        query_object_map[object_id]
                        for object_id in observation["participants"]
                    ],
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
                observation, label, query_objects, mode=mode
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
                "target": label,
                "correct_when_covered": (
                    prediction["prediction"] is label
                    if prediction["decision_status"] == "PREDICT" else None
                ),
                "candidate_count": prediction["compute_cost"]["candidate_count"],
                "version_space_after": update["after_candidate_count"],
            })

        total = len(prediction_rows)
        result = {
            "task": "E10-A finite relational version-space prequential experiment",
            "seed": seed,
            "mode": mode,
            "generator": "e10a-object-disjoint-task-v1",
            "learner_dsl": "one categorical feature + unordered distinct role-value set + one context equality",
            "support_observations": len(support["observations"]),
            "query_observations": total,
            "coverage": covered / total if total else 0.0,
            "selective_accuracy": correct / covered if covered else None,
            "strict_accuracy_abstentions_count_wrong": correct / total if total else 0.0,
            "abstention_rate": abstentions / total if total else 0.0,
            "revision_count_with_version_space_change": revisions,
            "candidate_update_operations": update_operations,
            "final_version_space_counts": {
                key: len(value)
                for key, value in learner.snapshot()["version_spaces"].items()
            },
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
    return result


def run_all(seed: int = 17, *, instances_per_template: int = 6) -> dict[str, Any]:
    results = [
        run(seed, mode=mode, instances_per_template=instances_per_template)
        for mode in MODES
    ]
    return {
        "experiment": "E10-A object-disjoint prequential finite-DSL comparison",
        "seed": seed,
        "arms": results,
        "comparisons": {
            "incremental_equals_batch_final_version_space": (
                results[1]["final_version_space_counts"]
                == results[2]["final_version_space_counts"]
            ),
            "frozen_candidate_update_operations": results[0]["candidate_update_operations"],
            "batch_candidate_update_operations": results[1]["candidate_update_operations"],
            "incremental_candidate_update_operations": results[2]["candidate_update_operations"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--instances-per-template", type=int, default=6)
    parser.add_argument("--mode", choices=(*MODES, "all"), default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = (
        run_all(args.seed, instances_per_template=args.instances_per_template)
        if args.mode == "all"
        else run(args.seed, mode=args.mode, instances_per_template=args.instances_per_template)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)


if __name__ == "__main__":
    main()
