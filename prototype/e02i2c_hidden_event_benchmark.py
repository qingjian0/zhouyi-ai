"""E02-I2-C hidden-event benchmark, development phase.

Ground-truth event labels live only in evaluator-owned Episode objects. The
adjudicator receives the observable identity snapshot, opportunities and
EvidencePacket values; it is never passed the hidden event label.

This development runner intentionally supports TRAIN and GATE only. It has no
locked-test mode: a separate frozen runner/protocol will be added only after
the decision rules and thresholds are frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Callable

from prototype.e02i2c_adjudication import (
    EvidencePacket,
    EvidencePolarity,
    EventType,
    IdentitySnapshot,
    MissingReason,
    ObservationOpportunity,
    adjudicate_event,
)


@dataclass(frozen=True)
class ObservationView:
    """Only the observable inputs available to an event policy."""

    identity: IdentitySnapshot | None
    candidate_signature: str | None
    opportunities: tuple[ObservationOpportunity, ...]
    evidence: tuple[EvidencePacket, ...]


@dataclass(frozen=True)
class Episode:
    """Evaluator-owned wrapper; truth is not part of ObservationView."""

    episode_id: str
    truth: EventType
    observation: ObservationView


SUPPORTED_EVENTS = (
    EventType.KEEP,
    EventType.MODIFY,
    EventType.CREATE,
    EventType.ABSTAIN,
    EventType.SUSPEND,
    EventType.REACTIVATE,
    EventType.REACTIVATE_MODIFY,
    EventType.RETIRE,
)


def _opportunity(window: int, *, coverage: float = 1.0,
                 observed: int = 10,
                 reason: MissingReason | None = None) -> ObservationOpportunity:
    return ObservationOpportunity(
        window=window, environment="env-a", expected_samples=10,
        observed_samples=observed, coverage=coverage, missing_reason=reason,
    )


def _packet(seed: int, event: str, window: int, polarity: EvidencePolarity,
            signature: str | None, *, source: str = "v1",
            split: str, ordinal: int = 0) -> EvidencePacket:
    """Create opaque provenance IDs; event labels never enter observable IDs."""
    del event  # Event truth is evaluator-side and must not shape observable metadata.
    material = f"{split}|{seed}|{window}|{ordinal}".encode("utf-8")
    token = hashlib.blake2b(material, digest_size=12).hexdigest()
    return EvidencePacket(
        evidence_id=f"ev-{token}",
        sample_id=f"sample-{token}",
        window=window,
        environment="env-a",
        split=split,
        polarity=polarity,
        source_version_id=source,
        candidate_signature=signature,
        raw_observation_ref=f"synthetic://observation/{token}",
    )


def build_episode(event: EventType, seed: int, *, split: str) -> Episode:
    """Build one observable episode and keep its truth evaluator-side."""
    if split not in {"train", "gate"}:
        raise ValueError("development benchmark accepts train or gate only")
    rng = random.Random(seed)
    identity = IdentitySnapshot("r1", "ACTIVE", "v1", "a&b")
    opportunities: tuple[ObservationOpportunity, ...]
    evidence: tuple[EvidencePacket, ...]
    candidate: str | None = "a&b"

    if event == EventType.KEEP:
        opportunities = (_opportunity(0),)
        evidence = (_packet(seed, "keep", 0, EvidencePolarity.SUPPORTS,
                            "a&b", split=split),)
    elif event == EventType.MODIFY:
        candidate = "a^b"
        opportunities = (_opportunity(0), _opportunity(1))
        evidence = tuple(_packet(seed, "modify", w, EvidencePolarity.SUPPORTS,
                                 candidate, source="v1", split=split)
                         for w in (0, 1))
    elif event == EventType.CREATE:
        identity = None
        candidate = "c&d"
        opportunities = (_opportunity(0), _opportunity(1))
        evidence = tuple(_packet(seed, "create", w, EvidencePolarity.SUPPORTS,
                                 candidate, source=None, split=split)
                         for w in (0, 1))
    elif event == EventType.ABSTAIN:
        candidate = "a^b"
        mode = seed % 4
        if mode == 0:
            # No prior identity and only one support window: abstention is not CREATE.
            identity = None
            opportunities = (_opportunity(0),)
            evidence = (_packet(seed, "unconfirmed-new", 0, EvidencePolarity.SUPPORTS,
                                candidate, source=None, split=split),)
        elif mode == 1:
            # One changed-rule window with no identity-continuity proof.
            opportunities = (_opportunity(0),)
            evidence = (_packet(seed, "ambiguous", 0, EvidencePolarity.SUPPORTS,
                                candidate, source="unlinked-version", split=split),)
        elif mode == 2:
            # Two nominal windows, but neither had sufficient sampling opportunity.
            opportunities = (
                _opportunity(0, coverage=0.1, observed=1, reason=MissingReason.NO_EXPOSURE),
                _opportunity(1, coverage=0.1, observed=1, reason=MissingReason.NO_EXPOSURE),
            )
            evidence = tuple(_packet(seed, "undersampled", w, EvidencePolarity.ABSENCE,
                                     None, split=split) for w in (0, 1))
        else:
            # Simultaneous positive and negative observations must not be averaged.
            opportunities = (_opportunity(0),)
            evidence = (
                _packet(seed, "conflict-positive", 0, EvidencePolarity.SUPPORTS,
                        candidate, source="v1", split=split, ordinal=0),
                _packet(seed, "conflict-negative", 0, EvidencePolarity.CONTRADICTS,
                        None, source="v1", split=split, ordinal=1),
            )
    elif event == EventType.SUSPEND:
        opportunities = (_opportunity(0), _opportunity(1))
        evidence = tuple(_packet(seed, "absence", w, EvidencePolarity.ABSENCE,
                                 None, split=split) for w in (0, 1))
    elif event == EventType.REACTIVATE:
        identity = IdentitySnapshot("r1", "SUSPENDED", "v1", "a&b")
        opportunities = (_opportunity(2), _opportunity(3))
        evidence = tuple(_packet(seed, "reactivate", w, EvidencePolarity.SUPPORTS,
                                 "a&b", source="v1", split=split) for w in (2, 3))
    elif event == EventType.REACTIVATE_MODIFY:
        identity = IdentitySnapshot("r1", "SUSPENDED", "v1", "a&b")
        candidate = "a|b"
        opportunities = (_opportunity(2), _opportunity(3))
        evidence = tuple(_packet(seed, "reactivate-modify", w,
                                 EvidencePolarity.SUPPORTS, candidate,
                                 source="v1", split=split) for w in (2, 3))
    elif event == EventType.RETIRE:
        identity = IdentitySnapshot("r1", "SUSPENDED", "v1", "a&b")
        opportunities = (_opportunity(2), _opportunity(3))
        evidence = tuple(_packet(seed, "contradiction", w,
                                 EvidencePolarity.CONTRADICTS, None,
                                 source="v1", split=split) for w in (2, 3))
    else:
        raise ValueError(f"unsupported event for this benchmark: {event}")

    # Randomize only presentation order, never the underlying episode.
    evidence = tuple(rng.sample(list(evidence), len(evidence)))
    return Episode(
        episode_id=f"{split}-{event.value}-{seed}",
        truth=event,
        observation=ObservationView(
            identity=identity,
            candidate_signature=candidate,
            opportunities=opportunities,
            evidence=evidence,
        ),
    )


def _similarity_only(episode: ObservationView) -> EventType:
    """Intentionally weak baseline: force a decision from one-step similarity."""
    identity = episode.identity
    support = [x for x in episode.evidence if x.polarity == EvidencePolarity.SUPPORTS]
    if identity is None:
        return EventType.CREATE
    if identity.status == "SUSPENDED":
        if support:
            return (EventType.REACTIVATE_MODIFY
                    if any(x.candidate_signature != identity.signature for x in support)
                    else EventType.REACTIVATE)
        if any(x.polarity == EvidencePolarity.CONTRADICTS for x in episode.evidence):
            return EventType.RETIRE
        return EventType.ABSTAIN
    if support:
        return (EventType.MODIFY
                if any(x.candidate_signature != identity.signature for x in support)
                else EventType.KEEP)
    if any(x.polarity == EvidencePolarity.ABSENCE for x in episode.evidence):
        return EventType.SUSPEND
    return EventType.ABSTAIN


def _single_window(episode: ObservationView) -> EventType:
    """Weak recency baseline: decide from the latest window only."""
    latest = max((x.window for x in episode.evidence), default=-1)
    observed = [x for x in episode.evidence if x.window == latest]
    if not observed:
        return EventType.ABSTAIN
    identity = episode.identity
    if identity is None:
        return EventType.CREATE if any(x.polarity == EvidencePolarity.SUPPORTS for x in observed) else EventType.ABSTAIN
    support = next((x for x in observed if x.polarity == EvidencePolarity.SUPPORTS), None)
    if support:
        if identity.status == "SUSPENDED":
            return EventType.REACTIVATE_MODIFY if support.candidate_signature != identity.signature else EventType.REACTIVATE
        return EventType.MODIFY if support.candidate_signature != identity.signature else EventType.KEEP
    if any(x.polarity == EvidencePolarity.ABSENCE for x in observed):
        return EventType.SUSPEND
    if any(x.polarity == EvidencePolarity.CONTRADICTS for x in observed):
        return EventType.RETIRE if identity.status == "SUSPENDED" else EventType.ABSTAIN
    return EventType.ABSTAIN


def _adjudicator(episode: ObservationView) -> EventType:
    return adjudicate_event(
        episode.identity,
        episode.opportunities,
        episode.evidence,
        candidate_signature=episode.candidate_signature,
    ).event


POLICIES: dict[str, Callable[[ObservationView], EventType]] = {
    "similarity_only": _similarity_only,
    "single_window": _single_window,
    "evidence_gated": _adjudicator,
}


def _metrics(rows: list[tuple[EventType, EventType]]) -> dict:
    labels = tuple(EventType)
    per_class: dict[str, dict[str, float | int]] = {}
    f1s = []
    for label in labels:
        tp = sum(truth == label and pred == label for truth, pred in rows)
        fp = sum(truth != label and pred == label for truth, pred in rows)
        fn = sum(truth == label and pred != label for truth, pred in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if tp + fp + fn:
            f1s.append(f1)
        per_class[label.value] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(truth == label for truth, _ in rows),
        }
    decided = [(truth, pred) for truth, pred in rows if pred != EventType.ABSTAIN]
    errors = sum(truth != pred for truth, pred in decided)
    return {
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "accuracy": round(sum(t == p for t, p in rows) / len(rows), 4) if rows else 0.0,
        "coverage": round(len(decided) / len(rows), 4) if rows else 0.0,
        "selective_risk": round(errors / len(decided), 4) if decided else 0.0,
        "false_create": sum(t != EventType.CREATE and p == EventType.CREATE for t, p in rows),
        "false_modify": sum(t != EventType.MODIFY and p == EventType.MODIFY for t, p in rows),
        "false_suspend": sum(t != EventType.SUSPEND and p == EventType.SUSPEND for t, p in rows),
        "false_retire": sum(t != EventType.RETIRE and p == EventType.RETIRE for t, p in rows),
        "per_class": per_class,
    }


def _build_episodes(*, seeds: int, start_seed: int, split: str) -> list[Episode]:
    """Build episodes with globally unique, event-unlinked seed assignments."""
    episodes: list[Episode] = []
    for offset in range(seeds):
        episode_seeds = list(range(
            start_seed + offset * len(SUPPORTED_EVENTS),
            start_seed + (offset + 1) * len(SUPPORTED_EVENTS),
        ))
        random.Random(f"{split}:{start_seed}:{offset}").shuffle(episode_seeds)
        episodes.extend(
            build_episode(event, episode_seed, split=split)
            for event, episode_seed in zip(SUPPORTED_EVENTS, episode_seeds)
        )
    return episodes


def run_benchmark(*, seeds: int = 20, start_seed: int = 1000,
                  split: str = "train") -> dict:
    if seeds < 1 or start_seed < 0:
        raise ValueError("seeds must be positive and start_seed non-negative")
    if split not in {"train", "gate"}:
        raise ValueError("locked Test is deliberately unavailable in the development runner")
    episodes = _build_episodes(seeds=seeds, start_seed=start_seed, split=split)
    results = {}
    for name, policy in POLICIES.items():
        rows = [(episode.truth, policy(episode.observation)) for episode in episodes]
        results[name] = _metrics(rows)
    return {
        "benchmark": "E02-I2-C-hidden-event-development",
        "split": split,
        "seeds_per_event": seeds,
        "episodes": len(episodes),
        "event_classes": [event.value for event in SUPPORTED_EVENTS],
        "truth_is_evaluator_only": True,
        "locked_test_available": False,
        "policies": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1000)
    parser.add_argument("--split", choices=("train", "gate"), default="train")
    args = parser.parse_args()
    print(json.dumps(run_benchmark(
        seeds=args.seeds, start_seed=args.start_seed, split=args.split,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
