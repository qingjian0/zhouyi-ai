"""CSG-GCR bounded global coordinator (research prototype).

This module coordinates immutable local proposals emitted by SROK or other
proposers. It does not generate local relations, validate scientific truth,
write evidence, or own candidate lifecycle. E09 and E12-A6 remain authoritative
for evidence governance and lifecycle transitions.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable


class CoordinationError(ValueError):
    """Invalid proposal or global coordination budget."""


@dataclass(frozen=True)
class CandidateProposal:
    proposal_id: str
    parent_state_ref: str
    branch_id: str
    bindings: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    score: float = 0.0
    cost: int = 1
    candidate_kind: str = "UNSPECIFIED"


@dataclass(frozen=True)
class GlobalConstraints:
    required_bindings: tuple[tuple[str, str], ...] = ()
    forbidden_bindings: tuple[tuple[str, str], ...] = ()
    max_selected: int = 8
    max_cost: int = 64
    max_states: int = 10_000
    result_limit: int = 5


@dataclass(frozen=True)
class CoordinatedCandidate:
    parent_state_ref: str
    proposal_ids: tuple[str, ...]
    branch_ids: tuple[str, ...]
    candidate_kinds: tuple[str, ...]
    bindings: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]
    score: float
    cost: int


@dataclass(frozen=True)
class CoordinationReport:
    candidates: tuple[CoordinatedCandidate, ...]
    input_count: int
    expanded_states: int
    rejected_conflicts: int
    status: str
    pruned_partial_sets: int = 0


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CoordinationError(f"{field} must be a non-empty string")


def _require_unique(values: tuple[str, ...], field: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise CoordinationError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise CoordinationError(f"{field} must not contain duplicates")


def _validate_pairs(values: tuple[tuple[str, str], ...], field: str) -> None:
    keys: set[str] = set()
    for pair in values:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise CoordinationError(f"{field} entries must be (key, value) pairs")
        key, value = pair
        _require_text(key, f"{field} key")
        _require_text(value, f"{field} value")
        if key in keys:
            raise CoordinationError(f"{field} keys must be unique")
        keys.add(key)


def _validate_proposal(proposal: CandidateProposal) -> None:
    if not isinstance(proposal, CandidateProposal):
        raise CoordinationError("all proposals must be CandidateProposal")
    for field in ("proposal_id", "parent_state_ref", "branch_id", "candidate_kind"):
        _require_text(getattr(proposal, field), field)
    _validate_pairs(proposal.bindings, "bindings")
    for field in ("evidence_refs", "requires", "excludes"):
        _require_unique(getattr(proposal, field), field)
    if proposal.proposal_id in proposal.requires or proposal.proposal_id in proposal.excludes:
        raise CoordinationError("a proposal cannot require or exclude itself")
    if (not isinstance(proposal.score, (int, float))
            or isinstance(proposal.score, bool)
            or not math.isfinite(proposal.score)):
        raise CoordinationError("score must be finite")
    if isinstance(proposal.cost, bool) or not isinstance(proposal.cost, int) or proposal.cost < 0:
        raise CoordinationError("cost must be a non-negative integer")


def _validate_constraints(constraints: GlobalConstraints) -> None:
    if not isinstance(constraints, GlobalConstraints):
        raise CoordinationError("constraints must be GlobalConstraints")
    _validate_pairs(constraints.required_bindings, "required_bindings")
    _validate_pairs(constraints.forbidden_bindings, "forbidden_bindings")
    for field in ("max_selected", "max_cost", "max_states", "result_limit"):
        value = getattr(constraints, field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise CoordinationError(f"{field} must be a positive integer")


class CandidateCoordinator:
    """Find high-scoring compatible proposal sets under explicit hard budgets.

    Proposals sharing a parent state may be combined across branches. Proposals
    from different parent states are never silently mixed. Scores are ranking
    utilities only: they are not probabilities, evidence strength, or truth.
    """

    def coordinate(
        self,
        proposals: Iterable[CandidateProposal],
        constraints: GlobalConstraints = GlobalConstraints(),
        *,
        partial_feasibility: Callable[[tuple[CandidateProposal, ...]], bool] | None = None,
    ) -> CoordinationReport:
        _validate_constraints(constraints)
        rows = tuple(proposals)
        for proposal in rows:
            _validate_proposal(proposal)
        ids = tuple(proposal.proposal_id for proposal in rows)
        _require_unique(ids, "proposal_ids")
        known = set(ids)
        for proposal in rows:
            unknown = (set(proposal.requires) | set(proposal.excludes)) - known
            if unknown:
                raise CoordinationError(
                    f"proposal {proposal.proposal_id} references unknown proposals: {sorted(unknown)}"
                )

        # Stable ordering makes results independent of input iteration order.
        ordered = tuple(sorted(rows, key=lambda item: (
            -item.score, item.cost, item.proposal_id
        )))
        results: dict[tuple[str, ...], CoordinatedCandidate] = {}
        expanded = 0
        rejected = 0
        budget_exhausted = False
        pruned_partial = 0
        if partial_feasibility is not None and not callable(partial_feasibility):
            raise CoordinationError("partial_feasibility must be callable")

        def compatible(candidate: CandidateProposal,
                       selected: tuple[CandidateProposal, ...]) -> bool:
            if selected and candidate.parent_state_ref != selected[0].parent_state_ref:
                return False
            selected_ids = {item.proposal_id for item in selected}
            if any(item.proposal_id in candidate.excludes for item in selected):
                return False
            if any(candidate.proposal_id in item.excludes for item in selected):
                return False
            bindings: dict[str, str] = {}
            for item in (*selected, candidate):
                for key, value in item.bindings:
                    previous = bindings.get(key)
                    if key in bindings and bindings[key] != value:
                        return False
                    bindings[key] = value
            return True

        def emit(selected: tuple[CandidateProposal, ...], total_cost: int) -> None:
            selected_ids = {item.proposal_id for item in selected}
            if not selected or any(
                not set(item.requires).issubset(selected_ids) for item in selected
            ):
                return
            merged: dict[str, str] = {}
            for item in selected:
                for key, value in item.bindings:
                    if key in merged and merged[key] != value:
                        return
                    merged[key] = value
            if any(merged.get(key) != value
                   for key, value in constraints.required_bindings):
                return
            if any(merged.get(key) == value
                   for key, value in constraints.forbidden_bindings):
                return
            proposal_ids = tuple(sorted(selected_ids))
            branches = tuple(sorted({item.branch_id for item in selected}))
            kinds = tuple(sorted({item.candidate_kind for item in selected}))
            evidence = tuple(sorted({
                ref for item in selected for ref in item.evidence_refs
            }))
            try:
                combined_score = math.fsum(item.score for item in selected)
            except OverflowError as exc:
                raise CoordinationError("combined score overflowed") from exc
            if not math.isfinite(combined_score):
                raise CoordinationError("combined score must be finite")
            candidate = CoordinatedCandidate(
                parent_state_ref=selected[0].parent_state_ref,
                proposal_ids=proposal_ids,
                branch_ids=branches,
                candidate_kinds=kinds,
                bindings=tuple(sorted(merged.items())),
                evidence_refs=evidence,
                score=combined_score,
                cost=total_cost,
            )
            results[proposal_ids] = candidate

        def search(index: int, selected: tuple[CandidateProposal, ...],
                   total_cost: int) -> None:
            nonlocal expanded, rejected, budget_exhausted, pruned_partial
            if expanded >= constraints.max_states:
                budget_exhausted = True
                return
            expanded += 1
            if index >= len(ordered) or len(selected) >= constraints.max_selected:
                emit(selected, total_cost)
                return

            current = ordered[index]
            # Explore inclusion first because proposals are utility-ranked.
            if total_cost + current.cost <= constraints.max_cost:
                if compatible(current, selected):
                    next_selected = (*selected, current)
                    if partial_feasibility is None:
                        search(index + 1, next_selected, total_cost + current.cost)
                    else:
                        feasible = partial_feasibility(next_selected)
                        if not isinstance(feasible, bool):
                            raise CoordinationError("partial_feasibility must return bool")
                        if feasible:
                            search(index + 1, next_selected, total_cost + current.cost)
                        else:
                            pruned_partial += 1
                else:
                    rejected += 1
            search(index + 1, selected, total_cost)

        search(0, (), 0)
        ranked = tuple(sorted(
            results.values(),
            key=lambda item: (
                -item.score, item.cost, len(item.proposal_ids), item.proposal_ids
            ),
        )[:constraints.result_limit])
        status = (
            "BUDGET_EXHAUSTED" if budget_exhausted
            else "COMPLETE" if ranked
            else "NO_FEASIBLE_SET"
        )
        return CoordinationReport(
            candidates=ranked,
            input_count=len(rows),
            expanded_states=expanded,
            rejected_conflicts=rejected,
            status=status,
            pruned_partial_sets=pruned_partial,
        )
