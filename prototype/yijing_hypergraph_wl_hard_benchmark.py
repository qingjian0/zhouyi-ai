"""YJ-10.6: bounded exact-oracle benchmark for 1-WL orbit over-merging.

Two 2-regular seven-vertex graphs have identical 1-WL color histograms:
C7 and C3 disjoint-union C4. Their exact automorphism orbit partitions differ.
The exact oracle is feasible here because the typed entity-bijection budget is
7! = 5,040. This is a small pairwise baseline, not a general hypergraph claim.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.yijing_hypergraph_automorphism import (
    AutomorphismOracleError,
    exact_hypergraph_automorphism_audit,
)
from prototype.yijing_hypergraph_induction import (
    Entity,
    Hyperedge,
    HypergraphState,
    RoleBinding,
)
from prototype.yijing_hypergraph_role_induction import RelationSymmetry


class WLHardBenchmarkError(ValueError):
    """Invalid benchmark case or exact-oracle configuration."""


@dataclass(frozen=True)
class WLHardCaseReport:
    case_name: str
    entity_count: int
    edge_count: int
    candidate_bijections: int
    automorphism_count: int
    exact_orbit_sizes: tuple[int, ...]
    wl_class_sizes: tuple[int, ...]
    wl_color_histogram: tuple[tuple[str, int], ...]
    pairwise_true_positive: int
    pairwise_false_merge: int
    pairwise_false_split: int
    pairwise_true_negative: int
    wl_pairwise_precision: float
    wl_pairwise_recall: float


@dataclass(frozen=True)
class WLHardBenchmarkReport:
    cases: tuple[WLHardCaseReport, ...]
    wl_histograms_match: bool
    exact_orbit_partitions_differ: bool
    total_candidate_bijections: int


def _cycle_edges(vertices: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(
        tuple(sorted((vertices[index], vertices[(index + 1) % len(vertices)])))
        for index in range(len(vertices))
    )


def build_wl_hard_state(case_name: str) -> HypergraphState:
    """Build C7 or C3 disjoint-union C4 as an undirected typed hypergraph."""
    if case_name == "cycle7":
        edges = _cycle_edges(tuple(range(7)))
    elif case_name == "triangle_plus_square":
        edges = _cycle_edges((0, 1, 2)) + _cycle_edges((3, 4, 5, 6))
    else:
        raise WLHardBenchmarkError("case_name must be cycle7 or triangle_plus_square")

    normalized = tuple(sorted(set(tuple(sorted(edge)) for edge in edges)))
    if len(normalized) != 7:
        raise WLHardBenchmarkError("benchmark graph must contain exactly seven edges")

    entities = tuple(Entity(f"v{index}", "vertex") for index in range(7))
    hyperedges = tuple(
        Hyperedge(
            edge_id=f"e{index}",
            relation_type="undirected_edge",
            bindings=(
                RoleBinding("endpoint_a", f"v{left}"),
                RoleBinding("endpoint_b", f"v{right}"),
            ),
            evidence_ids=(f"{case_name}:edge:{index}",),
        )
        for index, (left, right) in enumerate(normalized)
    )
    return HypergraphState(
        entities=entities,
        hyperedges=hyperedges,
        context=(),
        step=0,
        evidence_id=f"wl-hard:{case_name}",
        domain="synthetic-wl-hard-orbit",
        coverage_complete=True,
    )


def _case_report(
    case_name: str,
    *,
    max_candidate_bijections: int = 5_040,
    max_rounds: int = 6,
) -> WLHardCaseReport:
    state = build_wl_hard_state(case_name)
    audit = exact_hypergraph_automorphism_audit(
        state,
        (RelationSymmetry("undirected_edge", "UNORDERED"),),
        max_candidate_bijections=max_candidate_bijections,
        max_rounds=max_rounds,
    )
    # Recompute stable WL signatures through the public role inducer so
    # the two benchmark cases can be compared across graph instances.
    from prototype.yijing_hypergraph_role_induction import infer_hypergraph_roles

    wl_colors: dict[str, int] = {}

    inferred = infer_hypergraph_roles(
        state, (RelationSymmetry("undirected_edge", "UNORDERED"),),
        max_rounds=max_rounds,
    )
    for assignment in inferred.assignments:
        wl_colors[assignment.structural_signature] = (
            wl_colors.get(assignment.structural_signature, 0) + 1
        )

    return WLHardCaseReport(
        case_name=case_name,
        entity_count=audit.entity_count,
        edge_count=len(state.hyperedges),
        candidate_bijections=audit.candidate_bijections,
        automorphism_count=audit.automorphism_count,
        exact_orbit_sizes=tuple(sorted(len(group) for group in audit.exact_orbits)),
        wl_class_sizes=tuple(sorted(len(group) for group in audit.wl_classes)),
        wl_color_histogram=tuple(sorted(wl_colors.items())),
        pairwise_true_positive=audit.pairwise_true_positive,
        pairwise_false_merge=audit.pairwise_false_merge,
        pairwise_false_split=audit.pairwise_false_split,
        pairwise_true_negative=audit.pairwise_true_negative,
        wl_pairwise_precision=audit.wl_pairwise_precision,
        wl_pairwise_recall=audit.wl_pairwise_recall,
    )


def run_wl_hard_orbit_benchmark(
    *, max_candidate_bijections: int = 5_040, max_rounds: int = 6
) -> WLHardBenchmarkReport:
    """Run the two-case exact-orbit versus 1-WL benchmark."""
    if (not isinstance(max_candidate_bijections, int)
            or isinstance(max_candidate_bijections, bool)
            or max_candidate_bijections < 1):
        raise WLHardBenchmarkError("max_candidate_bijections must be positive")
    if (not isinstance(max_rounds, int) or isinstance(max_rounds, bool)
            or not 0 <= max_rounds <= 12):
        raise WLHardBenchmarkError("max_rounds must be between 0 and 12")
    try:
        cases = (
            _case_report(
                "cycle7",
                max_candidate_bijections=max_candidate_bijections,
                max_rounds=max_rounds,
            ),
            _case_report(
                "triangle_plus_square",
                max_candidate_bijections=max_candidate_bijections,
                max_rounds=max_rounds,
            ),
        )
    except AutomorphismOracleError as exc:
        raise WLHardBenchmarkError(str(exc)) from exc

    return WLHardBenchmarkReport(
        cases=cases,
        wl_histograms_match=(
            cases[0].wl_color_histogram == cases[1].wl_color_histogram
        ),
        exact_orbit_partitions_differ=(
            cases[0].exact_orbit_sizes != cases[1].exact_orbit_sizes
        ),
        total_candidate_bijections=sum(item.candidate_bijections for item in cases),
    )
