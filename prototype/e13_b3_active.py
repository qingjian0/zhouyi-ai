"""E13-B3-D disagreement-driven query selection and version-space filtering."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

@dataclass(frozen=True)
class CandidateForecast:
    candidate_id: str
    query_id: str
    predicted_outcome: str

@dataclass(frozen=True)
class QueryScore:
    query_id: str
    disagreement: float
    pairwise_disagreements: int
    pair_count: int

@dataclass(frozen=True)
class QuerySelection:
    status: str
    selected: QueryScore | None
    scores: tuple[QueryScore, ...]
    reason: str | None = None

@dataclass(frozen=True)
class VersionSpaceUpdate:
    status: str
    retained_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    reason: str | None = None

def select_discriminating_query(candidate_ids: Iterable[str], forecasts: Iterable[CandidateForecast]) -> QuerySelection:
    candidates = tuple(sorted(set(candidate_ids)))
    if len(candidates) < 2:
        return QuerySelection("INSUFFICIENT_CANDIDATES", None, (), "NEED_AT_LEAST_TWO_CANDIDATES")
    grouped: dict[str, dict[str, str]] = {}
    for forecast in forecasts:
        if forecast.candidate_id not in candidates:
            raise ValueError("forecast references an unknown candidate")
        bucket = grouped.setdefault(forecast.query_id, {})
        if forecast.candidate_id in bucket:
            raise ValueError("duplicate candidate forecast for query")
        bucket[forecast.candidate_id] = forecast.predicted_outcome
    pair_count = len(candidates) * (len(candidates) - 1) // 2
    scores = []
    for query_id, outcomes in grouped.items():
        if set(outcomes) != set(candidates):
            continue
        disagreements = sum(outcomes[a] != outcomes[b] for a, b in combinations(candidates, 2))
        scores.append(QueryScore(query_id, disagreements / pair_count, disagreements, pair_count))
    if not scores:
        return QuerySelection("NO_DISCRIMINATING_QUERY", None, (), "NO_QUERY_HAS_COMPLETE_FORECASTS")
    scores.sort(key=lambda x: (-x.disagreement, x.query_id))
    best = scores[0]
    if best.pairwise_disagreements == 0:
        return QuerySelection("NO_DISAGREEMENT", best, tuple(scores), "ALL_CANDIDATES_PREDICT_THE_SAME")
    return QuerySelection("SELECTED", best, tuple(scores))

def update_version_space(candidate_ids: Iterable[str], forecasts: Iterable[CandidateForecast], *, query_id: str, observed_outcome: str) -> VersionSpaceUpdate:
    candidates = tuple(sorted(set(candidate_ids)))
    relevant = [x for x in forecasts if x.query_id == query_id]
    predictions = {x.candidate_id: x.predicted_outcome for x in relevant}
    if len(predictions) != len(relevant) or set(predictions) != set(candidates):
        return VersionSpaceUpdate("REJECTED_INCOMPLETE_EVIDENCE", (), candidates, "FORECASTS_MUST_COVER_EACH_CANDIDATE_EXACTLY_ONCE")
    retained = tuple(x for x in candidates if predictions[x] == observed_outcome)
    rejected = tuple(x for x in candidates if predictions[x] != observed_outcome)
    if not retained:
        return VersionSpaceUpdate("CONTRADICTION", (), rejected, "OBSERVATION_REJECTS_ALL_CURRENT_CANDIDATES")
    return VersionSpaceUpdate("UPDATED", retained, rejected)
