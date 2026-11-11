"""E10-C.3 bounded sequential detector for increases in prequential error rate.

The detector consumes only a time-ordered binary error signal. It does not
segment epochs, revise a learner, expand a hypothesis universe, or infer why
errors increased. It is a diagnostic alarm, not a drift oracle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DriftAlarm:
    index: int
    statistic: float
    threshold: float


class BernoulliCUSUM:
    """One-sided likelihood-ratio CUSUM for an increase p0 -> p1.

    p0 is the tolerated stationary error rate; p1 is the design alternative.
    A threshold crossing emits one alarm and resets the statistic. The caller
    owns cooldown policy and any subsequent epoch/adjudication decisions.
    """

    def __init__(self, *, baseline_rate: float = 0.05,
                 alternative_rate: float = 0.40,
                 threshold: float = 8.0) -> None:
        if not 0.0 < baseline_rate < alternative_rate < 1.0:
            raise ValueError("rates must satisfy 0 < baseline < alternative < 1")
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        self.baseline_rate = baseline_rate
        self.alternative_rate = alternative_rate
        self.threshold = threshold
        self.statistic = 0.0
        self.samples_seen = 0
        self.alarms: list[DriftAlarm] = []
        self._error_llr = math.log(alternative_rate / baseline_rate)
        self._ok_llr = math.log((1.0 - alternative_rate) /
                                (1.0 - baseline_rate))

    def update(self, error: bool) -> DriftAlarm | None:
        if not isinstance(error, bool):
            raise TypeError("error must be bool")
        self.samples_seen += 1
        increment = self._error_llr if error else self._ok_llr
        self.statistic = max(0.0, self.statistic + increment)
        if self.statistic >= self.threshold:
            alarm = DriftAlarm(self.samples_seen, self.statistic, self.threshold)
            self.alarms.append(alarm)
            self.statistic = 0.0
            return alarm
        return None

    def run(self, errors: Iterable[bool]) -> list[DriftAlarm]:
        emitted = []
        for error in errors:
            alarm = self.update(error)
            if alarm is not None:
                emitted.append(alarm)
        return emitted

    def snapshot(self) -> dict[str, float | int]:
        return {
            "samples_seen": self.samples_seen,
            "statistic": self.statistic,
            "threshold": self.threshold,
            "alarm_count": len(self.alarms),
        }
