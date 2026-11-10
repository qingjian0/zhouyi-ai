"""E12-A6 x E02-D: finite-world lifecycle runner with Gate-Final and Locked-Test.

This connects the existing exact 27-rule symbolic benchmark to the lifecycle
ledger. It validates integration and delayed-counterexample handling, not
open-world discovery or neural learning.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from prototype.e02_rule_ood import (
    QUERIES, RULES, Episode, consistent_rules, make_episodes, target_c,
)
from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, Candidate, CandidateState, Evidence,
    LifecycleLedger, SplitRole,
)


def _candidate_id(index: int, rule: tuple[int, int, int]) -> str:
    return f"e02d:{index}:affine:{rule[0]}-{rule[1]}-{rule[2]}"


def run_episode(
    episode: Episode,
    index: int,
    *,
    inject_counterexample: bool = False,
) -> dict[str, Any]:
    ledger = LifecycleLedger()
    support_ids = []
    support_pairs = {(a, b) for a, b, _ in episode.support}
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

    # Keep the original held-out query and use another unseen query for Gate-Final
    # when the support size leaves enough observations. A final unseen query is
    # reserved for Locked-Test and is never used to choose the candidate.
    unseen = [q for q in QUERIES if q not in support_pairs]
    if episode.query not in unseen:
        raise AssertionError("episode query must be outside support")
    gate_queries = [episode.query]
    extras = [q for q in unseen if q != episode.query]
    if len(extras) >= 2:
        gate_queries.append(extras[0])
        locked_query = extras[-1]
    elif len(extras) == 1:
        locked_query = extras[0]
    else:
        raise ValueError("support_size must leave at least one Locked-Test query")

    mechanism_identifiable = len(hypotheses) == 1
    accepted = None
    gate_evidence_ids = []
    gate_prediction_correct = []
    for offset, (a, b) in enumerate(gate_queries):
        predictions = {target_c(rule, a, b) for rule in hypotheses}
        prediction_identifiable = len(predictions) == 1
        prediction = next(iter(predictions)) if prediction_identifiable else None
        gold = target_c(episode.rule, a, b)
        gate_prediction_correct.append(prediction_identifiable and prediction == gold)
        eid = f"e02d:{index}:gate-final:{offset}"
        gate_evidence_ids.append(eid)
        commit_step = 7 + offset * 2
        ledger.add_evidence(Evidence(
            evidence_id=eid, episode_id=f"e02d-{index}",
            world_family="z3-affine-rule-family", split_role=SplitRole.GATE_FINAL,
            observation_id=f"gate-query-{a}-{b}", outcome=str(gold),
            model_version="e02d-exact-symbolic-v1", measurement_cost=1.0,
            prediction_commit_step=commit_step,
            label_visibility_step=commit_step + 1,
            provenance="Gate-Final label revealed after prediction commit",
        ))

    if mechanism_identifiable and all(gate_prediction_correct):
        accepted = candidate_ids[hypotheses[0]]
        ledger.apply(Action(
            action_id=f"{accepted}:gate-final", action_type=ActionType.GATE_VALIDATE,
            candidate_id=accepted, candidate_version=1,
            evidence_ids=tuple(gate_evidence_ids),
            from_state=CandidateState.TRAIN_SUPPORTED,
            to_state=CandidateState.GATE_VALIDATED,
            note="unique support-consistent mechanism passed Gate-Final queries",
        ))
    else:
        ledger.apply(Action(
            action_id=f"e02d:{index}:abstain", action_type=ActionType.ABSTAIN,
            note=("mechanism ambiguous" if not mechanism_identifiable
                  else "Gate-Final prediction did not validate candidate"),
        ))

    # Locked-Test is revealed only after the candidate decision is frozen.
    la, lb = locked_query
    locked_prediction_set = {target_c(rule, la, lb) for rule in hypotheses}
    locked_prediction_identifiable = len(locked_prediction_set) == 1
    locked_prediction = next(iter(locked_prediction_set)) if locked_prediction_identifiable else None
    locked_gold = target_c(episode.rule, la, lb)
    observed_locked_label = (locked_gold + 1) % 3 if inject_counterexample else locked_gold
    locked_eid = f"e02d:{index}:locked-test"
    ledger.add_evidence(Evidence(
        evidence_id=locked_eid, episode_id=f"e02d-{index}",
        world_family="z3-affine-rule-family", split_role=SplitRole.LOCKED_TEST,
        observation_id=f"locked-query-{la}-{lb}", outcome=str(observed_locked_label),
        model_version="e02d-exact-symbolic-v1", measurement_cost=1.0,
        prediction_commit_step=20, label_visibility_step=21,
        provenance=("injected delayed counterexample" if inject_counterexample
                    else "Locked-Test label revealed after frozen prediction"),
    ))
    locked_correct = locked_prediction_identifiable and locked_prediction == observed_locked_label
    if accepted is not None and not locked_correct:
        ledger.apply(Action(
            action_id=f"{accepted}:locked-challenge", action_type=ActionType.CHALLENGE,
            candidate_id=accepted, candidate_version=1,
            evidence_ids=(locked_eid,),
            from_state=CandidateState.GATE_VALIDATED,
            to_state=CandidateState.CHALLENGED,
            note="Locked-Test counterexample challenges accepted primitive",
        ))

    states = Counter(c.state.value for c in ledger.candidates.values())
    return {
        "episode_id": index, "consistent_hypothesis_count": len(hypotheses),
        "mechanism_identifiable": mechanism_identifiable,
        "accepted_candidate_id": accepted,
        "gate_query_count": len(gate_queries),
        "gate_all_correct": all(gate_prediction_correct),
        "locked_test_prediction": locked_prediction,
        "locked_test_gold": observed_locked_label,
        "locked_test_correct": locked_correct,
        "counterexample_injected": inject_counterexample,
        "candidate_states": dict(states), "action_count": len(ledger.actions),
        "evidence_count": len(ledger.evidence),
        "abstained": accepted is None,
    }


def run(seed: int = 17, support_size: int = 6) -> dict[str, Any]:
    if not 1 <= support_size <= 7:
        raise ValueError("lifecycle runner requires support_size between 1 and 7")
    episodes = make_episodes(seed=seed, support_size=support_size)
    rows = [run_episode(ep, i) for i, ep in enumerate(episodes)]
    n = len(rows)
    accepted = sum(row["accepted_candidate_id"] is not None for row in rows)
    locked_correct = sum(row["locked_test_correct"] for row in rows)
    return {
        "task": "E12A6_x_E02D_primitive_lifecycle",
        "seed": seed, "support_size": support_size,
        "hypothesis_class_size": len(RULES), "episodes": n,
        "mechanism_identification_coverage": accepted / n,
        "locked_test_coverage": sum(row["locked_test_prediction"] is not None for row in rows) / n,
        "locked_test_accuracy_all_episodes": locked_correct / n,
        "locked_test_accuracy_when_covered": (
            locked_correct / sum(row["locked_test_prediction"] is not None for row in rows)
            if any(row["locked_test_prediction"] is not None for row in rows) else None
        ),
        "accepted_primitive_count": accepted,
        "delayed_counterexample_count": sum(
            row["candidate_states"].get("challenged", 0) > 0 for row in rows
        ),
        "abstention_count": n - accepted,
        "mean_consistent_hypotheses": sum(
            row["consistent_hypothesis_count"] for row in rows) / n,
        "lifecycle_action_count": sum(row["action_count"] for row in rows),
        "evidence_record_count": sum(row["evidence_count"] for row in rows),
        "episodes_detail": rows,
        "limitations": [
            "The 27-rule hypothesis class is declared in advance.",
            "This tests lifecycle integration, not open-world primitive discovery.",
            "The solver is exact symbolic enumeration, not a trained neural model.",
            "Gate-Final and Locked-Test each contain at most two and one queries respectively.",
            "Delayed counterexamples are injected only in dedicated tests, not the clean benchmark.",
        ],
    }


def run_sweep(seeds: int = 20, start_seed: int = 100) -> dict[str, Any]:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    results = []
    for support_size in range(1, 8):
        runs = [run(start_seed + offset, support_size) for offset in range(seeds)]
        total = sum(item["episodes"] for item in runs)
        results.append({
            "support_size": support_size, "seeds": seeds, "episodes": total,
            **{key: sum(item[key] * item["episodes"] for item in runs) / total
               for key in ("mechanism_identification_coverage",
                           "locked_test_coverage",
                           "locked_test_accuracy_all_episodes",
                           "mean_consistent_hypotheses")},
        })
    return {"task": "E12A6_x_E02D_support_sweep", "seed_start": start_seed,
            "seeds": seeds, "hypothesis_class_size": len(RULES), "results": results,
            "interpretation": (
                "Primitive acceptance requires a unique support-consistent mechanism "
                "and Gate-Final agreement. Locked-Test is evaluated only after the "
                "candidate decision is frozen; these are finite symbolic results."
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
