"""E12-A3-M1: stateful UCB1 budget allocator.

The allocator sees only per-batch scalar rewards supplied by the experiment
harness. It has no access to observations, labels, Gate-Final, or Locked Test.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AllocationEvent:
    family: str
    slots: int
    reward: float
    family_batches_after: int
    remaining_budget_after: int


class UCB1Allocator:
    def __init__(
        self,
        families: tuple[str, ...] | list[str],
        total_budget: int,
        batch_size: int = 4,
        exploration_floor: int = 1,
        exploration_constant: float = math.sqrt(2.0),
    ) -> None:
        if any(not isinstance(name, str) or not name for name in families):
            raise ValueError("family IDs must be non-empty strings")
        names = tuple(sorted(set(families)))
        if not names:
            raise ValueError("at least one family is required")
        if isinstance(total_budget, bool) or not isinstance(total_budget, int) or total_budget < 0:
            raise ValueError("total_budget must be a non-negative integer")
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if isinstance(exploration_floor, bool) or not isinstance(exploration_floor, int) or exploration_floor < 0:
            raise ValueError("exploration_floor must be a non-negative integer")
        if not math.isfinite(exploration_constant) or exploration_constant < 0:
            raise ValueError("exploration_constant must be finite and non-negative")
        if exploration_floor * len(names) * batch_size > total_budget:
            raise ValueError("budget cannot satisfy the requested exploration floor")

        self.families = names
        self.total_budget = total_budget
        self.remaining_budget = total_budget
        self.batch_size = batch_size
        self.exploration_floor = exploration_floor
        self.exploration_constant = exploration_constant
        self._pulls = {name: 0 for name in names}
        self._reward_sums = {name: 0.0 for name in names}
        self._allocations = {name: 0 for name in names}
        self._pending_family: str | None = None
        self._pending_slots = 0
        self.events: list[AllocationEvent] = []

    @property
    def allocations(self) -> dict[str, int]:
        return dict(self._allocations)

    @property
    def pulls(self) -> dict[str, int]:
        return dict(self._pulls)

    @property
    def pending(self) -> tuple[str, int] | None:
        if self._pending_family is None:
            return None
        return self._pending_family, self._pending_slots

    def choose_next_family(self) -> str | None:
        if self.remaining_budget == 0:
            return None
        if self._pending_family is not None:
            raise RuntimeError("observe the pending batch before choosing again")

        under_floor = [
            name for name in self.families
            if self._pulls[name] < self.exploration_floor
        ]
        if under_floor:
            # Stable round-robin among families below the floor.
            family = min(under_floor, key=lambda name: (self._pulls[name], name))
        else:
            unpulled = [name for name in self.families if self._pulls[name] == 0]
            if unpulled:
                family = unpulled[0]
            else:
                total_pulls = sum(self._pulls.values())
                log_total = math.log(max(2, total_pulls + 1))
                scores = {}
                for name in self.families:
                    mean_reward = self._reward_sums[name] / self._pulls[name]
                    bonus = self.exploration_constant * math.sqrt(
                        log_total / self._pulls[name]
                    )
                    scores[name] = mean_reward + bonus
                family = min(
                    self.families,
                    key=lambda name: (-scores[name], name),
                )

        self._pending_family = family
        self._pending_slots = min(self.batch_size, self.remaining_budget)
        return family

    def observe_batch(self, family: str, reward: float, used_slots: int | None = None) -> AllocationEvent:
        if self._pending_family is None:
            raise RuntimeError("no pending allocation batch")
        if family != self._pending_family:
            raise ValueError("reward family does not match pending allocation")
        if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not math.isfinite(reward):
            raise ValueError("reward must be a finite number")
        slots = self._pending_slots if used_slots is None else used_slots
        if isinstance(slots, bool) or not isinstance(slots, int):
            raise TypeError("used_slots must be an integer")
        if slots < 1 or slots > self._pending_slots:
            raise ValueError("used_slots must be within the pending batch size")

        self._pulls[family] += 1
        self._reward_sums[family] += float(reward)
        self._allocations[family] += slots
        self.remaining_budget -= slots
        event = AllocationEvent(
            family=family,
            slots=slots,
            reward=float(reward),
            family_batches_after=self._pulls[family],
            remaining_budget_after=self.remaining_budget,
        )
        self.events.append(event)
        self._pending_family = None
        self._pending_slots = 0
        return event

    def allocation_trace(self) -> tuple[AllocationEvent, ...]:
        return tuple(self.events)
