"""Evidence-grounded, task-conditioned class formation for classiang cognition.

A conservative symbolic baseline: consumes observed features and upstream
relevance scores; it does not infer perception, causality, or semantic truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

DIMENSIONS = frozenset({
    "morphology", "attribute", "function", "relation",
    "process", "spatiotemporal", "potential", "integrated",
})


class MembershipDecision(str, Enum):
    ACCEPT_PROVISIONAL = "accept_provisional"
    REJECT = "reject"
    ABSTAIN = "abstain"


class InductionStatus(str, Enum):
    PROVISIONAL = "provisional"
    DISCRIMINATIVE = "discriminative"
    UNDERDETERMINED = "underdetermined"


@dataclass(frozen=True, order=True)
class FeatureAtom:
    dimension: str
    value: str

    def validate(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ValueError("unknown feature dimension")
        _text(self.value, "feature value")


@dataclass(frozen=True)
class FeatureCandidate:
    feature_id: str
    atom: FeatureAtom
    evidence_refs: tuple[str, ...]
    purpose_scores: tuple[tuple[str, float], ...]

    def validate(self, observation_evidence: set[str]) -> None:
        _text(self.feature_id, "feature_id")
        if not isinstance(self.atom, FeatureAtom):
            raise ValueError("atom must be FeatureAtom")
        self.atom.validate()
        _unique_texts(self.evidence_refs, "feature evidence_refs", allow_empty=False)
        if not set(self.evidence_refs) <= observation_evidence:
            raise ValueError("feature evidence is not grounded in its observation")
        if not isinstance(self.purpose_scores, tuple):
            raise ValueError("purpose_scores must be a tuple")
        purposes: set[str] = set()
        for item in self.purpose_scores:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("purpose score must be a (purpose, score) pair")
            purpose, score = item
            _text(purpose, "purpose")
            if purpose in purposes:
                raise ValueError("purpose scores must have unique purposes")
            purposes.add(purpose)
            if (isinstance(score, bool) or not isinstance(score, (int, float))
                    or not math.isfinite(score) or not 0.0 <= score <= 1.0):
                raise ValueError("purpose score must be finite and in [0, 1]")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    subject_id: str
    domain: str
    evidence_refs: tuple[str, ...]
    features: tuple[FeatureCandidate, ...]
    context: tuple[str, ...] = ()
    explicit_contradictions: tuple[FeatureAtom, ...] = ()

    def validate(self) -> None:
        for field in ("observation_id", "subject_id", "domain"):
            _text(getattr(self, field), field)
        _unique_texts(self.evidence_refs, "observation evidence_refs", allow_empty=False)
        _unique_texts(self.context, "context", allow_empty=True)
        if not isinstance(self.features, tuple):
            raise ValueError("features must be a tuple")
        feature_ids: set[str] = set()
        for feature in self.features:
            if not isinstance(feature, FeatureCandidate):
                raise ValueError("features must contain FeatureCandidate")
            feature.validate(set(self.evidence_refs))
            if feature.feature_id in feature_ids:
                raise ValueError("feature IDs must be unique per observation")
            feature_ids.add(feature.feature_id)
        if not isinstance(self.explicit_contradictions, tuple):
            raise ValueError("explicit_contradictions must be a tuple")
        for atom in self.explicit_contradictions:
            if not isinstance(atom, FeatureAtom):
                raise ValueError("contradictions must contain FeatureAtom")
            atom.validate()
        if len(set(self.explicit_contradictions)) != len(self.explicit_contradictions):
            raise ValueError("explicit contradictions must be unique")
        if {feature.atom for feature in self.features} & set(self.explicit_contradictions):
            raise ValueError("a feature cannot be both observed and explicitly contradicted")


@dataclass(frozen=True)
class AspectSelection:
    observation_id: str
    purpose: str
    selected: tuple[FeatureAtom, ...]
    excluded: tuple[FeatureAtom, ...]
    unscored: tuple[FeatureAtom, ...]
    threshold: float


@dataclass(frozen=True)
class ClassExample:
    observation: Observation
    purpose: str
    selected_aspects: tuple[FeatureAtom, ...]
    selection_threshold: float = 0.5

    def validate(self) -> None:
        self.observation.validate()
        _text(self.purpose, "purpose")
        _threshold(self.selection_threshold, "selection_threshold")
        if not isinstance(self.selected_aspects, tuple):
            raise ValueError("selected_aspects must be a tuple")
        for atom in self.selected_aspects:
            if not isinstance(atom, FeatureAtom):
                raise ValueError("selected_aspects must contain FeatureAtom")
            atom.validate()
        if len(set(self.selected_aspects)) != len(self.selected_aspects):
            raise ValueError("selected_aspects must be unique")
        expected = select_aspects(
            self.observation, purpose=self.purpose,
            min_relevance=self.selection_threshold,
        ).selected
        if self.selected_aspects != expected:
            raise ValueError("selected aspects must match the task-conditioned selection protocol")


@dataclass(frozen=True)
class ClassHypothesis:
    class_id: str
    purpose: str
    domains: tuple[str, ...]
    required_features: tuple[FeatureAtom, ...]
    shared_positive_features: tuple[FeatureAtom, ...]
    negative_boundary_features: tuple[FeatureAtom, ...]
    positive_example_ids: tuple[str, ...]
    negative_example_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    counterexample_refs: tuple[str, ...]
    validity_scope: str
    version: int
    status: InductionStatus
    selection_threshold: float
    semantic_validity_established: bool = False


@dataclass(frozen=True)
class InductionResult:
    status: InductionStatus
    hypothesis: ClassHypothesis | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class MembershipAssessment:
    observation_id: str
    decision: MembershipDecision
    matched_features: tuple[FeatureAtom, ...]
    missing_features: tuple[FeatureAtom, ...]
    contradicted_features: tuple[FeatureAtom, ...]
    reason_codes: tuple[str, ...]


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _unique_texts(values: tuple[str, ...], field: str, *, allow_empty: bool) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be a tuple")
    for value in values:
        _text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")


def _threshold(value: float, field: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0.0 <= value <= 1.0):
        raise ValueError(f"{field} must be finite and in [0, 1]")


def select_aspects(
    observation: Observation, *, purpose: str, min_relevance: float = 0.5
) -> AspectSelection:
    """Select evidence-grounded features scored for the declared purpose.

    Scores are supplied by an upstream annotator/model; they are not assumed
    to be calibrated probabilities or independently verified judgments.
    """
    observation.validate()
    _text(purpose, "purpose")
    _threshold(min_relevance, "min_relevance")
    selected, excluded, unscored = [], [], []
    for feature in observation.features:
        scores = dict(feature.purpose_scores)
        if purpose not in scores:
            unscored.append(feature.atom)
        elif scores[purpose] >= min_relevance:
            selected.append(feature.atom)
        else:
            excluded.append(feature.atom)
    return AspectSelection(
        observation.observation_id, purpose,
        tuple(sorted(set(selected))), tuple(sorted(set(excluded))),
        tuple(sorted(set(unscored))), float(min_relevance),
    )


def induce_class(
    *,
    class_id: str,
    purpose: str,
    positive_examples: Sequence[ClassExample],
    negative_examples: Sequence[ClassExample] = (),
    validity_scope: str,
    version: int = 1,
) -> InductionResult:
    """Induce a conservative conjunction from shared positive aspects.

    A feature is discriminative only if it occurs in every positive example
    and in no supplied negative example. Without negatives, the result stays
    provisional. This is not open-world concept learning.
    """
    _text(class_id, "class_id")
    _text(purpose, "purpose")
    _text(validity_scope, "validity_scope")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("version must be a positive integer")
    if not isinstance(positive_examples, Sequence) or not positive_examples:
        raise ValueError("at least one positive example is required")
    if not isinstance(negative_examples, Sequence):
        raise ValueError("negative_examples must be a sequence")
    positives, negatives = tuple(positive_examples), tuple(negative_examples)
    for example in positives + negatives:
        if not isinstance(example, ClassExample):
            raise ValueError("examples must be ClassExample")
        example.validate()
        if example.purpose != purpose:
            raise ValueError("all examples must use the induction purpose")
    thresholds = {float(item.selection_threshold) for item in positives + negatives}
    if len(thresholds) != 1:
        raise ValueError("all examples must use the same selection threshold")
    selection_threshold = thresholds.pop()
    ids = [item.observation.observation_id for item in positives + negatives]
    if len(ids) != len(set(ids)):
        raise ValueError("example observation IDs must be unique")
    if len(positives) < 2:
        return InductionResult(
            InductionStatus.UNDERDETERMINED, None, ("INSUFFICIENT_POSITIVE_EXAMPLES",)
        )

    shared = set.intersection(*(set(item.selected_aspects) for item in positives))
    negative_union = set().union(*(set(item.selected_aspects) for item in negatives)) if negatives else set()
    discriminative = shared - negative_union
    if not shared:
        return InductionResult(
            InductionStatus.UNDERDETERMINED, None, ("NO_SHARED_POSITIVE_ASPECTS",)
        )
    if negatives and not discriminative:
        return InductionResult(
            InductionStatus.UNDERDETERMINED, None, ("NO_DISCRIMINATIVE_BOUNDARY_FEATURES",)
        )

    evidence = {ref for item in positives for ref in item.observation.evidence_refs}
    counterexamples = {ref for item in negatives for ref in item.observation.evidence_refs}
    status = InductionStatus.DISCRIMINATIVE if negatives else InductionStatus.PROVISIONAL
    hypothesis = ClassHypothesis(
        class_id=class_id, purpose=purpose,
        domains=tuple(sorted({item.observation.domain for item in positives})),
        required_features=tuple(sorted(discriminative if negatives else shared)),
        shared_positive_features=tuple(sorted(shared)),
        negative_boundary_features=tuple(sorted(negative_union)),
        positive_example_ids=tuple(sorted(item.observation.observation_id for item in positives)),
        negative_example_ids=tuple(sorted(item.observation.observation_id for item in negatives)),
        evidence_refs=tuple(sorted(evidence)),
        counterexample_refs=tuple(sorted(counterexamples)),
        validity_scope=validity_scope, version=version, status=status,
        selection_threshold=selection_threshold,
    )
    reasons = () if negatives else ("NEGATIVE_BOUNDARY_NOT_TESTED",)
    return InductionResult(status, hypothesis, reasons)


def assess_membership(
    observation: Observation, hypothesis: ClassHypothesis
) -> MembershipAssessment:
    """Assess a case; missing aspects abstain rather than being treated as false."""
    observation.validate()
    if not isinstance(hypothesis, ClassHypothesis):
        raise ValueError("hypothesis must be ClassHypothesis")
    present = set(select_aspects(
        observation, purpose=hypothesis.purpose,
        min_relevance=hypothesis.selection_threshold,
    ).selected)
    required = set(hypothesis.required_features)
    matched = tuple(sorted(present & required))
    missing = tuple(sorted(required - present))
    contradicted = tuple(sorted(set(observation.explicit_contradictions) & required))
    if contradicted:
        decision, reasons = MembershipDecision.REJECT, ("EXPLICIT_FEATURE_CONTRADICTION",)
    elif missing:
        decision, reasons = MembershipDecision.ABSTAIN, ("REQUIRED_ASPECTS_NOT_OBSERVED",)
    else:
        decision, reasons = MembershipDecision.ACCEPT_PROVISIONAL, ("MATCHES_PROVISIONAL_RULE",)
    return MembershipAssessment(
        observation.observation_id, decision, matched, missing, contradicted, reasons
    )
