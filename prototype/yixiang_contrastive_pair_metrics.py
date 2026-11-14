"""Evaluate contrastive analogy pairs without collapsing to case-level accuracy."""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Mapping, Sequence
from prototype.yixiang_benchmark import validate_dataset, validate_prediction

def evaluate_contrastive_pairs(cases: Sequence[Mapping], predictions: Sequence[Mapping], pairs: Sequence[Mapping], *, allow_fixture_expected: bool = False) -> dict:
    """Score paired cases whose expected decisions differ; missing predictions abstain."""
    validate_dataset(cases)
    statuses = {case["label_status"] for case in cases}
    if "pending_review" in statuses:
        raise ValueError("pending_review cases cannot be scored")
    if "fixture_expected" in statuses and not allow_fixture_expected:
        raise ValueError("fixture_expected labels require allow_fixture_expected=True and are not human gold")
    if len(statuses) != 1 or not statuses <= {"fixture_expected", "adjudicated"}:
        raise ValueError("contrastive evaluation requires one eligible label population")
    if not isinstance(predictions, Sequence) or isinstance(predictions, (str, bytes)):
        raise ValueError("predictions must be a sequence")
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)) or not pairs:
        raise ValueError("pairs must be a non-empty sequence")
    by_id = {case["case_id"]: case for case in cases}
    groups = {}
    paired_case_ids = []
    for pair in pairs:
        if not isinstance(pair, Mapping) or set(pair) != {"pair_id", "case_ids"}:
            raise ValueError("each pair requires exactly pair_id and case_ids")
        pair_id = pair["pair_id"]
        case_ids = pair["case_ids"]
        if not isinstance(pair_id, str) or not pair_id.strip():
            raise ValueError("pair_id must be non-empty")
        if pair_id in groups:
            raise ValueError("duplicate pair_id")
        if not isinstance(case_ids, (list, tuple)) or len(case_ids) != 2 or len(set(case_ids)) != 2:
            raise ValueError(f"pair {pair_id} must reference exactly two distinct case IDs")
        if any(not isinstance(case_id, str) or case_id not in by_id for case_id in case_ids):
            raise ValueError(f"pair {pair_id} references an unknown case ID")
        members = [by_id[case_id] for case_id in case_ids]
        if len({m["split_group"] for m in members}) != 1:
            raise ValueError(f"pair {pair_id} crosses split groups")
        if members[0]["gold_decision"] == members[1]["gold_decision"]:
            raise ValueError(f"pair {pair_id} must have different expected decisions")
        groups[pair_id] = members
        paired_case_ids.extend(case_ids)
    if len(paired_case_ids) != len(set(paired_case_ids)) or set(paired_case_ids) != set(by_id):
        raise ValueError("each case must occur in exactly one contrastive pair")
    predicted = {}
    for item in predictions:
        validate_prediction(item)
        if item["case_id"] in predicted:
            raise ValueError("duplicate prediction case_id")
        predicted[item["case_id"]] = item["decision"]
    known = {case["case_id"] for case in cases}
    if set(predicted) - known:
        raise ValueError("prediction references unknown case_id")
    exact = 0
    fully_answered = 0
    flip_correct = 0
    submitted_pairs = 0
    collapsed = 0
    rows = []
    for group_id, members in sorted(groups.items()):
        members = sorted(members, key=lambda item: item["case_id"])
        gold = [m["gold_decision"] for m in members]
        guess = [predicted.get(m["case_id"], "abstain") for m in members]
        pair_exact = guess == gold
        pair_answered = all(value != "abstain" for value in guess)
        pair_submitted = all(m["case_id"] in predicted for m in members)
        expected_flip = gold[0] != gold[1]
        predicted_flip = guess[0] != guess[1]
        exact += pair_exact
        fully_answered += pair_answered
        submitted_pairs += pair_submitted
        flip_correct += expected_flip and pair_submitted and predicted_flip
        collapsed += not predicted_flip
        rows.append({"group_id": group_id, "case_ids": [m["case_id"] for m in members],
                     "gold_decisions": gold, "predicted_decisions": guess,
                     "pair_exact": pair_exact, "fully_answered": pair_answered,
                     "expected_flip": expected_flip, "predicted_flip": predicted_flip})
    total = len(groups)
    return {"pair_count": total, "pair_exact_accuracy": exact / total,
            "submitted_pairs": submitted_pairs,
            "decision_flip_sensitivity": flip_correct / submitted_pairs if submitted_pairs else None,
            "collapsed_pair_count": collapsed, "collapsed_pair_rate": collapsed / total,
            "fully_answered_pairs": fully_answered, "pair_selective_coverage": fully_answered / total,
            "pair_selective_risk": 1 - exact / fully_answered if fully_answered else None,
            "pairs": rows}