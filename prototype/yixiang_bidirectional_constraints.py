"""Bidirectional whole/part constraint evaluation for yixiang research.

This module is an auditable research baseline, not a learned cognitive model.
Local observations score whole-level hypotheses; hypotheses generate explicit
expectations that are checked against observations. Contradictions are retained
as residuals and never silently rewritten away.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Mapping


@dataclass(frozen=True)
class LocalObservation:
    feature: str
    value: str
    reliability: float
    evidence_ref: str

    def validate(self) -> None:
        if not self.feature.strip() or not self.value.strip():
            raise ValueError("observation feature and value are required")
        if not 0.0 < self.reliability <= 1.0:
            raise ValueError("reliability must be in (0, 1]")
        if not self.evidence_ref.strip():
            raise ValueError("observation requires an evidence reference")


@dataclass(frozen=True)
class WholeHypothesis:
    hypothesis_id: str
    expected_features: Mapping[str, str]
    prior: float = 1.0

    def validate(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis id is required")
        if not 0.0 < self.prior <= 1.0:
            raise ValueError("prior must be in (0, 1]")
        if not self.expected_features:
            raise ValueError("hypothesis must declare at least one expectation")
        if any(not key.strip() or not value.strip()
               for key, value in self.expected_features.items()):
            raise ValueError("expectation keys and values must be non-empty")


@dataclass(frozen=True)
class FeatureResidual:
    feature: str
    expected: str
    observed: str
    reliability: float
    evidence_ref: str


@dataclass(frozen=True)
class HypothesisAssessment:
    hypothesis_id: str
    score: float
    matched_features: tuple[str, ...]
    residuals: tuple[FeatureResidual, ...]
    unobserved_features: tuple[str, ...]


@dataclass(frozen=True)
class BidirectionalAssessment:
    ranked: tuple[HypothesisAssessment, ...]
    observed_feature_count: int

    @property
    def winner(self) -> HypothesisAssessment | None:
        return self.ranked[0] if self.ranked else None


def assess_hypotheses(
    observations: tuple[LocalObservation, ...],
    hypotheses: tuple[WholeHypothesis, ...],
) -> BidirectionalAssessment:
    """Rank competing wholes without discarding local counter-evidence.

    The score is a transparent weighted log score:
      log(prior) + sum(log(reliability) for matches)
                  + sum(log(1-reliability) for mismatches).
    Reliability=1 represents a hard observation; a mismatch then receives a
    finite floor rather than negative infinity so alternatives remain visible.
    Unobserved expectations are neutral, not treated as false.
    """
    seen: set[str] = set()
    for observation in observations:
        observation.validate()
        if observation.feature in seen:
            raise ValueError(f"duplicate observation for feature: {observation.feature}")
        seen.add(observation.feature)

    ids: set[str] = set()
    for hypothesis in hypotheses:
        hypothesis.validate()
        if hypothesis.hypothesis_id in ids:
            raise ValueError("hypothesis ids must be unique")
        ids.add(hypothesis.hypothesis_id)

    by_feature = {item.feature: item for item in observations}
    assessments: list[HypothesisAssessment] = []
    floor = 1e-12

    for hypothesis in hypotheses:
        score = log(hypothesis.prior)
        matched: list[str] = []
        residuals: list[FeatureResidual] = []
        unobserved: list[str] = []
        for feature, expected in hypothesis.expected_features.items():
            observed = by_feature.get(feature)
            if observed is None:
                unobserved.append(feature)
            elif observed.value == expected:
                matched.append(feature)
                score += log(max(observed.reliability, floor))
            else:
                residuals.append(FeatureResidual(
                    feature, expected, observed.value,
                    observed.reliability, observed.evidence_ref,
                ))
                score += log(max(1.0 - observed.reliability, floor))
        assessments.append(HypothesisAssessment(
            hypothesis.hypothesis_id, score, tuple(sorted(matched)),
            tuple(sorted(residuals, key=lambda item: item.feature)),
            tuple(sorted(unobserved)),
        ))

    assessments.sort(key=lambda item: (-item.score, item.hypothesis_id))
    return BidirectionalAssessment(tuple(assessments), len(observations))
