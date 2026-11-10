"""E02-K: bounded sequential evidence for adaptive relation lifecycle decisions.

This controller is deliberately separated from candidate discovery. The
upstream evaluator supplies paired candidate-vs-baseline discordant counts
and current-relation invalidity evidence for each independent window.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceObservation:
    candidate_signature: tuple[tuple[int, ...], int] | None
    candidate_wins: int = 0
    candidate_losses: int = 0
    current_invalid_evidence: float = 0.0

    def __post_init__(self) -> None:
        if self.candidate_wins < 0 or self.candidate_losses < 0:
            raise ValueError("paired counts cannot be negative")


class AdaptiveEvidenceController:
    """Sequential evidence accumulator with a two-window anti-shock floor."""

    def __init__(
        self,
        *,
        alpha: float = 0.05,
        beta: float = 0.10,
        alternative_win_probability: float = 0.65,
        per_window_cap: float = 1.5,
        min_support_windows: int = 2,
    ) -> None:
        if not 0 < alpha < 1 or not 0 < beta < 1:
            raise ValueError("alpha and beta must be in (0, 1)")
        if not 0.5 < alternative_win_probability < 1:
            raise ValueError("alternative probability must be in (0.5, 1)")
        if per_window_cap <= 0 or min_support_windows < 2:
            raise ValueError("invalid cap or support-window floor")
        self.threshold = math.log((1 - beta) / alpha)
        self.alternative_win_probability = alternative_win_probability
        self.per_window_cap = per_window_cap
        self.min_support_windows = min_support_windows

        self.current_signature: tuple[tuple[int, ...], int] | None = None
        self.current_status = "ABSENT"
        self.ever_created = False

        self.pending_signature: tuple[tuple[int, ...], int] | None = None
        self.pending_score = 0.0
        self.pending_support_windows = 0

        self.invalid_score = 0.0
        self.invalid_support_windows = 0
        self.version = 0
        self.events: list[dict] = []

    def _clip(self, value: float) -> float:
        return max(-self.per_window_cap, min(self.per_window_cap, value))

    def _candidate_llr(self, wins: int, losses: int) -> float:
        p1 = self.alternative_win_probability
        return (
            wins * math.log(p1 / 0.5)
            + losses * math.log((1 - p1) / 0.5)
        )

    def _reset_pending(self) -> None:
        self.pending_signature = None
        self.pending_score = 0.0
        self.pending_support_windows = 0

    def _observe_candidate(self, observation: EvidenceObservation) -> float:
        signature = observation.candidate_signature
        if signature is None:
            self._reset_pending()
            return 0.0
        if signature != self.pending_signature:
            self.pending_signature = signature
            self.pending_score = 0.0
            self.pending_support_windows = 0
        evidence = self._clip(
            self._candidate_llr(
                observation.candidate_wins, observation.candidate_losses
            )
        )
        self.pending_score = max(0.0, self.pending_score + evidence)
        if evidence > 0:
            self.pending_support_windows += 1
        elif evidence < 0:
            self.pending_support_windows = max(0, self.pending_support_windows - 1)
        return evidence

    def _observe_current_health(self, evidence: float) -> float:
        clipped = self._clip(evidence)
        self.invalid_score = max(0.0, self.invalid_score + clipped)
        if clipped > 0:
            self.invalid_support_windows += 1
        elif clipped < 0:
            self.invalid_support_windows = 0
        return clipped

    def observe(self, observation: EvidenceObservation, *, window: int) -> str:
        signature = observation.candidate_signature

        # First discovery is a bootstrap event. After a retirement, resurrection
        # must pass the same accumulated evidence threshold as a reconfiguration.
        if self.current_signature is None and not self.ever_created:
            if signature is None:
                action = "NO_RELATION"
            else:
                self.current_signature = signature
                self.current_status = "ACTIVE"
                self.ever_created = True
                self.version += 1
                action = "CREATE"
            self.events.append(self._event(window, action, 0.0, 0.0))
            return action

        if self.current_signature is not None and signature == self.current_signature:
            self._reset_pending()
            self.invalid_score = 0.0
            self.invalid_support_windows = 0
            self.current_status = "ACTIVE"
            action = "KEEP"
            self.events.append(self._event(window, action, 0.0, 0.0))
            return action

        candidate_evidence = self._observe_candidate(observation)
        health_evidence = 0.0
        if self.current_signature is not None:
            health_evidence = self._observe_current_health(
                observation.current_invalid_evidence
            )
            self.current_status = "DEGRADED" if self.invalid_score > 0 else "ACTIVE"

        candidate_confirmed = (
            signature is not None
            and self.pending_signature == signature
            and self.pending_score >= self.threshold
            and self.pending_support_windows >= self.min_support_windows
        )
        current_retired = (
            self.current_signature is not None
            and self.invalid_score >= self.threshold
            and self.invalid_support_windows >= self.min_support_windows
        )

        if candidate_confirmed:
            old = self.current_signature
            self.current_signature = signature
            self.current_status = "ACTIVE"
            self.invalid_score = 0.0
            self.invalid_support_windows = 0
            self.version += 1
            self._reset_pending()
            action = "RECONFIGURE" if old is not None else "CREATE"
        elif current_retired:
            old = self.current_signature
            self.current_signature = None
            self.current_status = "ABSENT"
            self.invalid_score = 0.0
            self.invalid_support_windows = 0
            action = "RETIRE"
            self.events.append(self._event(
                window, action, candidate_evidence, health_evidence, old=old
            ))
            return action
        elif self.current_signature is None:
            action = "HOLD_PENDING" if signature is not None else "NO_RELATION"
        elif self.invalid_score > 0:
            action = "HOLD_PENDING" if signature is not None else "DEGRADE"
        else:
            action = "HOLD_PENDING" if signature is not None else "KEEP"

        self.events.append(self._event(
            window, action, candidate_evidence, health_evidence
        ))
        return action

    def _event(
        self,
        window: int,
        action: str,
        candidate_evidence: float,
        health_evidence: float,
        *,
        old: tuple[tuple[int, ...], int] | None = None,
    ) -> dict:
        event = {
            "window": window,
            "action": action,
            "current_status": self.current_status,
            "version": self.version,
            "candidate_score": round(self.pending_score, 6),
            "candidate_support_windows": self.pending_support_windows,
            "current_invalid_score": round(self.invalid_score, 6),
            "current_invalid_support_windows": self.invalid_support_windows,
            "candidate_evidence": round(candidate_evidence, 6),
            "health_evidence": round(health_evidence, 6),
        }
        if old is not None:
            event["from"] = old
        return event
