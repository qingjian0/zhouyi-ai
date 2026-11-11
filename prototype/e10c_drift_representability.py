"""E10-C.2 representability audit for sequential concept drift.

The E10-A DSL encodes one role-value set and one context equality per relation
symbol. This experiment compares a stationary combined fit with explicitly
segmented epochs after a controlled mechanism change. Epoch segmentation is an
oracle-declared boundary here; the experiment does not claim autonomous drift
detection.
"""
from __future__ import annotations

import json
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace


SCHEMA = "e10a-object-disjoint-task-v1"
RELATION = "relation-opaque"
FEATURE = "attribute-opaque"
CONTEXT = "context-opaque"


def _epoch_payload(
    epoch: int, role_values: tuple[str, str], context_value: str
) -> dict[str, Any]:
    left_id = f"epoch-{epoch}-object-left"
    right_id = f"epoch-{epoch}-object-right"
    observation_id = f"epoch-{epoch}-positive"
    return {
        "schema_version": SCHEMA,
        "phase": "support",
        "objects": [
            {"object_id": left_id, "attributes": [[FEATURE, role_values[0]]]},
            {"object_id": right_id, "attributes": [[FEATURE, role_values[1]]]},
        ],
        "observations": [{
            "observation_id": observation_id,
            "relation_symbol": RELATION,
            "participants": [left_id, right_id],
            "context": [[CONTEXT, context_value]],
            "outcome": True,
        }],
    }


def _combine(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "phase": "support",
        "objects": [row for payload in payloads for row in payload["objects"]],
        "observations": [
            row for payload in payloads for row in payload["observations"]
        ],
    }


def _fit_count(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    learner = FiniteRelationalVersionSpace().fit(payload)
    snapshot = learner.snapshot()
    return len(snapshot["version_spaces"].get(RELATION, [])), snapshot


def run() -> dict[str, Any]:
    epoch_1 = _epoch_payload(1, ("A", "B"), "red")
    epoch_2 = _epoch_payload(2, ("C", "D"), "blue")
    stationary_repeat = _epoch_payload(3, ("A", "B"), "red")

    combined_drift_count, combined_snapshot = _fit_count(
        _combine([epoch_1, epoch_2])
    )
    epoch_1_count, epoch_1_snapshot = _fit_count(epoch_1)
    epoch_2_count, epoch_2_snapshot = _fit_count(epoch_2)
    stationary_count, stationary_snapshot = _fit_count(
        _combine([epoch_1, stationary_repeat])
    )

    return {
        "experiment": "E10-C.2 single-rule DSL concept-drift representability",
        "drift_world": {
            "epoch_1_rule_signature": {
                "role_values": ["A", "B"], "context": "red"
            },
            "epoch_2_rule_signature": {
                "role_values": ["C", "D"], "context": "blue"
            },
            "combined_stationary_version_space_size": combined_drift_count,
            "epoch_1_version_space_size": epoch_1_count,
            "epoch_2_version_space_size": epoch_2_count,
        },
        "no_drift_control": {
            "repeated_rule_signature": {
                "role_values": ["A", "B"], "context": "red"
            },
            "combined_version_space_size": stationary_count,
        },
        "checks": {
            "combined_drift_is_inconsistent": combined_drift_count == 0,
            "epoch_1_is_identifiable": epoch_1_count == 1,
            "epoch_2_is_identifiable": epoch_2_count == 1,
            "no_drift_control_remains_identifiable": stationary_count == 1,
        },
        "interpretation": [
            "A single-rule-per-relation DSL cannot represent two sequentially different role-value/context signatures when all epochs are forced into one stationary fit.",
            "Separating epochs allows each local mechanism to be represented by one exact candidate in this minimal controlled example.",
            "Epoch boundaries are supplied by the evaluator; autonomous change-point detection is not tested.",
            "Historical evidence is not deleted: epoch segmentation changes which evidence is active for a version, while the experiment retains both source payloads.",
        ],
        "limitations": [
            "This is a minimal representability proof, not a broad concept-drift benchmark.",
            "Each epoch has one positive example and only two observed role values, so exact identification is deliberately easy.",
            "No noisy labels, overlapping drift, gradual drift, or false drift alarms are tested.",
            "The experiment does not add epoch-aware behavior to the production learner.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
