"""E02-I: evidence-gated evolution of discovered relation structures.

The learner re-discovers a bounded Boolean candidate independently in each
observation window. A separate evolution controller requires repeated
confirmatory windows before replacing a persistent relation, and repeated
failure before retiring it. Hidden schedules are generator/audit-only.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass

from prototype.e02h_boolean_rules import (
    Candidate, Row, accuracy, admissible_target_tables, discover, pairwise_baseline,
)


def _make_window_rows(*, seed: int, count: int, target: tuple[int, ...],
                      truth_table: int, noise: float = 0.02,
                      width: int = 8) -> list[Row]:
    if count < 4 or not 2 <= len(target) <= 3 or len(set(target)) != len(target):
        raise ValueError("invalid sample count or target")
    if any(i < 0 or i >= width for i in target):
        raise ValueError("target member outside feature width")
    if not 0 <= truth_table < (1 << (1 << len(target))) or not 0 <= noise < 0.5:
        raise ValueError("invalid truth table or noise")
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        values = tuple(rng.choice((-1, 1)) for _ in range(width))
        state = 0
        for position, member in enumerate(target):
            if values[member] == 1:
                state |= 1 << (len(target) - position - 1)
        label = 1 if (truth_table >> state) & 1 else -1
        if rng.random() < noise:
            label *= -1
        rows.append(Row(f"{seed}:{i}", values, label))
    return rows


@dataclass(frozen=True)
class Snapshot:
    members: tuple[int, ...]
    truth_table: int
    gate_accuracy: float
    pairwise_accuracy: float
    current_gate_accuracy: float | None = None

    @property
    def accepted(self) -> bool:
        return self.gate_accuracy >= 0.75 and (len(self.members) == 2 or self.gate_accuracy - self.pairwise_accuracy >= 0.05)

    @property
    def signature(self) -> tuple[tuple[int, ...], int]:
        return self.members, self.truth_table


class RelationEvolution:
    """Two-window confirmation, hysteresis, and auditable structural versions."""

    def __init__(self, *, confirm_windows: int = 2, retire_windows: int = 2):
        if confirm_windows < 2 or retire_windows < 2:
            raise ValueError("confirmation and retirement require at least two windows")
        self.confirm_windows = confirm_windows
        self.retire_windows = retire_windows
        self.current: Snapshot | None = None
        self.current_status = "ABSENT"
        self.pending_signature: tuple[tuple[int, ...], int] | None = None
        self.pending_count = 0
        self.invalid_count = 0
        self.version = 0
        self.events: list[dict] = []

    def observe(self, snapshot: Snapshot | None, *, window: int) -> str:
        candidate_accepted = snapshot is not None and snapshot.accepted
        current_gate_accuracy = None
        if snapshot is not None:
            current_gate_accuracy = (
                snapshot.current_gate_accuracy
                if snapshot.current_gate_accuracy is not None
                else snapshot.gate_accuracy
            )
        # Persistent structures must satisfy the same evidence standard as
        # newly proposed structures. Absolute accuracy alone is insufficient
        # for a 3-member relation when a simpler pairwise explanation catches up.
        current_is_valid = (
            self.current is not None
            and current_gate_accuracy is not None
            and current_gate_accuracy >= 0.75
            and (
                len(self.current.members) == 2
                or (
                    snapshot is not None
                    and current_gate_accuracy - snapshot.pairwise_accuracy >= 0.05
                )
            )
        )

        if self.current is None:
            if not candidate_accepted:
                self.pending_signature = None
                self.pending_count = 0
                self.current_status = "ABSENT"
                action = "NO_RELATION"
                self.events.append({"window": window, "action": action,
                                    "current_status": self.current_status})
                return action
            self.current = snapshot
            self.current_status = "ACTIVE"
            self.invalid_count = 0
            self.version += 1
            self.pending_signature = None
            self.pending_count = 0
            action = "CREATE"
            self.events.append({"window": window, "action": action,
                                "version": self.version,
                                "current_status": self.current_status})
            return action

        if current_is_valid:
            self.invalid_count = 0
            self.current_status = "ACTIVE"
        else:
            self.invalid_count += 1
            self.current_status = "DEGRADED"

        if candidate_accepted and snapshot.signature == self.current.signature:
            self.pending_signature = None
            self.pending_count = 0
            self.invalid_count = 0
            self.current_status = "ACTIVE"
            action = "KEEP"
        elif candidate_accepted:
            if snapshot.signature == self.pending_signature:
                self.pending_count += 1
            else:
                self.pending_signature = snapshot.signature
                self.pending_count = 1
            if self.pending_count >= self.confirm_windows:
                old = self.current.signature
                self.current = snapshot
                self.version += 1
                self.pending_signature = None
                self.pending_count = 0
                self.invalid_count = 0
                self.current_status = "ACTIVE"
                action = "RECONFIGURE"
                self.events.append({"window": window, "action": action,
                                    "from": old, "to": snapshot.signature,
                                    "version": self.version,
                                    "current_status": self.current_status})
                return action
            action = "HOLD_PENDING"
        else:
            self.pending_signature = None
            self.pending_count = 0
            if current_is_valid:
                action = "KEEP"
            elif self.invalid_count >= self.retire_windows:
                old = self.current.signature
                self.current = None
                self.current_status = "ABSENT"
                self.version += 1
                self.invalid_count = 0
                action = "RETIRE"
                self.events.append({"window": window, "action": action,
                                    "from": old, "version": self.version,
                                    "current_status": self.current_status})
                return action
            else:
                action = "DEGRADE"

        self.events.append({"window": window, "action": action,
                            "version": self.version,
                            "current_status": self.current_status,
                            "current_gate_accuracy": current_gate_accuracy,
                            "invalid_streak": self.invalid_count})
        return action


def _two_input_slice(table: int) -> int:
    # Restrict the 3-input table to the third input being zero.
    return sum(((table >> (state * 2)) & 1) << state for state in range(4))


def _two_inputs_essential(table: int) -> bool:
    return all(any(((table >> state) & 1) != ((table >> (state ^ (1 << bit))) & 1)
                   for state in range(4) if not (state & (1 << bit)))
               for bit in (0, 1))


def _targets(scenario: str, base2: tuple[int, ...], expanded3: tuple[int, ...],
             table3: int, table2: int, window: int) -> tuple[tuple[int, ...], int] | None:
    if scenario == "stable":
        return expanded3, table3
    if scenario == "member_add":
        return (base2, table2) if window < 2 else (expanded3, table3)
    if scenario == "member_remove":
        return (expanded3, table3) if window < 2 else (base2, table2)
    if scenario == "rule_change":
        return expanded3, (table3 if window < 2 else table3 ^ 255)
    if scenario == "transient_rule_change":
        return expanded3, (table3 ^ 255 if window == 2 else table3)
    if scenario == "disappear":
        return (expanded3, table3) if window < 2 else None
    if scenario == "never_present":
        return None
    raise ValueError("unknown scenario")

def run_episode(*, seed: int, scenario: str, windows: int = 5,
                train_n: int = 1024, gate_n: int = 512,
                test_n: int = 512, noise: float = 0.02) -> dict:
    if windows < 4 or min(train_n, gate_n, test_n) < 4:
        raise ValueError("at least four windows and four samples per split are required")
    rng = random.Random(seed * 7919 + 41)
    base2 = tuple(sorted(rng.sample(range(6), 2)))
    expanded3 = tuple(sorted((*base2, 6)))
    tables = tuple(t for t in admissible_target_tables()
                   if _two_inputs_essential(_two_input_slice(t)))
    table3 = rng.choice(tables)
    table2 = _two_input_slice(table3)
    controller = RelationEvolution()
    rows = []
    for window in range(windows):
        target = _targets(scenario, base2, expanded3, table3, table2, window)
        if target is None:
            # Null relation: independent random labels, not a hidden "inactive" flag.
            train = []
            gate = []
            test = []
            for split, count in ((1, train_n), (2, gate_n), (3, test_n)):
                rr = random.Random(seed * 1000003 + window * 101 + split)
                generated = []
                for i in range(count):
                    values = tuple(rr.choice((-1, 1)) for _ in range(8))
                    label = rr.choice((-1, 1))
                    generated.append(Row(f"{seed}:{window}:{split}:{i}", values, label))
                if split == 1:
                    train = generated
                elif split == 2:
                    gate = generated
                else:
                    test = generated
            # Test split is evaluation-only and never affects the state transition.
            winner = discover(train)
            gate_acc = accuracy(gate, winner)
            pair_acc = pairwise_baseline(train, gate)
            test_acc = accuracy(test, winner)
            pair_test_acc = pairwise_baseline(train, test)
            snapshot = Snapshot(winner.members, winner.truth_table, gate_acc, pair_acc)
        else:
            members, truth = target
            train = _make_window_rows(seed=seed * 1000003 + window * 101 + 1,
                                      count=train_n, target=members,
                                      truth_table=truth, noise=noise)
            gate = _make_window_rows(seed=seed * 1000003 + window * 101 + 2,
                                     count=gate_n, target=members,
                                     truth_table=truth, noise=noise)
            test = _make_window_rows(seed=seed * 1000003 + window * 101 + 3,
                                     count=test_n, target=members,
                                     truth_table=truth, noise=noise)
            winner = discover(train)
            test_acc = accuracy(test, winner)
            pair_test_acc = pairwise_baseline(train, test)
            snapshot = Snapshot(winner.members, winner.truth_table,
                                accuracy(gate, winner),
                                pairwise_baseline(train, gate))
        if controller.current is not None:
            current_candidate = Candidate(
                controller.current.members, controller.current.truth_table, 0.0
            )
            snapshot = Snapshot(
                snapshot.members, snapshot.truth_table,
                snapshot.gate_accuracy, snapshot.pairwise_accuracy,
                accuracy(gate, current_candidate),
            )
        action = controller.observe(snapshot, window=window)
        persistent_candidate = (
            Candidate(controller.current.members, controller.current.truth_table, 0.0)
            if controller.current is not None else None
        )
        persistent_test_acc = (
            accuracy(test, persistent_candidate)
            if persistent_candidate is not None else None
        )
        rows.append({
            "window": window, "action": action,
            "candidate_members": list(snapshot.members),
            "candidate_truth_table": snapshot.truth_table,
            "gate_accuracy": snapshot.gate_accuracy,
            "current_gate_accuracy": snapshot.current_gate_accuracy,
            "pairwise_gate_accuracy": snapshot.pairwise_accuracy,
            "candidate_test_accuracy": test_acc,
            "pairwise_test_accuracy": pair_test_acc,
            "persistent_test_accuracy": persistent_test_acc,
            "persistent_members": (
                list(controller.current.members) if controller.current else None
            ),
            "persistent_truth_table": (
                controller.current.truth_table if controller.current else None
            ),
            "split_ids_disjoint": (len({r.sample_id for r in train} | {r.sample_id for r in gate} | {r.sample_id for r in test}) == len(train) + len(gate) + len(test)),
            "accepted": snapshot.accepted,
            "current_status": controller.current_status,
            "target_for_audit_only": list(target[0]) if target else None,
            "target_table_for_audit_only": target[1] if target else None,
        })
    return {
        "seed": seed, "scenario": scenario, "windows": rows,
        "events": controller.events, "final_version": controller.version,
        "final_relation": (
            {"members": list(controller.current.members),
             "truth_table": controller.current.truth_table}
            if controller.current else None
        ),
    }


def run(*, seeds: int = 20, start_seed: int = 1200) -> dict:
    scenarios = ("stable", "member_add", "member_remove", "rule_change",
                 "transient_rule_change", "disappear", "never_present")
    results = {
        scenario: [run_episode(seed=start_seed + i, scenario=scenario)
                   for i in range(seeds)]
        for scenario in scenarios
    }
    return {
        "task": "E02I_evidence_gated_relation_evolution",
        "seeds_per_scenario": seeds,
        "summary": {
            "stable_no_reconfiguration": sum(
                all(w["action"] != "RECONFIGURE" for w in e["windows"])
                for e in results["stable"]) / seeds,
            "stable_final_structure_correct": sum(
                e["final_relation"] == {
                    "members": e["windows"][-1]["target_for_audit_only"],
                    "truth_table": e["windows"][-1]["target_table_for_audit_only"],
                } for e in results["stable"]) / seeds,
            "member_add_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["member_add"]) / seeds,
            "member_add_final_structure_correct": sum(
                e["final_relation"] == {
                    "members": e["windows"][-1]["target_for_audit_only"],
                    "truth_table": e["windows"][-1]["target_table_for_audit_only"],
                } for e in results["member_add"]) / seeds,
            "member_remove_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["member_remove"]) / seeds,
            "member_remove_final_structure_correct": sum(
                e["final_relation"] == {
                    "members": e["windows"][-1]["target_for_audit_only"],
                    "truth_table": e["windows"][-1]["target_table_for_audit_only"],
                } for e in results["member_remove"]) / seeds,
            "rule_change_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["rule_change"]) / seeds,
            "rule_change_final_structure_correct": sum(
                e["final_relation"] == {
                    "members": e["windows"][-1]["target_for_audit_only"],
                    "truth_table": e["windows"][-1]["target_table_for_audit_only"],
                } for e in results["rule_change"]) / seeds,
            "transient_change_no_reconfiguration": sum(
                all(w["action"] != "RECONFIGURE" for w in e["windows"])
                for e in results["transient_rule_change"]) / seeds,
            "transient_final_structure_correct": sum(
                e["final_relation"] == {
                    "members": e["windows"][-1]["target_for_audit_only"],
                    "truth_table": e["windows"][-1]["target_table_for_audit_only"],
                } for e in results["transient_rule_change"]) / seeds,
            "disappearance_retired": sum(
                any(w["action"] == "RETIRE" for w in e["windows"])
                for e in results["disappear"]) / seeds,
            "disappearance_finally_absent": sum(
                e["final_relation"] is None for e in results["disappear"]) / seeds,
            "mean_candidate_test_accuracy_by_scenario": {
                scenario: sum(w["candidate_test_accuracy"] for e in episodes for w in e["windows"]) / (seeds * 5)
                for scenario, episodes in results.items()
            },
            "mean_persistent_test_accuracy_by_scenario": {
                scenario: (
                    sum(w["persistent_test_accuracy"] for e in episodes for w in e["windows"]
                        if w["persistent_test_accuracy"] is not None)
                    / sum(1 for e in episodes for w in e["windows"]
                          if w["persistent_test_accuracy"] is not None)
                    if any(w["persistent_test_accuracy"] is not None
                           for e in episodes for w in e["windows"]) else None
                )
                for scenario, episodes in results.items()
            },
            "never_present_no_false_create": sum(
                not any(w["action"] == "CREATE" for w in e["windows"])
                for e in results["never_present"]
            ) / seeds,
            "never_present_finally_absent": sum(
                e["final_relation"] is None for e in results["never_present"]
            ) / seeds,
            "null_window_false_create_rate": (
                sum(
                    w["action"] == "CREATE"
                    for episodes in results.values()
                    for e in episodes for w in e["windows"]
                    if w["target_for_audit_only"] is None
                )
                / sum(
                    w["target_for_audit_only"] is None
                    for episodes in results.values()
                    for e in episodes for w in e["windows"]
                )
            ),
            "degraded_episode_rate_by_scenario": {
                scenario: sum(
                    any(w["current_status"] == "DEGRADED" for w in e["windows"])
                    for e in episodes
                ) / seeds
                for scenario, episodes in results.items()
            },
            "persistent_relation_coverage_by_scenario": {
                scenario: sum(w["persistent_test_accuracy"] is not None
                              for e in episodes for w in e["windows"]) / (seeds * 5)
                for scenario, episodes in results.items()
            },
            "mean_pairwise_test_accuracy_by_scenario": {
                scenario: sum(w["pairwise_test_accuracy"] for e in episodes for w in e["windows"]) / (seeds * 5)
                for scenario, episodes in results.items()
            },
            "all_train_gate_test_splits_disjoint": all(
                w["split_ids_disjoint"] for episodes in results.values()
                for e in episodes for w in e["windows"]
            ),
        },
        "episodes": results,
        "limitations": [
            "Synthetic binary Boolean rules with a bounded 2-3 feature truth-table grammar.",
            "Seven predeclared scenarios, including a never-present null-world negative control; not open-world structure evolution.",
            "Gate controls state transitions; an independent test split evaluates each window after decisions and never feeds back.",
            "The hidden target is used only for post-hoc exact-structure scoring; test accuracy is not a proof of causal or open-world validity.",
            "A fixed two-window confirmation policy; no learned transition policy.",
            "No causal or natural-language discovery claim.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1200)
    args = parser.parse_args()
    print(json.dumps(run(seeds=args.seeds, start_seed=args.start_seed), indent=2))


if __name__ == "__main__":
    main()
