"""E02-I: streaming drift response with evidence-gated edge lifecycle.

The experiment tests whether a finite-rule learner can distinguish a transient
unreliable window from persistent structural replacement. Lifecycle mutations
remain explicit policy decisions, not learned autonomy.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from prototype.e02_edge_lifecycle import EdgeProposal, HyperedgeLifecycle
from prototype.e02h_boolean_rules import (
    Candidate, accuracy, discover, make_rows, pairwise_baseline,
)


def _ids(rows, candidate: Candidate) -> tuple[tuple[str, ...], tuple[str, ...]]:
    support, counter = [], []
    from prototype.e02h_boolean_rules import predict
    for row in rows:
        (support if predict(row, candidate) == row.label else counter).append(row.sample_id)
    return tuple(support), tuple(counter)


def _proposal(edge_id: str, candidate: Candidate, train, gain: float) -> EdgeProposal:
    support, counter = _ids(train, candidate)
    return EdgeProposal(
        edge_id=edge_id,
        members=tuple(f"x{i}" for i in candidate.members),
        roles=tuple(f"input-{i}" for i in range(len(candidate.members))),
        relation_type=f"boolean-table-{len(candidate.members)}-{candidate.truth_table}",
        support_ids=support,
        counterexample_ids=counter,
        validation_gain=gain,
        cost=1.0,
    )


def _edge_id(candidate: Candidate) -> str:
    return "edge-" + "-".join(map(str, candidate.members)) + f"-t{candidate.truth_table}"


def run_episode(seed: int, *, train_n: int = 1024, gate_n: int = 512,
                test_n: int = 512, min_gain: float = 0.05,
                prune_patience: int = 3) -> dict:
    # The two concepts use disjoint feature triples, so a persistent switch is
    # a genuine membership replacement rather than a small parameter drift.
    target_a = (0, 1, 2)
    target_b = (3, 4, 5)
    from prototype.e02h_boolean_rules import admissible_target_tables
    import random
    rng = random.Random(seed * 101 + 5)
    tables = admissible_target_tables()
    table_a, table_b = rng.sample(tables, 2)

    manager = HyperedgeLifecycle(
        min_support=3, min_gain=min_gain, prune_patience=prune_patience,
        max_edges=4,
    )
    current: Candidate | None = None
    current_id: str | None = None
    events = []
    windows = []
    # Three stable windows, one severe but transient label-corruption window,
    # two recovery windows, then three windows of a persistent new concept.
    schedule = [
        (target_a, table_a, 0.02, "stable"),
        (target_a, table_a, 0.02, "stable"),
        (target_a, table_a, 0.02, "stable"),
        (target_a, table_a, 0.48, "transient_noise"),
        (target_a, table_a, 0.02, "recovery"),
        (target_a, table_a, 0.02, "recovery"),
        (target_b, table_b, 0.02, "persistent_shift"),
        (target_b, table_b, 0.02, "persistent_shift"),
        (target_b, table_b, 0.02, "persistent_shift"),
    ]

    for window, (members, table, noise, regime) in enumerate(schedule):
        base = seed * 100000 + window * 10000
        train = make_rows(seed=base + 1, count=train_n,
                          target_members=members, target_table=table, noise=noise)
        gate = make_rows(seed=base + 2, count=gate_n,
                         target_members=members, target_table=table, noise=noise)
        test = make_rows(seed=base + 3, count=test_n,
                         target_members=members, target_table=table, noise=noise)
        challenger = discover(train)
        challenger_gain = accuracy(gate, challenger) - pairwise_baseline(train, gate)

        action = "NONE"
        current_gain = None
        if current is not None and current_id is not None:
            current_gain = accuracy(gate, current) - pairwise_baseline(train, gate)
            support, counter = _ids(train, current)
            updated = manager.observe(
                current_id, support_ids=support, counterexample_ids=counter,
                validation_gain=current_gain, cost=1.0,
            )
            action = "OBSERVE"
            if updated.stale_windows >= prune_patience:
                manager.prune(current_id)
                events.append({"window": window, "op": "PRUNE", "edge_id": current_id})
                current = None
                current_id = None
                action = "PRUNE"

        if current is None and challenger_gain >= min_gain:
            proposed_id = _edge_id(challenger)
            if proposed_id not in manager.edges:
                manager.create(_proposal(proposed_id, challenger, train, challenger_gain))
                current, current_id = challenger, proposed_id
                events.append({"window": window, "op": "CREATE", "edge_id": proposed_id})
                action = "CREATE" if action == "NONE" else action + "+CREATE"

        windows.append({
            "window": window, "regime": regime, "action": action,
            "challenger_members": list(challenger.members),
            "challenger_gain": challenger_gain,
            "current_gain": current_gain,
            "test_accuracy": accuracy(test, challenger),
            "active_edge_id": current_id,
            "stale_windows": manager.edges[current_id].stale_windows if current_id else None,
        })

    expected_a = set(target_a)
    expected_b = set(target_b)
    created_ids = [e["edge_id"] for e in events if e["op"] == "CREATE"]
    pruned_ids = [e["edge_id"] for e in events if e["op"] == "PRUNE"]
    return {
        "seed": seed,
        "initial_concept_created": bool(created_ids),
        "transient_noise_did_not_prune": len(pruned_ids) == 0 or (
            next((w["window"] for w in events if w["op"] == "PRUNE"), 99) > 5
        ),
        "persistent_shift_pruned_old": bool(pruned_ids),
        "new_concept_active": current is not None and set(current.members) == expected_b,
        "old_members": sorted(expected_a),
        "new_members": sorted(expected_b),
        "events": events,
        "windows": windows,
        "active_edges": sorted(manager.edges),
    }


def run(seeds: int = 20, start_seed: int = 1200) -> dict:
    episodes = [run_episode(start_seed + i) for i in range(seeds)]
    return {
        "task": "E02I_streaming_transient_noise_vs_persistent_structural_shift",
        "seeds": seeds,
        "summary": {
            "transient_noise_preserved_rate": sum(e["transient_noise_did_not_prune"] for e in episodes) / seeds,
            "persistent_shift_pruned_rate": sum(e["persistent_shift_pruned_old"] for e in episodes) / seeds,
            "new_concept_recovery_rate": sum(e["new_concept_active"] for e in episodes) / seeds,
        },
        "episodes": episodes,
        "limitations": [
            "Synthetic binary Boolean concepts with a predeclared 9-window schedule.",
            "Two concepts use disjoint triples; overlapping or gradual drift is not covered.",
            "Lifecycle thresholds and prune patience are explicit hand-designed policy.",
            "This tests streaming evidence handling, not general autonomous concept invention.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1200)
    args = parser.parse_args()
    print(json.dumps(run(args.seeds, args.start_seed), indent=2))


if __name__ == "__main__":
    main()
