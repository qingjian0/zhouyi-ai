"""N0.12: active identification over a finite set of operator hypotheses.

N0.11 proposes executable programs. This module does not synthesize programs;
it chooses informative experiments that distinguish an existing version space,
then updates that version space from observed outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Protocol, Sequence


State = tuple[float, ...]


class PredictiveProgram(Protocol):
    def apply(self, state: Sequence[float]) -> State: ...


class IdentificationError(ValueError):
    """Invalid hypotheses, experiments, observations, or budgets."""


@dataclass(frozen=True)
class OperatorHypothesis:
    hypothesis_id: str
    program: PredictiveProgram

    def predict(self, state: Sequence[float]) -> State:
        return self.program.apply(state)


@dataclass(frozen=True)
class Observation:
    before: State
    after: State
    source_id: str = "environment"


@dataclass(frozen=True)
class ExperimentCandidate:
    before: State
    entropy_bits: float
    expected_remaining: float
    worst_case_remaining: int
    partitions: tuple[tuple[State, tuple[str, ...]], ...]


@dataclass(frozen=True)
class ExperimentRecord:
    before: State
    after: State
    surviving_hypotheses: tuple[str, ...]
    source_id: str
    version_space_digest: str


@dataclass(frozen=True)
class IdentificationStatus:
    status: str
    surviving_hypotheses: tuple[str, ...]
    experiments_used: int
    reason: str


class ActiveOperatorIdentifier:
    """Select maximum-disagreement queries and eliminate falsified hypotheses.

    The query pool is explicit and finite. A query is informative only when
    surviving hypotheses predict different outputs for it. Ties are resolved
    deterministically by expected remaining version-space size, worst-case
    remaining size, then lexicographic input state.
    """

    def __init__(
        self,
        hypotheses: Iterable[OperatorHypothesis],
        query_pool: Iterable[Sequence[float]],
        *,
        max_experiments: int = 8,
        tolerance: float = 1e-8,
    ) -> None:
        items = tuple(hypotheses)
        if not items:
            raise IdentificationError("at least one hypothesis is required")
        ids = [item.hypothesis_id for item in items]
        if any(not item for item in ids) or len(set(ids)) != len(ids):
            raise IdentificationError("hypothesis IDs must be non-empty and unique")
        if (
            isinstance(max_experiments, bool)
            or not isinstance(max_experiments, int)
            or max_experiments < 0
            or isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or tolerance < 0
        ):
            raise IdentificationError("invalid experiment budget or tolerance")
        pool = tuple(sorted({self._state(row) for row in query_pool}))
        if not pool:
            raise IdentificationError("query pool must not be empty")
        dimensions = {len(row) for row in pool}
        if len(dimensions) != 1:
            raise IdentificationError("query states must have equal dimensions")
        self._hypotheses = items
        self._pool = pool
        self._max_experiments = max_experiments
        self._tolerance = tolerance
        self._observations: list[Observation] = []
        self._rejected_observations: list[Observation] = []
        self._records: list[ExperimentRecord] = []
        self._issued: dict[State, ExperimentCandidate] = {}
        self._answered_inputs: set[State] = set()
        self._used_inputs: set[State] = set()

    @staticmethod
    def _state(values: Sequence[float]) -> State:
        state = tuple(float(value) for value in values)
        if not state or any(not math.isfinite(value) for value in state):
            raise IdentificationError("states must be non-empty and finite")
        return state

    @property
    def hypotheses(self) -> tuple[OperatorHypothesis, ...]:
        return self._hypotheses

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(self._observations)

    @property
    def rejected_observations(self) -> tuple[Observation, ...]:
        return tuple(self._rejected_observations)

    @property
    def records(self) -> tuple[ExperimentRecord, ...]:
        return tuple(self._records)

    @staticmethod
    def _digest(ids: Sequence[str]) -> str:
        payload = "\n".join(sorted(ids)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _same(self, left: Sequence[float], right: Sequence[float]) -> bool:
        return len(left) == len(right) and all(
            abs(a - b) <= self._tolerance for a, b in zip(left, right)
        )

    def rank_experiments(self) -> tuple[ExperimentCandidate, ...]:
        if len(self._hypotheses) <= 1:
            return ()
        ranked = []
        for state in self._pool:
            if state in self._used_inputs:
                continue
            predictions = []
            for hypothesis in self._hypotheses:
                try:
                    prediction = self._state(hypothesis.predict(state))
                except (TypeError, ValueError, OverflowError) as exc:
                    raise IdentificationError(
                        f"hypothesis {hypothesis.hypothesis_id!r} returned an invalid state"
                    ) from exc
                if len(prediction) != len(state):
                    raise IdentificationError(
                        f"hypothesis {hypothesis.hypothesis_id!r} changed state dimension"
                    )
                predictions.append((prediction, hypothesis.hypothesis_id))

            # Absolute-tolerance closeness is not transitive. Build deterministic
            # complete-link clusters over sorted predictions so hypothesis ID
            # ordering cannot change the resulting partition.
            predictions.sort(key=lambda item: (item[0], item[1]))
            groups: list[tuple[list[State], list[str]]] = []
            for prediction, hypothesis_id in predictions:
                matching = next(
                    (
                        group for group in groups
                        if all(self._same(member, prediction) for member in group[0])
                    ),
                    None,
                )
                if matching is None:
                    groups.append(([prediction], [hypothesis_id]))
                else:
                    matching[0].append(prediction)
                    matching[1].append(hypothesis_id)
            if len(groups) <= 1:
                continue
            sizes = [len(ids) for _, ids in groups]
            total = len(self._hypotheses)
            entropy = -sum(
                (size / total) * math.log2(size / total) for size in sizes
            )
            expected = sum(size * size for size in sizes) / total
            ranked.append(ExperimentCandidate(
                before=state,
                entropy_bits=entropy,
                expected_remaining=expected,
                worst_case_remaining=max(sizes),
                partitions=tuple(
                    (outputs[0], tuple(sorted(ids)))
                    for outputs, ids in groups
                ),
            ))
        ranked.sort(key=lambda item: (
            -item.entropy_bits,
            item.expected_remaining,
            item.worst_case_remaining,
            item.before,
        ))
        return tuple(ranked)

    def choose_experiment(self) -> ExperimentCandidate | None:
        if len(self._issued) >= self._max_experiments:
            return None
        if len(self._issued) > len(self._answered_inputs):
            return None
        ranked = self.rank_experiments()
        if not ranked:
            return None
        chosen = ranked[0]
        self._issued[chosen.before] = chosen
        self._used_inputs.add(chosen.before)
        return chosen

    def observe(
        self,
        before: Sequence[float],
        after: Sequence[float],
        *,
        source_id: str = "environment",
    ) -> IdentificationStatus:
        state = self._state(before)
        output = self._state(after)
        if not isinstance(source_id, str) or not source_id.strip():
            raise IdentificationError("source_id must be a non-empty string")
        if len(output) != len(state):
            raise IdentificationError("observed output dimension must match input state")
        if state not in self._issued:
            raise IdentificationError("observation must answer an issued experiment")
        for prior in self._observations + self._rejected_observations:
            if self._same(prior.before, state):
                if self._same(prior.after, output):
                    raise IdentificationError("experiment input was already observed")
                raise IdentificationError("conflicting outcome for an observed input")

        observation = Observation(state, output, source_id)
        survivors = tuple(
            hypothesis for hypothesis in self._hypotheses
            if self._same(self._state(hypothesis.predict(state)), output)
        )
        self._answered_inputs.add(state)
        if not survivors:
            self._rejected_observations.append(observation)
            raise IdentificationError(
                "no hypothesis explains the observation; counterexample preserved, revise grammar"
            )
        self._hypotheses = survivors
        self._observations.append(observation)
        ids = tuple(item.hypothesis_id for item in survivors)
        self._records.append(ExperimentRecord(
            before=state,
            after=output,
            surviving_hypotheses=ids,
            source_id=source_id,
            version_space_digest=self._digest(ids),
        ))
        return self.status()

    def status(self) -> IdentificationStatus:
        ids = tuple(item.hypothesis_id for item in self._hypotheses)
        if len(ids) == 1:
            return IdentificationStatus(
                "identified", ids, len(self._issued),
                "one hypothesis remains in the declared candidate set",
            )
        if len(self._issued) > len(self._answered_inputs):
            return IdentificationStatus(
                "ambiguous", ids, len(self._issued),
                "an informative experiment is awaiting its observation",
            )
        if not self.rank_experiments():
            return IdentificationStatus(
                "unidentifiable", ids, len(self._issued),
                "all surviving hypotheses agree on the remaining query pool",
            )
        if len(self._issued) >= self._max_experiments:
            return IdentificationStatus(
                "budget_exhausted", ids, len(self._issued),
                "experiment budget exhausted while multiple hypotheses remain",
            )
        return IdentificationStatus(
            "ambiguous", ids, len(self._issued),
            "more than one hypothesis remains; informative experiments are available",
        )
