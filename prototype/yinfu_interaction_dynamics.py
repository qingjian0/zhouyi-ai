"""YF-02/YF-03: signed reciprocal interaction and context-dependent reversal.

A small synthetic mechanism, not a literal implementation of classical cosmology.
The three nodes are generic environment/resource/agent roles. Edge effects are
learned/declared parameters and can change sign with context.
"""
from __future__ import annotations
import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Iterable

@dataclass(frozen=True)
class InteractionEdge:
    source: str
    target: str
    base_effect: float
    context_sensitivity: float = 0.0

@dataclass(frozen=True)
class InteractionGraph:
    nodes: tuple[str, ...]
    edges: tuple[InteractionEdge, ...]

@dataclass(frozen=True)
class StepResult:
    states: tuple[tuple[str, float], ...]
    edge_effects: tuple[tuple[str, str, float], ...]

@dataclass(frozen=True)
class ReversalResult:
    short_term_delta: float
    long_term_delta: float
    reversed: bool
    threshold: float


def _finite(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_graph(graph: InteractionGraph) -> None:
    if not graph.nodes or len(set(graph.nodes)) != len(graph.nodes):
        raise ValueError("nodes must be non-empty and unique")
    node_set = set(graph.nodes)
    seen = set()
    for edge in graph.edges:
        if edge.source not in node_set or edge.target not in node_set:
            raise ValueError("edge endpoint must be a declared node")
        if edge.source == edge.target:
            raise ValueError("self-edges are not supported in this baseline")
        key = (edge.source, edge.target)
        if key in seen:
            raise ValueError("duplicate directed edge")
        seen.add(key)
        if not _finite(edge.base_effect) or not _finite(edge.context_sensitivity):
            raise ValueError("edge parameters must be finite")


def step(
    graph: InteractionGraph,
    states: dict[str, float],
    *,
    context: float,
    damping: float = 0.0,
) -> StepResult:
    """One synchronous update; all edges read the same prior state snapshot."""
    validate_graph(graph)
    if set(states) != set(graph.nodes):
        raise ValueError("states must cover every graph node exactly")
    if any(not _finite(v) for v in states.values()):
        raise ValueError("states must be finite")
    if not _finite(context) or not _finite(damping) or not 0 <= damping <= 1:
        raise ValueError("context must be finite and damping must be in [0,1]")
    delta = {node: 0.0 for node in graph.nodes}
    effects = []
    for edge in graph.edges:
        effect = edge.base_effect + edge.context_sensitivity * context
        delta[edge.target] += effect * states[edge.source]
        effects.append((edge.source, edge.target, effect))
    updated = {
        node: (1.0 - damping) * (states[node] + delta[node]) + damping * states[node]
        for node in graph.nodes
    }
    return StepResult(tuple(sorted(updated.items())), tuple(sorted(effects)))


def detect_reversal(short_term_delta: float, long_term_delta: float, *, threshold: float = 1e-9) -> ReversalResult:
    if not all(_finite(x) for x in (short_term_delta, long_term_delta, threshold)) or threshold < 0:
        raise ValueError("deltas must be finite and threshold non-negative")
    reversed_sign = (
        short_term_delta > threshold and long_term_delta < -threshold
    ) or (
        short_term_delta < -threshold and long_term_delta > threshold
    )
    return ReversalResult(short_term_delta, long_term_delta, reversed_sign, threshold)


def triadic_resource_demo(horizon: int = 8) -> dict:
    """Action helps an agent immediately but depletes a shared resource later."""
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 2:
        raise ValueError("horizon must be an integer >= 2")
    # Nodes: environment replenishes resource; resource benefits agent;
    # agent extraction feeds back negatively into resource.
    graph = InteractionGraph(
        ("environment", "resource", "agent"),
        (
            InteractionEdge("environment", "resource", 0.18),
            InteractionEdge("resource", "agent", 0.7),
            InteractionEdge("agent", "resource", -0.22),
        ),
    )
    baseline = {"environment": 1.0, "resource": 0.8, "agent": 0.2}
    intervention = dict(baseline)
    intervention["agent"] += 0.35
    first_base = step(graph, baseline, context=0.0, damping=0.5).states
    first_act = step(graph, intervention, context=0.0, damping=0.5).states
    first_base_map, first_act_map = dict(first_base), dict(first_act)
    short_delta = first_act_map["agent"] - first_base_map["agent"]

    base_state, act_state = dict(baseline), dict(intervention)
    for _ in range(horizon):
        base_state = dict(step(graph, base_state, context=0.0, damping=0.5).states)
        act_state = dict(step(graph, act_state, context=0.0, damping=0.5).states)
    # Score long-run agent viability jointly with retained resource.
    base_score = base_state["agent"] + 0.5 * base_state["resource"]
    act_score = act_state["agent"] + 0.5 * act_state["resource"]
    long_delta = act_score - base_score
    reversal = detect_reversal(short_delta, long_delta)
    return {
        "horizon": horizon,
        "short_term_agent_delta": short_delta,
        "long_term_joint_delta": long_delta,
        "reversal": asdict(reversal),
        "baseline_final": base_state,
        "intervention_final": act_state,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(triadic_resource_demo(args.horizon), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
