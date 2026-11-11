"""N3-A bounded dirty-set scheduling prototype.

The scheduler traverses an explicit dependency index from event-touched IDs.
It returns partial work honestly when a node budget is exhausted; it does not
claim that the returned set is the complete graph impact in that case.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class ScheduleStatus(str, Enum):
    COMPLETE = "COMPLETE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


@dataclass(frozen=True)
class DirtySetResult:
    affected_ids: tuple[str, ...]
    frontier_ids: tuple[str, ...]
    scanned_edges: int
    max_depth_reached: int
    status: ScheduleStatus


def build_dependency_index(
    dependencies: Iterable[tuple[str, str]],
) -> dict[str, tuple[str, ...]]:
    """Build a deterministic forward index: changed source -> dependent IDs."""
    index: dict[str, set[str]] = {}
    for source, dependent in dependencies:
        if not source.strip() or not dependent.strip():
            raise ValueError("dependency IDs must be non-empty")
        if source == dependent:
            raise ValueError("self-dependencies are not allowed")
        index.setdefault(source, set()).add(dependent)
    return {key: tuple(sorted(values)) for key, values in index.items()}


def schedule_dirty_set(
    event_touched_ids: Iterable[str],
    dependency_index: Mapping[str, Iterable[str]],
    *,
    max_hops: int = 2,
    max_nodes: int = 256,
) -> DirtySetResult:
    """Return touched IDs and their bounded transitive dependents.

    max_nodes limits the returned set, including the initial touched IDs.
    frontier_ids identifies queued IDs omitted because the node budget ran out.
    A COMPLETE result means traversal completed within max_hops, not that the
    dependency index itself is globally complete or factually correct.
    """
    if max_hops < 0:
        raise ValueError("max_hops must be >= 0")
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")

    raw_roots = tuple(event_touched_ids)
    if any(not isinstance(node_id, str) or not node_id.strip() for node_id in raw_roots):
        raise ValueError("event-touched IDs must be non-empty strings")
    roots = sorted(set(raw_roots))

    queue = deque((node_id, 0) for node_id in roots)
    queued = set(roots)
    affected: list[str] = []
    visited: set[str] = set()
    scanned_edges = 0
    max_depth_reached = 0
    frontier: list[str] = []

    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited:
            continue
        if len(affected) >= max_nodes:
            frontier.append(node_id)
            frontier.extend(item for item, _ in queue)
            break

        visited.add(node_id)
        affected.append(node_id)
        max_depth_reached = max(max_depth_reached, depth)

        if depth >= max_hops:
            continue

        neighbors = sorted(set(dependency_index.get(node_id, ())))
        for neighbor in neighbors:
            if not isinstance(neighbor, str) or not neighbor.strip():
                raise ValueError("dependency index contains an empty/non-string ID")
            scanned_edges += 1
            if neighbor not in queued and neighbor not in visited:
                queued.add(neighbor)
                queue.append((neighbor, depth + 1))

    return DirtySetResult(
        affected_ids=tuple(affected),
        frontier_ids=tuple(dict.fromkeys(frontier)),
        scanned_edges=scanned_edges,
        max_depth_reached=max_depth_reached,
        status=(
            ScheduleStatus.BUDGET_EXHAUSTED
            if frontier else ScheduleStatus.COMPLETE
        ),
    )
