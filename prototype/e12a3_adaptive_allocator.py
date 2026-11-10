"""E12-A3-M1: deterministic UCB1 allocator for a shared proposal budget.

One allocation unit is one fixed-size proposal batch. The caller supplies a
bounded Gate-Dev incremental-utility reward after each batch. Gate-Final and
Locked-Test evidence are deliberately absent from this API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AllocationEvent:
    step: int
    family: str
    reward: float
    evidence_id: str
    family_pulls: int
    total_pulls: int


class UCB1Allocator:
    """Sequential, deterministic UCB1 allocation with an exploration floor.

    Rewards must be normalized Gate-Dev incremental utility in [0, 1].
    Each call to next_family() reserves exactly one proposal-batch unit. The
    matching record_gate_dev_reward() call closes that allocation before the
    next family can be selected.
    """

    def __init__(
        self,
        families: Sequence[str],
        total_budget: int,
        *,
        exploration_floor: int = 1,
        exploration_constant: float = math.sqrt(2.0),
    ) -> None:
        if isinstance(total_budget, bool) or not isinstance(total_budget, int):
            raise TypeError("total_budget must be an integer")
        if isinstance(exploration_floor, bool) or not isinstance(exploration_floor, int):
            raise TypeError("exploration_floor must be an integer")
        if total_budget < 0 or exploration_floor < 1:
            raise ValueError("total_budget must be non-negative and exploration_floor positive")
        names = tuple(sorted(set(families)))
        if not names or any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("at least one non-empty proposer family is required")
        if len(names) != len(tuple(families)):
            raise ValueError("proposer family names must be unique")
        if total_budget < len(names) * exploration_floor:
            raise ValueError("total_budget cannot satisfy every family's exploration floor")
        if isinstance(exploration_constant, bool) or not isinstance(exploration_constant, (int, float)):
            raise TypeError("exploration_constant must be numeric")
        exploration_constant = float(exploration_constant)
        if not math.isfinite(exploration_constant) or exploration_constant < 0:
            raise ValueError("exploration_constant must be finite and non-negative")

        self._families = names
        self._budget = total_budget
        self._floor = exploration_floor
        self._c = exploration_constant
        self._counts = {name: 0 for name in names}
        self._reward_sums = {name: 0.0 for name in names}
        self._events: list[AllocationEvent] = []
        self._evidence_ids: set[str] = set()
        self._used = 0
        self._pending: str | None = None
        self._frozen = False

    @property
    def remaining_budget(self) -> int:
        return self._budget - self._used

    @property
    def pending_family(self) -> str | None:
        return self._pending

    def _ucb(self, family: str) -> float:
        count = self._counts[family]
        if count == 0:
            return math.inf
        mean_reward = self._reward_sums[family] / count
        exploration = self._c * math.sqrt(math.log(max(1, self._used)) / count)
        return mean_reward + exploration

    def next_family(self) -> str:
        if self._frozen:
            raise RuntimeError("allocator is frozen")
        if self._pending is not None:
            raise RuntimeError("record the pending Gate-Dev reward before allocating again")
        if self._used >= self._budget:
            raise StopIteration("proposal budget exhausted")

        under_floor = [name for name in self._families if self._counts[name] < self._floor]
        if under_floor:
            selected = min(under_floor, key=lambda name: (self._counts[name], name))
        else:
            selected = min(self._families, key=lambda name: (-self._ucb(name), name))

        self._used += 1
        self._pending = selected
        return selected

    def record_gate_dev_reward(self, reward: float, evidence_id: str) -> AllocationEvent:
        if self._frozen:
            raise RuntimeError("allocator is frozen")
        if self._pending is None:
            raise RuntimeError("no pending allocation is awaiting a reward")
        if isinstance(reward, bool) or not isinstance(reward, (int, float)):
            raise TypeError("Gate-Dev reward must be numeric")
        reward = float(reward)
        if not math.isfinite(reward) or not 0.0 <= reward <= 1.0:
            raise ValueError("Gate-Dev reward must be finite and in [0, 1]")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string")
        if evidence_id in self._evidence_ids:
            raise ValueError("Gate-Dev evidence IDs must be unique")

        family = self._pending
        self._counts[family] += 1
        self._reward_sums[family] += reward
        self._evidence_ids.add(evidence_id)
        event = AllocationEvent(
            step=self._used,
            family=family,
            reward=reward,
            evidence_id=evidence_id,
            family_pulls=self._counts[family],
            total_pulls=self._used,
        )
        self._events.append(event)
        self._pending = None
        return event

    def freeze(self) -> dict[str, Any]:
        if self._pending is not None:
            raise RuntimeError("cannot freeze while a Gate-Dev reward is pending")
        self._frozen = True
        counts = dict(self._counts)
        return {
            "status": "FROZEN",
            "total_budget": self._budget,
            "used_budget": self._used,
            "remaining_budget": self.remaining_budget,
            "exploration_floor": self._floor,
            "exploration_constant": self._c,
            "allocations": counts,
            "reward_means": {
                name: (self._reward_sums[name] / counts[name] if counts[name] else None)
                for name in self._families
            },
            "trace": [
                {
                    "step": event.step,
                    "family": event.family,
                    "reward": event.reward,
                    "evidence_id": event.evidence_id,
                    "family_pulls": event.family_pulls,
                    "total_pulls": event.total_pulls,
                }
                for event in self._events
            ],
        }


def allocate_equal_budget(families: Sequence[str], total_budget: int) -> dict[str, int]:
    """Deterministic fixed-allocation control with exact budget conservation."""
    if isinstance(total_budget, bool) or not isinstance(total_budget, int):
        raise TypeError("total_budget must be an integer")
    if total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    names = tuple(sorted(set(families)))
    if not names:
        if total_budget:
            raise ValueError("cannot allocate positive budget to no families")
        return {}
    base, remainder = divmod(total_budget, len(names))
    result = {name: base + int(index < remainder) for index, name in enumerate(names)}
    assert sum(result.values()) == total_budget
    return result


def replay_ucb1(
    reward_streams: Mapping[str, Sequence[float]],
    total_budget: int,
    *,
    exploration_floor: int = 1,
    exploration_constant: float = math.sqrt(2.0),
) -> dict[str, Any]:
    """Replay deterministic pre-generated Gate-Dev reward streams for tests.

    This is a policy harness only. It is not a benchmark result and does not
    model proposer runtime or candidate evaluation cost.
    """
    allocator = UCB1Allocator(
        tuple(reward_streams), total_budget,
        exploration_floor=exploration_floor,
        exploration_constant=exploration_constant,
    )
    offsets = {family: 0 for family in reward_streams}
    while allocator.remaining_budget:
        family = allocator.next_family()
        index = offsets[family]
        if index >= len(reward_streams[family]):
            raise ValueError(f"reward stream exhausted for proposer family {family}")
        allocator.record_gate_dev_reward(
            reward_streams[family][index],
            f"gate-dev:{family}:{index}",
        )
        offsets[family] += 1
    return allocator.freeze()


if __name__ == "__main__":
    import json
    demo = replay_ucb1(
        {"STAT": (0.3, 0.4, 0.35), "RELATIONAL": (0.8, 0.75, 0.85),
         "RANDOM": (0.1, 0.2, 0.15)},
        total_budget=12,
    )
    print(json.dumps(demo, ensure_ascii=False, indent=2))
