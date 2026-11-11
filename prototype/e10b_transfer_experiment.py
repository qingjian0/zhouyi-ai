"""E10-B transfer and abstention audit over the E10-A object-disjoint task.

This first gate measures invariance to consistent renaming and fail-closed
behavior under query-only schema/value/context shift. It is not open-world
concept discovery and makes no claim about general semantic analogy.
"""
from __future__ import annotations

import hashlib
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task


def _score(rows: list[dict[str, Any]], truth: dict[str, bool]) -> dict[str, Any]:
    covered = [row for row in rows if row["prediction"] is not None]
    correct = sum(row["prediction"] is truth[row["observation_id"]] for row in covered)
    total = len(rows)
    return {
        "n": total,
        "coverage": len(covered) / total if total else 0.0,
        "selective_accuracy": correct / len(covered) if covered else None,
        "strict_accuracy": correct / total if total else 0.0,
        "abstention_rate": 1 - len(covered) / total if total else 0.0,
        "decision_counts": {
            status: sum(row["decision_status"] == status for row in rows)
            for status in sorted({row["decision_status"] for row in rows})
        },
    }


def _predict(learner: FiniteRelationalVersionSpace,
             observations: list[dict[str, Any]],
             object_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects = {row["object_id"]: row for row in object_rows}
    return [
        learner.predict(
            row, [objects[object_id] for object_id in row["participants"]]
        )
        for row in observations
    ]


def _rename_payloads(support: dict[str, Any], query: dict[str, Any]):
    support = {
        key: [dict(row) for row in value] if isinstance(value, list) else value
        for key, value in support.items()
    }
    query = {
        key: [dict(row) for row in value] if isinstance(value, list) else value
        for key, value in query.items()
    }
    feature_keys = sorted({
        key for obj in support["objects"] for key, _ in obj["attributes"]
    })
    context_keys = sorted({
        key for row in support["observations"] for key, _ in row["context"]
    })
    feature_map = {key: f"renamed_feature_{i}" for i, key in enumerate(feature_keys)}
    context_map = {key: f"renamed_context_{i}" for i, key in enumerate(context_keys)}
    for payload in (support, query):
        for obj in payload["objects"]:
            obj["attributes"] = [[feature_map[key], value]
                                 for key, value in obj["attributes"]]
        for row in payload["observations"]:
            if "context" in row:
                row["context"] = [[context_map[key], value]
                                  for key, value in row["context"]]
    return support, query


def run(seed: int = 1701, *, instances_per_template: int = 4) -> dict[str, Any]:
    support, query, truth_payload = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    truth = {row["observation_id"]: row["valid"]
             for row in truth_payload["query_truth"]}
    learner_support = {
        key: support[key] for key in ("schema_version", "phase", "objects", "observations")
    }
    learner = FiniteRelationalVersionSpace().fit(learner_support)
    native_rows = _predict(learner, query["observations"], query["objects"])

    renamed_support, renamed_query = _rename_payloads(
        learner_support, query
    )
    renamed_learner = FiniteRelationalVersionSpace().fit(renamed_support)
    renamed_rows = _predict(
        renamed_learner, renamed_query["observations"], renamed_query["objects"]
    )
    native_by_id = {row["observation_id"]: row for row in native_rows}
    renamed_by_id = {row["observation_id"]: row for row in renamed_rows}
    renaming_agreement = all(
        native_by_id[key]["decision_status"] == renamed_by_id[key]["decision_status"]
        and native_by_id[key]["prediction"] == renamed_by_id[key]["prediction"]
        for key in native_by_id
    )

    schema_objects = []
    for obj in query["objects"]:
        schema_objects.append({
            **obj,
            "attributes": [[f"unseen_{key}", value] for key, value in obj["attributes"]],
        })
    schema_rows = _predict(learner, query["observations"], schema_objects)

    value_objects = []
    for obj in query["objects"]:
        value_objects.append({
            **obj,
            "attributes": [[key, f"heldout-category-{seed}"]
                           for key, _ in obj["attributes"]],
        })
    value_rows = _predict(learner, query["observations"], value_objects)

    context_observations = []
    for row in query["observations"]:
        context_observations.append({
            **row,
            "context": [[key, f"heldout-context-{seed}"]
                        for key, _ in row["context"]],
        })
    context_rows = _predict(learner, context_observations, query["objects"])

    majority = sum(row["outcome"] for row in support["observations"])
    majority_total = len(support["observations"])
    majority_prediction = majority * 2 >= majority_total
    majority_rows = [
        {"observation_id": row["observation_id"],
         "decision_status": "PREDICT",
         "prediction": majority_prediction}
        for row in query["observations"]
    ]
    random_rows = [
        {
            "observation_id": row["observation_id"],
            "decision_status": "PREDICT",
            "prediction": bool(hashlib.sha256(
                f"{seed}:{row['observation_id']}".encode()
            ).digest()[0] & 1),
        }
        for row in query["observations"]
    ]
    oracle_rows = [
        {"observation_id": row["observation_id"],
         "decision_status": "PREDICT",
         "prediction": truth[row["observation_id"]]}
        for row in query["observations"]
    ]
    return {
        "experiment": "E10-B renamed-schema and OOD abstention audit",
        "seed": seed,
        "instances_per_template": instances_per_template,
        "native": _score(native_rows, truth),
        "consistent_renaming": {
            "metrics": _score(renamed_rows, truth),
            "prediction_invariance": renaming_agreement,
        },
        "query_only_shift": {
            "renamed_attribute_schema": _score(schema_rows, truth),
            "unseen_categorical_values": _score(value_rows, truth),
            "unseen_context_values": _score(context_rows, truth),
        },
        "baselines": {
            "support_majority": _score(majority_rows, truth),
            "deterministic_random": _score(random_rows, truth),
            "evaluator_oracle_upper_bound": _score(oracle_rows, truth),
        },
        "expectations": {
            "consistent_renaming_invariant": True,
            "query_only_schema_shift_abstains_all": True,
            "query_only_value_shift_abstains_all": True,
            "query_only_context_shift_abstains_all": True,
        },
        "checks": {
            "consistent_renaming_invariant": renaming_agreement,
            "schema_shift_all_abstain": all(r["prediction"] is None for r in schema_rows),
            "value_shift_all_abstain": all(r["prediction"] is None for r in value_rows),
            "context_shift_all_abstain": all(r["prediction"] is None for r in context_rows),
        },
        "limitations": [
            "Consistent renaming tests symbol invariance, not semantic analogy.",
            "Query-only unseen values are deliberately treated as OOD and abstained on; no extrapolation is claimed.",
            "The finite DSL and generator remain synthetic and matched.",
            "No learned representation, neural baseline, or open-world operator induction is evaluated.",
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
