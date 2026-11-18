"""Reproducible synthetic benchmark for multi-scale temporal reasoning.

The generator exposes ground-truth phase boundaries and event order separately
from sampled observations. It is a benchmark fixture, not a learned model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sin, pi, isfinite
from typing import Iterable


@dataclass(frozen=True)
class LatentPhase:
    label: str
    start: float
    end: float


@dataclass(frozen=True)
class Observation:
    time: float
    phase_label: str
    fast_signal: float
    slow_signal: float
    delayed_signal: float


@dataclass(frozen=True)
class TemporalBenchmark:
    phases: tuple[LatentPhase, ...]
    observations: tuple[Observation, ...]
    sample_interval: float
    duration: float
    missing_times: tuple[float, ...]


def _phase_at(phases: tuple[LatentPhase, ...], time: float) -> LatentPhase:
    for phase in phases:
        if phase.start <= time < phase.end:
            return phase
    return phases[-1]


def generate_temporal_benchmark(
    *,
    sample_interval: float = 1.0,
    duration: float = 30.0,
    phase_lengths: tuple[float, ...] = (10.0, 10.0, 10.0),
    missing_indices: Iterable[int] = (),
    delay: float = 2.0,
) -> TemporalBenchmark:
    """Generate one latent process sampled at a chosen rate.

    Phase labels encode a three-stage process. Fast/slow signals are deterministic
    functions of latent time; delayed_signal responds to the previous phase
    transition after the configured delay. Missingness removes observations only:
    it never changes the latent process or ground truth.
    """
    numeric = (sample_interval, duration, delay, *phase_lengths)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x)
           for x in numeric):
        raise ValueError("time parameters must be finite numeric values")
    if sample_interval <= 0 or duration <= 0 or delay < 0:
        raise ValueError("sample interval and duration must be positive; delay non-negative")
    if not phase_lengths or any(length <= 0 for length in phase_lengths):
        raise ValueError("phase lengths must be positive")
    if abs(sum(phase_lengths) - duration) > 1e-9:
        raise ValueError("phase lengths must sum to duration")

    labels = ("emergence", "transition", "stabilization")
    phases_list = []
    cursor = 0.0
    for index, length in enumerate(phase_lengths):
        label = labels[index] if index < len(labels) else f"phase-{index + 1}"
        phases_list.append(LatentPhase(label, cursor, cursor + length))
        cursor += length
    phases = tuple(phases_list)

    missing = set(missing_indices)
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in missing):
        raise ValueError("missing indices must be non-negative integers")

    observations = []
    count = int(duration / sample_interval)
    if any(index >= count for index in missing):
        raise ValueError("missing index is outside the sampled observation range")
    for index in range(count + 1):
        time = min(index * sample_interval, duration)
        if time >= duration or index in missing:
            continue
        phase = _phase_at(phases, time)
        fast = sin(2.0 * pi * time / 3.0)
        slow = time / duration
        prior_transition = max((p.start for p in phases[1:] if p.start <= time - delay), default=0.0)
        delayed = 1.0 if prior_transition > 0 else 0.0
        observations.append(Observation(time, phase.label, fast, slow, delayed))

    return TemporalBenchmark(phases, tuple(observations), float(sample_interval),
                             float(duration), tuple(sorted(missing)))


def event_order_accuracy(predicted_order: tuple[str, ...],
                         reference_order: tuple[str, ...]) -> float:
    """Pairwise order accuracy over shared unique event ids."""
    if len(set(predicted_order)) != len(predicted_order):
        raise ValueError("predicted event ids must be unique")
    if len(set(reference_order)) != len(reference_order):
        raise ValueError("reference event ids must be unique")
    predicted_positions = {item: i for i, item in enumerate(predicted_order)}
    shared = [item for item in reference_order if item in predicted_positions]
    if len(shared) < 2:
        return 1.0
    correct = total = 0
    for i, left in enumerate(shared):
        for right in shared[i + 1:]:
            total += 1
            correct += predicted_positions[left] < predicted_positions[right]
    return correct / total
