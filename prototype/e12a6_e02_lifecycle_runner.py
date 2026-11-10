"""E12-A6 x E02-D finite-world lifecycle runner.

This connects the existing exact 27-rule symbolic benchmark to the lifecycle
ledger. It validates integration and abstention behavior, not open-world
discovery or neural learning.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from prototype.e02_rule_ood import RULES, Episode, consistent_rules, make_episodes, target_c
from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, Candidate, CandidateState, Evidence,
    LifecycleLedger, SplitRole,
)


def _candidate_id(index: int, rule: tuple[int, int, int]) -> str:
    return f"e02d:{index}:affine:{rule[0]}-{rule[1]}-{rule[2]}"


def run_episode(episode: Episode, index: int) -> dict[str, Any]:
    ledger = LifecycleLedger()
    support_ids = []
    for offset, (a, b, c) in enumerate(episode.support):
        eid = f"e02d:{index}:support:{offset}"
        support_ids.append(eid)
        ledger.add_evidence(Evidence(
            evidence_id=eid, episode_id=f"e02d-{index}",
            world_family="z3-affine-rule-family", split_role=SplitRole.TRAIN,
            observation_id=f"support-{offset}", outcome=f"{a},{b}->{c}",
            model_version="e02d-exact-symbolic-v1", measurement_cost=1.0,
            provenance="visible labeled support observation",
        ))

    hypotheses = consistent_rules(episode.support)
    if not hypotheses:
        raise AssertionError("generating rule must remain support-consistent")
    candidate_ids = {}
    for rule in hypotheses:
        cid = _candidate_id(index, rule)
        candidate_ids[rule] = cid
        ledger.add_candidate(Candidate(
            candidate_id=cid, version=1,
            canonical_expression=f"c=-({rule[0]}*a+{rule[1]}*b+{rule[2]}) mod 3",
            proposer_family="e02d_exact_hypothesis_enumerator",
            supporting_families=("finite-rule-enumerator",),
            input_types=("Z3", "Z3"), operator="AFFINE_MOD3",
            conditions=("a in Z3", "b in Z3"), uncertainty=1.0,
            complexity=4, proposal_cost=0.0,
            evidence_ids=tuple(support_ids),
        ))
        ledger.apply(Action(
            action_id=f"{cid}:propose", action_type=ActionType.PROPOSE,
            candidate_id=cid, candidate_version=1,
            from_state=CandidateState.OBSERVED, to_state=CandidateState.PROPOSED,
        ))
        ledger.apply(Action(
            action_id=f"{cid}:discriminate",
            action_type=ActionType.REQUEST_DISCRIMINATION,
            candidate_id=cid, candidate_version=1,
            from_state=CandidateState.PROPOSED,
            to_state=CandidateState.DISCRIMINATION_PENDING,
        ))
        ledger.apply(Action(
            action_id=f"{cid}:train-support", action_type=ActionType.TRAIN_SUPPORT,
            candidate_id=cid, candidate_version=1, evidence_ids=tuple(support_ids),
            from_state=CandidateState.DISCRIMINATION_PENDING,
            to_state=CandidateState.TRAIN_SUPPORTED,
        ))

    a, b = episode.query
    query_predictions = {target_c(rule, a, b) for rule in hypotheses}
    prediction_identifiable = len(query_predictions) == 1
    prediction = next(iter(query_predictions)) if prediction_identifiable else None
    mechanism_identifiable = len(hypotheses) == 1
    gold = target_c(episode.rule, a, b)

    # Commit the query prediction at step 7; reveal the held-out label at step 8.
    query_eid = f"e02d:{index}:gate-final"
    ledger.add_evidence(Evidence(
        evidence_id=query_eid, episode_id=f"e02d-{index}",
        world_family="z3-affine-rule-family", split_role=SplitRole.GATE_FINAL,
        observation_id=f"query-{a}-{b}", outcome=str(gold),
        model_version="e02d-exact-symbolic-v1", measurement_cost=1.0,
        prediction_commit_step=7, label_visibility_step=8,
        provenance="held-out label revealed after prediction commit",
    ))

    accepted = None
    if mechanism_identifiable:
        accepted = candidate_ids[hypotheses[0]]
        ledger.apply(Action(
            action_id=f"{accepted}:gate-final", action_type=ActionType.GATE_VALIDATE,
            candidate_id=accepted, candidate_version=1,
            evidence_ids=(query_eid,),
            from_state=CandidateState.TRAIN_SUPPORTED,
            to_state=CandidateState.GATE_VALIDATED,
            note="unique support-consistent mechanism and Gate-Final validation",
        ))
    else:
        ledger.apply(Action(
            action_id=f"e02d:{index}:abstain", action_type=ActionType.ABSTAIN,
            note=("mechanism ambiguous" if prediction_identifiable
                  else "support-consistent mechanisms disagree on query"),
        ))

    states = Counter(c.state.value for c in ledger.candidates.values())
    return {
        "episode_id": index, "consistent_hypothesis_count": len(hypotheses),
        "prediction_identifiable": prediction_identifiable,
        "prediction": prediction, "gold": gold,
        "prediction_correct": prediction_identifiable and prediction == gold,
        "mechanism_identifiable": mechanism_identifiable,
        "accepted_candidate_id": accepted,
        "candidate_states": dict(states), "action_count": len(ledger.actions),
        "evidence_count": len(ledger.evidence),
        "abstained": not mechanism_identifiable,
    }


def run(seed: int = 17, support_size: int = 6) -> dict[str, Any]:
    episodes = make_episodes(seed=seed, support_size=support_size)
    rows = [run_episode(ep, i) for i, ep in enumerate(episodes)]
    n = len(rows)
    identified = sum(row["mechanism_identifiable"] for row in rows)
    covered = sum(row["prediction_identifiable"] for row in rows)
    correct = sum(row["prediction_correct"] for row in rows)
    return {
        "task": "E12A6_x_E02D_primitive_lifecycle", "seed": seed,
        "support_size": support_size, "hypothesis_class_size": len(RULES),
        "episodes": n, "mechanism_identification_coverage": identified / n,
        "query_prediction_coverage": covered / n,
        "query_accuracy_all_episodes": correct / n,
        "query_accuracy_when_covered": correct / covered if covered else None,
        "accepted_primitive_count": identified,
        "abstention_count": n - identified,
        "mean_consistent_hypotheses": sum(
            row["consistent_hypothesis_count"] for row in rows) / n,
        "lifecycle_action_count": sum(row["action_count"] for row in rows),
        "evidence_record_count": sum(row["evidence_count"] for row in rows),
        "episodes_detail": rows,
        "limitations": [
            "The 27-rule hypothesis class is declared in advance.",
            "This tests lifecycle integration, not open-world primitive discovery.",
            "The solver is exact symbolic enumeration, not a trained neural model.",
            "Only one held-out query is used per episode.",
            "Delayed post-deployment counterexamples are not yet included.",
        ],
    }


def run_sweep(seeds: int = 20, start_seed: int = 100) -> dict[str, Any]:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    results = []
    for support_size in range(1, 9):
        runs = [run(start_seed + offset, support_size) for offset in range(seeds)]
        total = sum(item["episodes"] for item in runs)
        results.append({
            "support_size": support_size, "seeds": seeds, "episodes": total,
            **{key: sum(item[key] * item["episodes"] for item in runs) / total
               for key in ("mechanism_identification_coverage",
                           "query_prediction_coverage",
                           "query_accuracy_all_episodes",
                           "mean_consistent_hypotheses")},
        })
    return {"task": "E12A6_x_E02D_support_sweep", "seed_start": start_seed,
            "seeds": seeds, "hypothesis_class_size": len(RULES), "results": results,
            "interpretation": (
                "Mechanism identification requires exactly one support-consistent rule. "
                "Prediction coverage can be higher when distinct rules agree on the query. "
                "Metrics are finite symbolic benchmark results, not neural generalization."
            )}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--support-size", type=int, default=6)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_sweep(args.seeds, args.start_seed) if args.sweep else run(args.seed, args.support_size)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)


if __name__ == "__main__":
    main()
