"""Evidence-bounded MERGE / SPLIT / UNRESOLVED decisions.

This module consumes learner-visible paired challenge records only. It must
not receive evaluator state IDs, latent generator labels, or oracle partitions.
A MERGE is scoped to the tested action set, evidence horizon, and repetitions;
it is not a proof of global or infinite-horizon equivalence.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Hashable, Iterable


class PartitionDecision(str, Enum):
    MERGE = "MERGE"
    SPLIT = "SPLIT"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class PairChallengeEvidence:
    """One paired challenge under the same action and protocol conditions."""

    action: Hashable
    trial_id: Hashable
    left_outcome: Hashable
    right_outcome: Hashable
    left_successor_signature: Hashable
    right_successor_signature: Hashable


@dataclass(frozen=True)
class PairDecision:
    decision: PartitionDecision
    covered_actions: tuple[Hashable, ...]
    missing_actions: tuple[Hashable, ...]
    repetitions_by_action: tuple[tuple[Hashable, int], ...]
    counterexample_trials: tuple[Hashable, ...]
    scope: str = "observed_actions_and_successor_signatures_only"


def decide_pair_partition(
    actions: Iterable[Hashable],
    evidence: Iterable[PairChallengeEvidence],
    *,
    min_repetitions_per_action: int = 1,
) -> PairDecision:
    """Conservatively adjudicate a proposed pair from paired observations.

    SPLIT: at least one paired challenge differs in immediate outcome or
    successor signature.
    MERGE: every declared action has the required number of paired trials and
    every observed pair matches on both fields.
    UNRESOLVED: otherwise.

    Repeated trial IDs are rejected globally to prevent accidental double
    counting. This simple exact-match protocol is for deterministic XRA-P1;
    stochastic/noisy evidence requires a separately specified statistical
    decision procedure.
    """
    action_values = tuple(actions)
    records = tuple(evidence)
    if not action_values:
        raise ValueError("actions must be non-empty")
    try:
        if len(set(action_values)) != len(action_values):
            raise ValueError("actions must be unique")
        action_set = set(action_values)
        trial_ids = [record.trial_id for record in records]
        if len(set(trial_ids)) != len(trial_ids):
            raise ValueError("trial_id values must be globally unique")
        for record in records:
            if record.action not in action_set:
                raise ValueError("evidence contains an undeclared action")
            for value in (
                record.left_outcome,
                record.right_outcome,
                record.left_successor_signature,
                record.right_successor_signature,
            ):
                hash(value)
    except TypeError as exc:
        raise ValueError("actions, trial IDs, and evidence values must be hashable") from exc

    if min_repetitions_per_action < 1:
        raise ValueError("min_repetitions_per_action must be >= 1")

    counts = Counter(record.action for record in records)
    covered = tuple(action for action in action_values if counts[action] > 0)
    missing = tuple(
        action for action in action_values
        if counts[action] < min_repetitions_per_action
    )
    counterexamples = tuple(
        record.trial_id for record in records
        if (
            record.left_outcome != record.right_outcome
            or record.left_successor_signature != record.right_successor_signature
        )
    )

    if counterexamples:
        decision = PartitionDecision.SPLIT
    elif not missing:
        decision = PartitionDecision.MERGE
    else:
        decision = PartitionDecision.UNRESOLVED

    return PairDecision(
        decision=decision,
        covered_actions=covered,
        missing_actions=missing,
        repetitions_by_action=tuple(
            (action, counts[action]) for action in action_values
        ),
        counterexample_trials=counterexamples,
    )
