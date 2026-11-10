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
    Row, accuracy, admissible_target_tables, discover, pairwise_baseline,
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
        self.pending_signature: tuple[tuple[int, ...], int] | None = None
        self.pending_count = 0
        self.invalid_count = 0
        self.version = 0
        self.events: list[dict] = []

    def observe(self, snapshot: Snapshot | None, *, window: int) -> str:
        if snapshot is None or not snapshot.accepted:
            self.pending_signature = None
            self.pending_count = 0
            self.invalid_count += 1
            if self.current is None:
                action = "NO_RELATION"
            elif self.invalid_count >= self.retire_windows:
                old = self.current.signature
                self.current = None
                self.version += 1
                action = "RETIRE"
                self.events.append({"window": window, "action": action,
                                    "from": old, "version": self.version})
                self.invalid_count = 0
                return action
            else:
                action = "DEGRADE"
            self.events.append({"window": window, "action": action,
                                "invalid_streak": self.invalid_count})
            return action

        self.invalid_count = 0
        if self.current is None:
            self.current = snapshot
            self.version += 1
            self.pending_signature = None
            self.pending_count = 0
            action = "CREATE"
        elif snapshot.signature == self.current.signature:
            self.pending_signature = None
            self.pending_count = 0
            action = "KEEP"
        else:
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
                action = "RECONFIGURE"
                self.events.append({"window": window, "action": action,
                                    "from": old, "to": snapshot.signature,
                                    "version": self.version})
                return action
            action = "HOLD_PENDING"
        self.events.append({"window": window, "action": action,
                            "version": self.version})
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
    raise ValueError("unknown scenario")

def run_episode(*, seed: int, scenario: str, windows: int = 5,
                train_n: int = 1024, gate_n: int = 512,
                noise: float = 0.02) -> dict:
    if windows < 4:
        raise ValueError("at least four windows are required")
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
            for split, count in ((1, train_n), (2, gate_n)):
                rr = random.Random(seed * 1000003 + window * 101 + split)
                generated = []
                for i in range(count):
                    values = tuple(rr.choice((-1, 1)) for _ in range(8))
                    label = rr.choice((-1, 1))
                    generated.append(Row(f"{seed}:{window}:{split}:{i}", values, label))
                if split == 1:
                    train = generated
                else:
                    gate = generated
            # A best candidate is still produced; only its independent gate decides.
            winner = discover(train)
            gate_acc = accuracy(gate, winner)
            pair_acc = pairwise_baseline(train, gate)
            snapshot = Snapshot(winner.members, winner.truth_table, gate_acc, pair_acc)
        else:
            members, truth = target
            train = _make_window_rows(seed=seed * 1000003 + window * 101 + 1,
                                      count=train_n, target=members,
                                      truth_table=truth, noise=noise)
            gate = _make_window_rows(seed=seed * 1000003 + window * 101 + 2,
                                     count=gate_n, target=members,
                                     truth_table=truth, noise=noise)
            winner = discover(train)
            snapshot = Snapshot(winner.members, winner.truth_table,
                                accuracy(gate, winner),
                                pairwise_baseline(train, gate))
        action = controller.observe(snapshot, window=window)
        rows.append({
            "window": window, "action": action,
            "candidate_members": list(snapshot.members),
            "candidate_truth_table": snapshot.truth_table,
            "gate_accuracy": snapshot.gate_accuracy,
            "pairwise_gate_accuracy": snapshot.pairwise_accuracy,
            "accepted": snapshot.accepted,
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
                 "transient_rule_change", "disappear")
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
            "member_add_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["member_add"]) / seeds,
            "member_remove_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["member_remove"]) / seeds,
            "rule_change_reconfigured": sum(
                any(w["action"] == "RECONFIGURE" for w in e["windows"])
                for e in results["rule_change"]) / seeds,
            "transient_change_no_reconfiguration": sum(
                all(w["action"] != "RECONFIGURE" for w in e["windows"])
                for e in results["transient_rule_change"]) / seeds,
            "disappearance_retired": sum(
                any(w["action"] == "RETIRE" for w in e["windows"])
                for e in results["disappear"]) / seeds,
        },
        "episodes": results,
        "limitations": [
            "Synthetic binary Boolean rules with a bounded 2-3 feature truth-table grammar.",
            "Five predeclared change scenarios; not open-world structure evolution.",
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
