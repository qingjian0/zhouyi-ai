"""E10-B.3 identifiability boundary for zero-shot opaque relation symbols.

Construct two evaluator worlds with identical learner-visible Support/Query
payloads but opposite labels on an unseen relation. This demonstrates that
zero-shot transfer for an opaque symbol is unidentifiable without additional
public structure; a sound learner must abstain or receive more information.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run(seed: int = 2701, *, instances_per_template: int = 4) -> dict[str, Any]:
    support, query, evaluator = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    relations = sorted({row["relation_symbol"] for row in support["observations"]})
    if len(relations) < 2:
        raise ValueError("identifiability audit requires at least two relation symbols")
    seen_relation, heldout_relation = relations[:2]

    seen_rows = [
        row for row in support["observations"]
        if row["relation_symbol"] == seen_relation
    ]
    seen_object_ids = {
        object_id for row in seen_rows for object_id in row["participants"]
    }
    seen_objects = [
        row for row in support["objects"]
        if row["object_id"] in seen_object_ids
    ]
    learner_support = {
        "schema_version": support["schema_version"],
        "phase": "support",
        "objects": seen_objects,
        "observations": seen_rows,
    }

    heldout_rows = [
        row for row in query["observations"]
        if row["relation_symbol"] == heldout_relation
    ]
    heldout_object_ids = {
        object_id for row in heldout_rows for object_id in row["participants"]
    }
    heldout_objects = [
        row for row in query["objects"]
        if row["object_id"] in heldout_object_ids
    ]
    learner_query = {
        "observations": heldout_rows,
        "objects": heldout_objects,
    }

    # The evaluator's second possible world changes only hidden labels.
    # Every byte visible to the learner remains exactly the same.
    visible_payload = {
        "support": learner_support,
        "query": learner_query,
    }
    world_a_hash = _canonical_hash(visible_payload)
    world_b_hash = _canonical_hash(visible_payload)

    truth_a = {
        row["observation_id"]: row["valid"]
        for row in evaluator["query_truth"]
        if row["observation_id"] in {
            item["observation_id"] for item in heldout_rows
        }
    }
    truth_b = {key: not value for key, value in truth_a.items()}
    opposite_labels = all(truth_a[key] is not truth_b[key] for key in truth_a)

    learner = FiniteRelationalVersionSpace().fit(learner_support)
    object_map = {row["object_id"]: row for row in heldout_objects}
    predictions = [
        learner.predict(
            row, [object_map[object_id] for object_id in row["participants"]]
        )
        for row in heldout_rows
    ]
    statuses = {
        status: sum(row["decision_status"] == status for row in predictions)
        for status in sorted({row["decision_status"] for row in predictions})
    }
    abstained = all(row["prediction"] is None for row in predictions)
    n = len(predictions)
    return {
        "experiment": "E10-B.3 opaque relation zero-shot identifiability boundary",
        "seed": seed,
        "seen_relation_symbol": seen_relation,
        "heldout_relation_symbol": heldout_relation,
        "support_observations_for_seen_relation": len(seen_rows),
        "heldout_query_observations": n,
        "learner_visible_payload_hash_world_a": world_a_hash,
        "learner_visible_payload_hash_world_b": world_b_hash,
        "visible_payloads_identical": world_a_hash == world_b_hash,
        "hidden_labels_opposite_between_worlds": opposite_labels,
        "current_learner_decision_counts": statuses,
        "current_learner_abstains_all": abstained,
        "forced_binary_predictor_mean_accuracy_upper_bound": 0.5,
        "abstaining_predictor_coverage": 0.0,
        "checks": {
            "same_visible_input": world_a_hash == world_b_hash,
            "opposite_hidden_labels": opposite_labels,
            "unseen_relation_rejected": abstained and statuses == {
                "ABSTAIN_OOD_RELATION": n
            },
        },
        "interpretation": [
            "No deterministic predictor can distinguish the two evaluator worlds from identical learner-visible input.",
            "A forced binary prediction has mean accuracy 50% across the two equally weighted worlds.",
            "Abstention avoids unsupported claims but has zero coverage on the held-out relation.",
            "Transfer requires additional observable relation descriptors, shared examples, or an explicit prior over relation families.",
        ],
        "limitations": [
            "This is an identifiability boundary demonstration on the synthetic E10 task.",
            "The 50% bound is for the paired indistinguishable-world construction, not a universal benchmark score.",
            "It does not test transfer once public relation descriptors are supplied.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
