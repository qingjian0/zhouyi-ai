"""Explicit multi-scale temporal primitives.

This is a data/validation baseline. It does not infer phases, resample clocks,
discover causal links, or compare uncalibrated time units.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class TimeScale:
    scale_id: str
    parent_scale_id: str | None = None
    description: str = ""

@dataclass(frozen=True)
class TemporalEvent:
    event_id: str
    scale_id: str
    clock_id: str
    start: float
    end: float
    observed_at: float
    evidence_refs: tuple[str, ...]
    parent_event_id: str | None = None

@dataclass(frozen=True)
class TemporalRelation:
    relation: str
    comparable: bool
    reason: str

@dataclass(frozen=True)
class MultiScaleTimeline:
    scales: Mapping[str, TimeScale]
    events: tuple[TemporalEvent, ...]

    def validate(self) -> None:
        if not isinstance(self.scales, Mapping) or not self.scales:
            raise ValueError("at least one time scale is required")
        for key, scale in self.scales.items():
            if not isinstance(scale, TimeScale) or key != scale.scale_id or not key:
                raise ValueError("scale keys must match non-empty scale ids")
            if scale.parent_scale_id is not None and scale.parent_scale_id not in self.scales:
                raise ValueError(f"unknown parent scale: {scale.parent_scale_id}")
        for scale_id in self.scales:
            seen = set()
            current = scale_id
            while current is not None:
                if current in seen:
                    raise ValueError("time-scale hierarchy contains a cycle")
                seen.add(current)
                current = self.scales[current].parent_scale_id

        if not isinstance(self.events, tuple):
            raise ValueError("events must be a tuple")
        by_id = {}
        for event in self.events:
            if not isinstance(event, TemporalEvent):
                raise ValueError("events must contain TemporalEvent values")
            if not all(isinstance(x, str) and x.strip() for x in
                       (event.event_id, event.scale_id, event.clock_id)):
                raise ValueError("event id, scale id and clock id are required")
            if event.event_id in by_id:
                raise ValueError("event ids must be unique")
            if event.scale_id not in self.scales:
                raise ValueError(f"unknown event scale: {event.scale_id}")
            if any(isinstance(x, bool) or not isinstance(x, (int, float))
                   for x in (event.start, event.end, event.observed_at)):
                raise ValueError("event times must be numeric")
            if event.start > event.end:
                raise ValueError("event start must not exceed end")
            if not isinstance(event.evidence_refs, tuple) or not event.evidence_refs:
                raise ValueError("each event requires evidence references")
            if any(not isinstance(ref, str) or not ref.strip()
                   for ref in event.evidence_refs):
                raise ValueError("evidence references must be non-empty strings")
            by_id[event.event_id] = event

        for event in self.events:
            if event.parent_event_id is None:
                continue
            parent = by_id.get(event.parent_event_id)
            if parent is None:
                raise ValueError(f"unknown parent event: {event.parent_event_id}")
            if parent.event_id == event.event_id:
                raise ValueError("event cannot parent itself")
            # Parent event must be on an ancestor scale, not the same or a child scale.
            current = self.scales[event.scale_id].parent_scale_id
            ancestors = set()
            while current is not None:
                ancestors.add(current)
                current = self.scales[current].parent_scale_id
            if parent.scale_id not in ancestors:
                raise ValueError("parent event must belong to an ancestor time scale")
            if parent.clock_id != event.clock_id:
                raise ValueError("parent-child containment needs a shared calibrated clock")
            if parent.start > event.start or parent.end < event.end:
                raise ValueError("parent event interval must contain child event interval")

def compare_intervals(left: TemporalEvent, right: TemporalEvent) -> TemporalRelation:
    """Return an Allen-style interval relation only for a shared clock."""
    if left.clock_id != right.clock_id:
        return TemporalRelation("INCOMPARABLE", False,
            "different clocks require an explicit calibration transform")
    a, b, c, d = left.start, left.end, right.start, right.end
    if a == c and b == d: relation = "EQUAL"
    elif a == c and b < d: relation = "STARTS"
    elif a == c and b > d: relation = "STARTED_BY"
    elif b == d and a > c: relation = "FINISHES"
    elif b == d and a < c: relation = "FINISHED_BY"
    elif a < c and b > d: relation = "CONTAINS"
    elif a > c and b < d: relation = "DURING"
    elif b < c: relation = "BEFORE"
    elif b == c: relation = "MEETS"
    elif d < a: relation = "AFTER"
    elif d == a: relation = "MET_BY"
    else: relation = "OVERLAPS"
    return TemporalRelation(relation, True, "shared clock; interval relation is comparable")
