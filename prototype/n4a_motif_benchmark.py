"""N4-A controlled motif-vs-bag-of-relations diagnostic.

The positive and negative classes have identical unordered relation-family
counts; they differ only in directed role topology. This is a deliberately
narrow synthetic identifiability test, not a natural-language benchmark.
"""
from __future__ import annotations

import json
from prototype.n4a_relation_discovery import (
    Edge, Node, RelationalCase, discover_relations, matches_candidate,
)


def make_case(index: int, partition: str, outcome: bool) -> RelationalCase:
    label = "positive" if outcome else "negative"
    prefix = f"case-{index}-{label}-"
    nodes = (
        Node(prefix + "a", "domain-specific-source", ("source",)),
        Node(prefix + "b", "domain-specific-process", ("mediator",)),
        Node(prefix + "c", "domain-specific-result", ("target",)),
        Node(prefix + "d", "domain-specific-context", ("context",)),
    )
    first = (
        Edge(prefix + "a", prefix + "b", "initiates")
        if outcome else Edge(prefix + "b", prefix + "a", "initiates")
    )
    edges = (
        first,
        Edge(prefix + "b", prefix + "c", "transforms"),
        Edge(prefix + "d", prefix + "a", "contextualizes"),
    )
    return RelationalCase(
        f"case-{index}-{label}", f"domain-{index % 3}", "directed-process",
        partition, outcome, nodes, edges,
    )


def run() -> dict:
    train = [
        make_case(i, "train", outcome)
        for i in range(40)
        for outcome in (True, False)
    ]
    validation = [
        make_case(100 + i, "validation", outcome)
        for i in range(20)
        for outcome in (True, False)
    ]
    discovery = discover_relations(
        train + validation, min_train_support=5,
        min_validation_support=5, min_validation_lift=0.2,
        max_nodes=3,
    )
    target = [
        candidate for candidate in discovery.candidates
        if candidate.role_count == 3
        and {role[0] for role in json.loads(candidate.signature)["roles"]}
        == {"source", "mediator", "target"}
    ]
    if len(target) != 1:
        raise RuntimeError(f"expected one directed-process candidate, got {len(target)}")
    candidate = target[0]
    predictions = [
        (case.outcome, matches_candidate(candidate, case, max_nodes=3))
        for case in validation
    ]
    correct = sum(actual == predicted for actual, predicted in predictions)
    bag_signatures = {
        tuple(sorted(edge.relation_family for edge in case.edges))
        for case in validation
    }
    class_bags = {
        outcome: {
            tuple(sorted(edge.relation_family for edge in case.edges))
            for case in validation if case.outcome is outcome
        }
        for outcome in (True, False)
    }
    bag_separates = class_bags[True].isdisjoint(class_bags[False])
    return {
        "task": "directed_role_topology_vs_unordered_relation_bag",
        "train_cases": len(train),
        "validation_cases": len(validation),
        "domains": sorted({case.domain for case in validation}),
        "candidate_id": candidate.candidate_id,
        "candidate_train_support": len(candidate.support_case_ids),
        "candidate_train_counterexamples": len(candidate.counterexample_case_ids),
        "candidate_validation_precision": candidate.validation_precision,
        "candidate_validation_lift": candidate.validation_lift,
        "motif_accuracy": correct / len(validation),
        "bag_of_relation_families_unique_signatures": len(bag_signatures),
        "bag_baseline_separates_classes": bag_separates,
        "bag_baseline_accuracy_ceiling_on_this_balanced_task": 0.5,
        "caveat": (
            "Synthetic proof-of-mechanism only. Role features and relation "
            "families are supplied; this does not measure raw-text parsing, "
            "causal discovery, learned semantics, or general intelligence."
        ),
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
