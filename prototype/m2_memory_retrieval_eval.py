"""Deterministic evaluation metrics for bounded lexical M2 retrieval.

This evaluator measures retrieval against explicit held-out relevant record IDs.
It does not score answer generation or claim semantic understanding.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from prototype.m2_memory_lexical_retrieval import retrieve_lexical_memory
from prototype.m2_memory_packet import MemoryQuery


class RetrievalEvaluationError(ValueError):
    """An evaluation case or metric configuration is invalid."""


@dataclass(frozen=True)
class LexicalRetrievalCase:
    query: MemoryQuery
    reader: object
    relevant_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class LexicalRetrievalEvaluation:
    cases: int
    k: int
    recall_at_k: float
    precision_at_k: float
    mean_reciprocal_rank: float
    hit_rate: float
    mean_candidates_scanned: float
    scan_budget_exhausted_cases: int
    mean_packet_bytes: float
    no_memory_recall_at_k: float = 0.0
    no_memory_precision_at_k: float = 0.0
    no_memory_mrr: float = 0.0
    no_memory_hit_rate: float = 0.0
    metric_schema: str = "m2-lexical-retrieval-eval-v1"


def evaluate_lexical_retrieval(
    cases: Sequence[LexicalRetrievalCase], *, k: int = 5,
) -> LexicalRetrievalEvaluation:
    """Evaluate fixed queries against explicit relevance judgments.

    Precision denominator is always k, including short result lists. Recall is
    averaged per query over its relevant IDs. Queries with no relevant IDs are
    rejected because they make recall undefined. No-memory is an explicit
    zero-retrieval baseline, not an inferred model response.
    """
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or not cases:
        raise RetrievalEvaluationError("cases must be a non-empty sequence")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise RetrievalEvaluationError("k must be a positive integer")

    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []
    hits: list[float] = []
    scanned: list[int] = []
    exhausted = 0
    packet_bytes: list[int] = []

    for case in cases:
        if not isinstance(case, LexicalRetrievalCase):
            raise RetrievalEvaluationError("every case must be LexicalRetrievalCase")
        relevant = case.relevant_record_ids
        if not relevant or any(not isinstance(value, str) or not value for value in relevant):
            raise RetrievalEvaluationError("relevant_record_ids must contain non-empty IDs")
        if len(set(relevant)) != len(relevant):
            raise RetrievalEvaluationError("relevant_record_ids must be unique")
        report = retrieve_lexical_memory(case.reader, case.query)
        ranked = [item.record_id for item in report.packet.items[:k]]
        relevant_set = set(relevant)
        found = [record_id for record_id in ranked if record_id in relevant_set]
        recalls.append(len(set(found)) / len(relevant_set))
        precisions.append(len(found) / k)
        reciprocal_ranks.append(
            next((1.0 / (index + 1) for index, record_id in enumerate(ranked)
                  if record_id in relevant_set), 0.0)
        )
        hits.append(1.0 if found else 0.0)
        scanned.append(report.candidates_scanned)
        packet_bytes.append(report.packet.serialized_bytes)
        exhausted += int(report.scan_budget_exhausted)

    return LexicalRetrievalEvaluation(
        cases=len(cases),
        k=k,
        recall_at_k=fmean(recalls),
        precision_at_k=fmean(precisions),
        mean_reciprocal_rank=fmean(reciprocal_ranks),
        hit_rate=fmean(hits),
        mean_candidates_scanned=fmean(scanned),
        scan_budget_exhausted_cases=exhausted,
        mean_packet_bytes=fmean(packet_bytes),
    )
