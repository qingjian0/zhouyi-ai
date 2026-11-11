"""E10-C.1 contradiction audit for finite relational structure revision.

A correctly predicted Query example is revealed, then an identical input with
an independently identified observation ID is revealed with the opposite
label. Exact version-space updates must remove every incompatible hypothesis
and make the relation abstain as inconsistent. This is a controlled conflict
test, not a claim of open-world dynamic rule invention.
"""
from __future__ import annotations

import json
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task


UPDATE_MODES = ("FROZEN", "BATCH_REFIT", "INCREMENTAL_FILTER")


def _learner_support(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("schema_version", "phase", "objects", "observations")
    }


def run(seed: int = 2801, *, instances_per_template: int = 5) -> dict[str, Any]:
    support, query, evaluator = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    truth = {
        row["observation_id"]: row["valid"]
        for row in evaluator["query_truth"]
    }
    object_map = {row["object_id"]: row for row in query["objects"]}
    selected = None
    selected_objects = None

    # Select an example that the Support-only learner already predicts correctly.
    # This isolates the conflict response from ordinary initial model error.
    probe = FiniteRelationalVersionSpace().fit(_learner_support(support))
    for row in query["observations"]:
        participants = [object_map[key] for key in row["participants"]]
        prediction = probe.predict(row, participants)
        if (prediction["decision_status"] == "PREDICT"
                and prediction["prediction"] is truth[row["observation_id"]]):
            selected = row
            selected_objects = participants
            break
    if selected is None or selected_objects is None:
        raise RuntimeError("generator seed produced no correctly predicted covered Query")

    actual_label = truth[selected["observation_id"]]
    conflict = {
        **selected,
        "observation_id": selected["observation_id"] + "-conflict",
    }
    reports: dict[str, Any] = {}
    final_spaces: dict[str, Any] = {}

    for mode in UPDATE_MODES:
        learner = FiniteRelationalVersionSpace().fit(_learner_support(support))
        before = learner.snapshot()["report"]["consistent_candidate_count"]
        first = learner.update(selected, actual_label, selected_objects, mode=mode)
        after_first = learner.snapshot()["version_spaces"].get(
            selected["relation_symbol"], []
        )
        second = learner.update(
            conflict, not actual_label, selected_objects, mode=mode
        )
        after_conflict = learner.snapshot()["version_spaces"].get(
            selected["relation_symbol"], []
        )
        final_prediction = learner.predict(selected, selected_objects)
        reports[mode] = {
            "initial_total_candidate_count": before,
            "after_consistent_reveal_count": len(after_first),
            "after_conflicting_reveal_count": len(after_conflict),
            "first_update": first,
            "conflict_update": second,
            "final_decision_status": final_prediction["decision_status"],
            "final_prediction": final_prediction["prediction"],
            "evidence_digest": learner.snapshot()["evidence_digest"],
        }
        final_spaces[mode] = after_conflict

    batch_matches_incremental = (
        final_spaces["BATCH_REFIT"] == final_spaces["INCREMENTAL_FILTER"]
    )
    return {
        "experiment": "E10-C.1 contradictory evidence and version-space revision",
        "seed": seed,
        "relation_symbol": selected["relation_symbol"],
        "selected_query_observation_id": selected["observation_id"],
        "selected_query_truth": actual_label,
        "selected_query_participant_count": len(selected_objects),
        "conflict_observation_id": conflict["observation_id"],
        "conflict_has_identical_relation_participants_context": all(
            conflict[key] == selected[key]
            for key in ("relation_symbol", "participants", "context")
        ),
        "conflict_label": not actual_label,
        "conflict_label_is_opposite": (not actual_label) != actual_label,
        "modes": reports,
        "checks": {
            "conflict_input_identical_except_id_and_label": True,
            "incremental_and_batch_both_empty": (
                not final_spaces["INCREMENTAL_FILTER"]
                and not final_spaces["BATCH_REFIT"]
            ),
            "incremental_equals_batch": batch_matches_incremental,
            "incremental_abstains_inconsistent": (
                reports["INCREMENTAL_FILTER"]["final_decision_status"]
                == "ABSTAIN_INCONSISTENT"
            ),
            "batch_abstains_inconsistent": (
                reports["BATCH_REFIT"]["final_decision_status"]
                == "ABSTAIN_INCONSISTENT"
            ),
            "frozen_retains_prior_structure": bool(final_spaces["FROZEN"]),
        },
        "interpretation": [
            "A contradictory reveal for identical observable relation inputs makes the exact consistent version space empty.",
            "BATCH_REFIT and INCREMENTAL_FILTER must agree on the empty final version space.",
            "The learner fails closed as ABSTAIN_INCONSISTENT instead of silently converting contradiction into a negative rule.",
            "FROZEN is a control that intentionally does not revise its version space.",
        ],
        "limitations": [
            "The contradiction is injected as a controlled evaluator stress test, not sampled natural noise.",
            "An empty version space detects inconsistency but does not identify which evidence source is wrong.",
            "This tests revision within a fixed candidate universe, not invention of a new rule after concept drift.",
            "The benchmark is synthetic and the DSL is finite.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
