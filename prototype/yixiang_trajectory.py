"""Order-preserving trajectory analogy over situated Yixiang snapshots.

The evaluator consumes explicit annotations and an explicit entity mapping.
It finds a maximum monotone alignment of compatible snapshots; it does not
infer causality, interpolate missing states, or discover mappings.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from prototype.yixiang_situated import YixiangSituation, compare_situations

@dataclass(frozen=True)
class TrajectoryAlignment:
    accepted: bool
    matched_pairs: tuple[tuple[int, int], ...]
    skipped_source: tuple[int, ...]
    skipped_target: tuple[int, ...]
    source_coverage: float
    target_coverage: float
    reason_codes: tuple[str, ...]

def _validate_trajectory(items: tuple[YixiangSituation, ...], label: str) -> None:
    if not isinstance(items, tuple) or not items:
        raise ValueError(f"{label} trajectory must be a non-empty tuple")
    ids = set()
    previous_step = None
    for item in items:
        if not isinstance(item, YixiangSituation):
            raise ValueError(f"{label} trajectory contains a non-situation")
        if item.situation_id in ids:
            raise ValueError(f"{label} situation ids must be unique")
        ids.add(item.situation_id)
        if previous_step is not None and item.step <= previous_step:
            raise ValueError(f"{label} steps must be strictly increasing")
        previous_step = item.step

def align_trajectories(
    source: tuple[YixiangSituation, ...],
    target: tuple[YixiangSituation, ...],
    *,
    entity_mapping: Mapping[str, str],
    required_context: tuple[str, ...],
    min_source_coverage: float = 1.0,
    min_target_coverage: float = 1.0,
    require_same_position: bool = False,
    require_same_stage: bool = False,
) -> TrajectoryAlignment:
    """Maximum-cardinality monotone alignment; intermediate snapshots may be skipped."""
    _validate_trajectory(source, "source")
    _validate_trajectory(target, "target")
    for name, value in (("min_source_coverage", min_source_coverage),
                        ("min_target_coverage", min_target_coverage)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise ValueError(f"{name} must be in (0, 1]")
    n, m = len(source), len(target)
    compatible = [[False] * m for _ in range(n)]
    for i, left in enumerate(source):
        for j, right in enumerate(target):
            compatible[i][j] = compare_situations(
                left, right, entity_mapping=entity_mapping,
                required_context=required_context,
                require_same_position=require_same_position,
                require_same_stage=require_same_stage,
            ).accepted
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    choice = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            up, left = dp[i - 1][j], dp[i][j - 1]
            best = max(up, left)
            if compatible[i - 1][j - 1] and dp[i - 1][j - 1] + 1 >= best:
                best = dp[i - 1][j - 1] + 1
                choice[i][j] = "match"
            elif up >= left:
                choice[i][j] = "skip_source"
            else:
                choice[i][j] = "skip_target"
            dp[i][j] = best
    pairs = []
    i, j = n, m
    while i and j:
        action = choice[i][j]
        if action == "match":
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif action == "skip_source":
            i -= 1
        elif action == "skip_target":
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    matched_source = {a for a, _ in pairs}
    matched_target = {b for _, b in pairs}
    skipped_source = tuple(k for k in range(n) if k not in matched_source)
    skipped_target = tuple(k for k in range(m) if k not in matched_target)
    source_coverage, target_coverage = len(pairs) / n, len(pairs) / m
    reasons = []
    if source_coverage < min_source_coverage:
        reasons.append("SOURCE_COVERAGE_BELOW_THRESHOLD")
    if target_coverage < min_target_coverage:
        reasons.append("TARGET_COVERAGE_BELOW_THRESHOLD")
    if not pairs:
        reasons.append("NO_ORDERED_COMPATIBLE_SNAPSHOTS")
    return TrajectoryAlignment(not reasons, tuple(pairs), skipped_source,
        skipped_target, source_coverage, target_coverage, tuple(reasons))
