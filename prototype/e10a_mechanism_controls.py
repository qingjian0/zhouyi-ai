"""Controlled frozen/online/batch-refit comparison for E10-A."""
from __future__ import annotations
import copy
from typing import Any
from prototype.e10a_mechanism_learner import E10AMechanismLearner


def _score(records: list[dict[str, Any]], revisions: int, refits: int) -> dict[str, Any]:
    total = len(records)
    decided = [x for x in records if x["decision_status"] == "PREDICT"]
    correct = sum(x["prediction"] == x["target"] for x in decided)
    return {
        "observations": total, "decided": len(decided),
        "abstentions": total - len(decided),
        "coverage": len(decided) / total if total else 0.0,
        "accuracy_on_decided": correct / len(decided) if decided else None,
        "accuracy_all_abstain_wrong": correct / total if total else None,
        "revision_events": revisions, "batch_refits": refits,
        "candidate_counts": [x["candidate_count"] for x in records],
        "candidate_hashes": [x["candidate_set_hash"] for x in records],
    }


def run_mechanism_controls(support: dict[str, Any], query: dict[str, Any],
                           evaluator_truth: dict[str, Any]) -> dict[str, Any]:
    """Run identical ordered Query rows; reveal targets only after predictions."""
    truth = {x["observation_id"]: x["valid"] for x in evaluator_truth["query_truth"]}
    rows = query["observations"]
    if set(truth) != {x["observation_id"] for x in rows}:
        raise ValueError("Query/evaluator observation IDs must match")

    frozen = E10AMechanismLearner(copy.deepcopy(support))
    online = E10AMechanismLearner(copy.deepcopy(support))
    frozen.add_query_objects(copy.deepcopy(query["objects"]))
    online.add_query_objects(copy.deepcopy(query["objects"]))
    batch_objects = copy.deepcopy(support["objects"]) + copy.deepcopy(query["objects"])
    batch = E10AMechanismLearner(copy.deepcopy(support))
    batch.add_query_objects(copy.deepcopy(query["objects"]))

    records = {"frozen": [], "online": [], "batch_refit": []}
    online_revisions = batch_refits = 0
    revealed_rows: list[dict[str, Any]] = []

    for row in rows:
        # All arms predict before the harness reads the evaluator target.
        predictions = {
            "frozen": frozen.predict(row),
            "online": online.predict(row),
            "batch_refit": batch.predict(row),
        }
        target = truth[row["observation_id"]]
        for arm, prediction in predictions.items():
            records[arm].append({**prediction, "target": target})

        online.revise(row, target)
        online_revisions += 1
        revealed_rows.append({
            "observation_id": row.get("observation_id"),
            "relation_symbol": row["relation_symbol"],
            "participants": list(row["participants"]),
            "context": [list(x) for x in row["context"]],
            "outcome": target,
        })
        refit_payload = {
            "phase": "support",
            "objects": batch_objects,
            "observations": copy.deepcopy(support["observations"]) + copy.deepcopy(revealed_rows),
        }
        batch = E10AMechanismLearner(refit_payload)
        batch_refits += 1

    return {
        "protocol": "same_query_order_predictions_before_reveal",
        "arms": {
            "frozen": _score(records["frozen"], 0, 0),
            "online_candidate_elimination": _score(records["online"], online_revisions, 0),
            "batch_refit": _score(records["batch_refit"], 0, batch_refits),
        },
        "interpretation_warning": (
            "The current A-O generator repeats the same finite mechanism and violation "
            "templates across Support and Query, changing object identities rather than "
            "the structural challenge. Equal scores do not show that revision is unnecessary."
        ),
    }
