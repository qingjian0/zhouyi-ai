"""Register competing interpretations of classical inference terms without ranking them."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class InterpretiveFramework(str, Enum):
    LOGICAL_TAXONOMY = "logical_taxonomy"
    DIALECTICAL_PROCESS = "dialectical_process"
    UNIFIED_ANALOGY = "unified_analogy"
    RHETORICAL_PRAGMATIC = "rhetorical_pragmatic"
    TEXTUAL_PHILOLOGICAL = "textual_philological"
    OTHER = "other"

class InterpretationSourceLayer(str, Enum):
    PRE_QING_COMMENTARY = "pre_qing_commentary"
    QING_COMMENTARY = "qing_commentary"
    POST_QING_SCHOLARSHIP = "post_qing_scholarship"
    CONTEMPORARY_RESEARCH = "contemporary_research"

class CompetitionStatus(str, Enum):
    NO_RECORDED_POSITION = "no_recorded_position"
    SINGLE_POSITION = "single_position"
    MULTIPLE_POSITIONS_SAME_FRAMEWORK = "multiple_positions_same_framework"
    COMPETING_FRAMEWORKS = "competing_frameworks"

@dataclass(frozen=True)
class InterpretationPosition:
    position_id: str
    author: str
    work: str
    publication_year: int
    source_layer: InterpretationSourceLayer
    framework: InterpretiveFramework
    target_terms: Tuple[str, ...]
    interpretation: str
    scope: str
    textual_basis_refs: Tuple[str, ...]
    scholarship_refs: Tuple[str, ...]
    caveats: Tuple[str, ...]

@dataclass(frozen=True)
class InterpretationCase:
    case_id: str
    title: str
    primary_text_refs: Tuple[str, ...]
    positions: Tuple[InterpretationPosition, ...]

@dataclass(frozen=True)
class InterpretationCompetition:
    case_id: str
    status: CompetitionStatus
    position_ids: Tuple[str, ...]
    frameworks: Tuple[InterpretiveFramework, ...]
    shared_textual_basis_refs: Tuple[str, ...]
    unique_textual_basis_refs: Tuple[str, ...]
    winner_position_id: str | None = None
    interpretive_truth_established: bool = False
    independence_established: bool = False
    adjudication: str = "not_performed"

def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")

def _refs(values, field, allow_empty=False):
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be tuple")
    for value in values:
        _text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")

def _validate_position(position):
    if not isinstance(position, InterpretationPosition):
        raise ValueError("positions must contain InterpretationPosition")
    for field in ("position_id", "author", "work", "interpretation", "scope"):
        _text(getattr(position, field), field)
    if not isinstance(position.publication_year, int) or isinstance(position.publication_year, bool):
        raise ValueError("publication_year must be an integer")
    if position.publication_year <= 0:
        raise ValueError("publication_year must be positive")
    if not isinstance(position.source_layer, InterpretationSourceLayer):
        raise ValueError("invalid source_layer")
    if not isinstance(position.framework, InterpretiveFramework):
        raise ValueError("invalid framework")
    _refs(position.target_terms, "target_terms")
    _refs(position.textual_basis_refs, "textual_basis_refs")
    _refs(position.scholarship_refs, "scholarship_refs")
    _refs(position.caveats, "caveats")

def assess_interpretation_competition(case):
    """Report recorded diversity; never select the historically correct reading."""
    if not isinstance(case, InterpretationCase):
        raise ValueError("case must be InterpretationCase")
    _text(case.case_id, "case_id")
    _text(case.title, "title")
    _refs(case.primary_text_refs, "primary_text_refs")
    if not isinstance(case.positions, tuple):
        raise ValueError("positions must be tuple")
    seen = set()
    for position in case.positions:
        _validate_position(position)
        if position.position_id in seen:
            raise ValueError("duplicate position_id")
        seen.add(position.position_id)
        if not set(position.textual_basis_refs).intersection(case.primary_text_refs):
            raise ValueError("each position must link to at least one declared primary text reference")
    frameworks = tuple(sorted({p.framework for p in case.positions}, key=lambda x: x.value))
    if not case.positions:
        status = CompetitionStatus.NO_RECORDED_POSITION
    elif len(case.positions) == 1:
        status = CompetitionStatus.SINGLE_POSITION
    elif len(frameworks) == 1:
        status = CompetitionStatus.MULTIPLE_POSITIONS_SAME_FRAMEWORK
    else:
        status = CompetitionStatus.COMPETING_FRAMEWORKS
    if case.positions:
        counts = {}
        for position in case.positions:
            for ref in set(position.textual_basis_refs):
                counts[ref] = counts.get(ref, 0) + 1
        shared = tuple(sorted(ref for ref, count in counts.items() if count > 1))
        unique = tuple(sorted(ref for ref, count in counts.items() if count == 1))
    else:
        shared, unique = (), ()
    return InterpretationCompetition(
        case_id=case.case_id, status=status,
        position_ids=tuple(sorted(p.position_id for p in case.positions)),
        frameworks=frameworks, shared_textual_basis_refs=shared,
        unique_textual_basis_refs=unique,
    )
