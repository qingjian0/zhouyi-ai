"""YJ-05: auditable coordination of discovery, validation and active tests.

This layer coordinates the bounded YJ-04 relational inducer. It does not claim
to merge N0.10/N0.11/N0.12/E13 into one trained model; it makes evidence,
candidate lifecycle, validation splits and active experiment handling explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Sequence

from prototype.yijing_operator_induction import (
    CandidateStatus as InductionStatus,
    EvidenceKind,
    ExperimentQuery,
    MechanismCandidate,
    RelationalOperatorInducer,
    TransitionObservation,
    rank_experiments,
)


class LearningLoopError(ValueError):
    """Invalid evidence split, candidate lifecycle, or experiment protocol."""


class EvidenceSplit(str, Enum):
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class CandidateLifecycle(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EvidenceCase:
    observation: TransitionObservation
    split: EvidenceSplit

    @property
    def evidence_id(self) -> str:
        return self.observation.evidence_id


@dataclass(frozen=True)
class CandidateRecord:
    candidate: MechanismCandidate
    lifecycle: CandidateLifecycle
    discovery_evidence_ids: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...] = ()
    counterexample_ids: tuple[str, ...] = ()
    validation_accuracy: float | None = None
    validation_coverage: float | None = None


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    split: EvidenceSplit
    total: int
    eligible: int
    correct: int
    abstained_evidence_ids: tuple[str, ...]
    incorrect_evidence_ids: tuple[str, ...]

    @property
    def coverage(self) -> float:
        return self.eligible / self.total if self.total else 0.0

    @property
    def accuracy(self) -> float:
        return self.correct / self.eligible if self.eligible else 0.0


@dataclass(frozen=True)
class ExperimentFeedback:
    query_id: str
    evidence_id: str
    evidence_kind: EvidenceKind
    matching_candidate_ids: tuple[str, ...]
    contradicted_candidate_ids: tuple[str, ...]
    unexplained_outcome: bool


class OperatorLearningCoordinator:
    """A small evidence-governed loop around the YJ-04 structural inducer.

    DISCOVERY evidence may propose candidates. VALIDATION evidence may promote
    candidates to VALIDATED. TEST evidence is reporting-only. Active query
    outcomes are separately committed and revealed with provenance.
    """

    def __init__(
        self, *, min_support: int = 2, max_candidates: int = 256
    ) -> None:
        self._min_support = min_support
        self._inducer = RelationalOperatorInducer(
            min_support=min_support, max_candidates=max_candidates
        )
        self._records: dict[str, CandidateRecord] = {}
        self._evidence_ledger: dict[str, str] = {}
        self._tickets: dict[str, ExperimentQuery] = {}
        self._revealed_query_ids: set[str] = set()

    @property
    def candidates(self) -> tuple[CandidateRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def propose(self, cases: Iterable[EvidenceCase]) -> tuple[CandidateRecord, ...]:
        rows = tuple(cases)
        if not rows:
            raise LearningLoopError("discovery evidence must not be empty")
        if any(case.split != EvidenceSplit.DISCOVERY for case in rows):
            raise LearningLoopError("only DISCOVERY evidence may propose candidates")
        ids = [case.evidence_id for case in rows]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise LearningLoopError("discovery evidence IDs must be non-empty and unique")
        if any(item in self._evidence_ledger for item in ids):
            raise LearningLoopError("evidence IDs cannot be reused across splits or events")
        report = self._inducer.discover(case.observation for case in rows)
        proposed = []
        for candidate in report.candidates:
            prior = self._records.get(candidate.candidate_id)
            if prior is not None:
                prior_candidate = prior.candidate
                common_patterns = tuple(sorted(
                    set(prior_candidate.required_patterns)
                    & set(candidate.required_patterns)
                ))
                prior_context = dict(prior_candidate.required_context)
                next_context = dict(candidate.required_context)
                common_context = tuple(sorted(
                    (key, value) for key, value in prior_context.items()
                    if next_context.get(key) == value
                ))
                evidence_ids = tuple(sorted(
                    set(prior_candidate.evidence_ids) | set(candidate.evidence_ids)
                ))
                evidence_kinds = tuple(sorted(
                    set(prior_candidate.evidence_kinds) | set(candidate.evidence_kinds),
                    key=lambda item: item.value,
                ))
                domains = tuple(sorted(
                    set(prior_candidate.domains) | set(candidate.domains)
                ))
                candidate = replace(
                    candidate,
                    version=prior_candidate.version + 1,
                    required_patterns=common_patterns,
                    required_context=common_context,
                    evidence_ids=evidence_ids,
                    evidence_kinds=evidence_kinds,
                    domains=domains,
                    status=(
                        InductionStatus.INTERVENTION_SUPPORTED
                        if EvidenceKind.INTERVENTIONAL in evidence_kinds
                        and len(evidence_ids) >= self._min_support
                        else InductionStatus.PROPOSED
                    ),
                )
                lifecycle = (
                    prior.lifecycle
                    if prior.lifecycle in {
                        CandidateLifecycle.SUSPENDED, CandidateLifecycle.REJECTED
                    }
                    else CandidateLifecycle.PROPOSED
                )
                record = replace(
                    prior,
                    candidate=candidate,
                    lifecycle=lifecycle,
                    discovery_evidence_ids=evidence_ids,
                    validation_accuracy=None,
                    validation_coverage=None,
                )
            else:
                record = CandidateRecord(
                    candidate=candidate,
                    lifecycle=CandidateLifecycle.PROPOSED,
                    discovery_evidence_ids=candidate.evidence_ids,
                )
            self._records[candidate.candidate_id] = record
            proposed.append(record)
        self._evidence_ledger.update({item: EvidenceSplit.DISCOVERY.value for item in ids})
        return tuple(proposed)

    def evaluate(
        self,
        candidate_id: str,
        cases: Iterable[EvidenceCase],
        *,
        split: EvidenceSplit,
    ) -> CandidateEvaluation:
        if split not in {EvidenceSplit.VALIDATION, EvidenceSplit.TEST}:
            raise LearningLoopError("evaluation split must be VALIDATION or TEST")
        if candidate_id not in self._records:
            raise LearningLoopError("unknown candidate")
        rows = tuple(cases)
        if not rows or any(case.split != split for case in rows):
            raise LearningLoopError("all evaluation cases must use the declared split")
        ids = [case.evidence_id for case in rows]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise LearningLoopError("evaluation evidence IDs must be non-empty and unique")
        if any(item in self._evidence_ledger for item in ids):
            raise LearningLoopError("evidence IDs cannot be reused across splits or events")
        candidate = self._records[candidate_id].candidate
        eligible = correct = 0
        abstained, incorrect = [], []
        for case in rows:
            observation = case.observation
            prediction = candidate.predict(
                observation.before, observation.intervention,
                domain=observation.domain,
            )
            if prediction is None:
                abstained.append(case.evidence_id)
                continue
            eligible += 1
            if prediction == observation.after:
                correct += 1
            else:
                incorrect.append(case.evidence_id)
        self._evidence_ledger.update({item: split.value for item in ids})
        return CandidateEvaluation(
            candidate_id, split, len(rows), eligible, correct,
            tuple(sorted(abstained)), tuple(sorted(incorrect)),
        )

    def validate(
        self,
        evaluation: CandidateEvaluation,
        *,
        minimum_accuracy: float = 1.0,
        minimum_coverage: float = 0.5,
    ) -> CandidateRecord:
        if evaluation.split != EvidenceSplit.VALIDATION:
            raise LearningLoopError("only VALIDATION evidence may promote a candidate")
        if not (0.0 <= minimum_accuracy <= 1.0 and 0.0 <= minimum_coverage <= 1.0):
            raise LearningLoopError("validation thresholds must be within [0,1]")
        record = self._records.get(evaluation.candidate_id)
        if record is None:
            raise LearningLoopError("unknown candidate")
        if record.lifecycle != CandidateLifecycle.PROPOSED:
            raise LearningLoopError("only PROPOSED candidates can be validated")
        if evaluation.total < 1:
            raise LearningLoopError("validation evaluation must contain evidence")
        passed = (
            evaluation.accuracy >= minimum_accuracy
            and evaluation.coverage >= minimum_coverage
            and not evaluation.incorrect_evidence_ids
        )
        updated = replace(
            record,
            lifecycle=(
                CandidateLifecycle.VALIDATED if passed
                else CandidateLifecycle.PROPOSED
            ),
            validation_accuracy=evaluation.accuracy,
            validation_coverage=evaluation.coverage,
        )
        self._records[evaluation.candidate_id] = updated
        return updated

    def rank_queries(
        self, queries: Iterable[ExperimentQuery]
    ):
        eligible = tuple(
            record.candidate for record in self._records.values()
            if record.lifecycle in {
                CandidateLifecycle.PROPOSED, CandidateLifecycle.VALIDATED
            }
        )
        if len(eligible) < 2:
            return ()
        return rank_experiments(eligible, queries)

    def commit_experiment(self, query: ExperimentQuery) -> None:
        if not query.query_id or query.query_id in self._tickets:
            raise LearningLoopError("query_id must be non-empty and not previously issued")
        ranked = self.rank_queries((query,))
        if not ranked:
            raise LearningLoopError("query does not distinguish at least two eligible candidates")
        self._tickets[query.query_id] = query

    def reveal_experiment(
        self,
        query_id: str,
        after,
        *,
        evidence_id: str,
        evidence_kind: EvidenceKind,
    ) -> ExperimentFeedback:
        query = self._tickets.get(query_id)
        if query is None:
            raise LearningLoopError("outcome must answer a committed experiment")
        if query_id in self._revealed_query_ids:
            raise LearningLoopError("experiment outcome has already been revealed")
        if not evidence_id or evidence_id in self._evidence_ledger:
            raise LearningLoopError("evidence_id must be globally unique across all splits and events")
        observation = TransitionObservation(
            before=query.state,
            after=after,
            intervention=query.intervention,
            evidence_id=evidence_id,
            evidence_kind=evidence_kind,
            domain=query.domain,
        )
        matching, contradicted = [], []
        for candidate_id, record in tuple(self._records.items()):
            if record.lifecycle in {
                CandidateLifecycle.SUSPENDED, CandidateLifecycle.REJECTED
            }:
                continue
            prediction = record.candidate.predict(
                observation.before, observation.intervention,
                domain=observation.domain,
            )
            if prediction is None:
                continue
            if prediction == observation.after:
                matching.append(candidate_id)
                updated = replace(
                    record,
                    supporting_evidence_ids=tuple(sorted(
                        set(record.supporting_evidence_ids) | {evidence_id}
                    )),
                )
            else:
                contradicted.append(candidate_id)
                updated = replace(
                    record,
                    lifecycle=CandidateLifecycle.SUSPENDED,
                    counterexample_ids=tuple(sorted(
                        set(record.counterexample_ids) | {evidence_id}
                    )),
                )
            self._records[candidate_id] = updated
        self._revealed_query_ids.add(query_id)
        self._evidence_ledger[evidence_id] = "ACTIVE_INTERVENTION"
        return ExperimentFeedback(
            query_id, evidence_id, evidence_kind,
            tuple(sorted(matching)), tuple(sorted(contradicted)),
            not matching and not contradicted,
        )
