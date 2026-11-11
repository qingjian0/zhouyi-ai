"""Label-free E09 inbox for evaluator-authorized challenge signals.

This queue is deliberately not a learner update API: accepting a challenge
must never append an Example, call PrequentialRunner.reveal(), or revise a model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping


CHALLENGE_KINDS = {
    "RECONSIDER", "INSUFFICIENT_EVIDENCE", "BOUNDARY_CASE", "INVARIANCE_CHECK",
}
CHALLENGE_FIELDS = {"challenge_id", "observation_id", "challenge_kind"}


class E09ChallengeError(ValueError):
    """Invalid or conflicting label-free challenge signal."""


@dataclass(frozen=True)
class ChallengeSignal:
    challenge_id: str
    observation_id: str
    challenge_kind: str


class E09ChallengeInbox:
    """Accepts only safe challenge descriptors for already committed observations."""

    def __init__(self, committed_observation_ids: Iterable[str]) -> None:
        known = set(committed_observation_ids)
        if any(not isinstance(value, str) or not value.strip() for value in known):
            raise E09ChallengeError("committed observation IDs must be non-empty strings")
        self._known_observations = known
        self._signals: dict[str, ChallengeSignal] = {}
        self._acknowledged: set[str] = set()

    def accept(self, payload: Mapping[str, object]) -> bool:
        if not isinstance(payload, Mapping) or set(payload) != CHALLENGE_FIELDS:
            raise E09ChallengeError("challenge payload must contain only the three allowlisted fields")
        challenge_id = payload["challenge_id"]
        observation_id = payload["observation_id"]
        challenge_kind = payload["challenge_kind"]
        for name, value in (
            ("challenge_id", challenge_id),
            ("observation_id", observation_id),
            ("challenge_kind", challenge_kind),
        ):
            if not isinstance(value, str) or not value.strip():
                raise E09ChallengeError(f"{name} must be a non-empty string")
        if challenge_kind not in CHALLENGE_KINDS:
            raise E09ChallengeError("unsupported challenge_kind")
        if observation_id not in self._known_observations:
            raise E09ChallengeError("challenge must reference an observation already committed by E09")
        signal = ChallengeSignal(challenge_id, observation_id, challenge_kind)
        previous = self._signals.get(challenge_id)
        if previous is not None:
            if previous != signal:
                raise E09ChallengeError("challenge_id was reused with different content")
            return False
        self._signals[challenge_id] = signal
        return True

    def pending(self) -> tuple[ChallengeSignal, ...]:
        return tuple(signal for key, signal in self._signals.items() if key not in self._acknowledged)

    def acknowledge(self, challenge_id: str) -> None:
        if challenge_id not in self._signals:
            raise E09ChallengeError("cannot acknowledge an unknown challenge")
        self._acknowledged.add(challenge_id)

    def snapshot(self) -> dict:
        return {
            "accepted": [asdict(signal) for signal in self._signals.values()],
            "acknowledged_ids": sorted(self._acknowledged),
            "pending_ids": [key for key in self._signals if key not in self._acknowledged],
        }
