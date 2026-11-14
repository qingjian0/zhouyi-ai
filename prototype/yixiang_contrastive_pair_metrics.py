"""Evaluate contrastive analogy pairs without collapsing to case-level accuracy."""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Mapping, Sequence
from prototype.yixiang_benchmark import validate_dataset, validate_prediction

def evaluate_contrastive_pairs(cases: Sequence[Mapping], predictions: Sequence[Mapping], *, allow_fixture_expected: bool = False) -> dict:
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
    groups = defaultdict(list)
    for case in cases:
        groups[case["independence_group"]].append(case)
    if not groups:
        raise ValueError("at least one contrastive pair is required")
    for group_id, members in groups.items():
        if len(members) != 2:
            raise ValueError(f"contrastive group {group_id} must contain exactly two cases")
        if len({m["split_group"] for m in members}) != 1:
            raise ValueError(f"contrastive group {group_id} crosses split groups")
        if members[0]["gold_decision"] == members[1]["gold_decision"]:
            raise ValueError(f"contrastive group {group_id} must have different expected decisions")
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