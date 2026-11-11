"""Paired raw-observation analysis with auditable provenance and Student-t intervals.

The analyzer accepts multiple uniquely identified evaluation observations per scheduled task and never infers missing results. It compares treatment and baseline on matched track/seed/split/control
and resource-budget keys. Effects always retain the raw treatment-minus-baseline
sign; metric_direction describes desirability, not a sign-flipping transform.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any, Mapping, Sequence


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("analysis input must be finite JSON data") from exc


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    tiny = 1e-300
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-14:
            return h
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _student_t_cdf(t: float, degrees: int) -> float:
    x = degrees / (degrees + t * t)
    tail = 0.5 * _regularized_beta(x, degrees / 2.0, 0.5)
    return 1.0 - tail if t >= 0 else tail


def _student_t_critical_two_sided(confidence_level: float, degrees: int) -> float:
    target = (1.0 + confidence_level) / 2.0
    low, high = 0.0, 1.0
    while _student_t_cdf(high, degrees) < target:
        high *= 2.0
        if high > 1e8:
            raise ArithmeticError("could not bracket Student-t quantile")
    for _ in range(100):
        mid = (low + high) / 2.0
        if _student_t_cdf(mid, degrees) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _paired_t_interval(values: list[float], confidence_level: float) -> tuple[float, float, float]:
    n = len(values)
    if n < 2:
        raise ValueError("at least two paired observations are required")
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    standard_error = math.sqrt(variance / n)
    critical = _student_t_critical_two_sided(confidence_level, n - 1)
    margin = critical * standard_error
    return mean, mean - margin, mean + margin



def task_manifest_from_specs(tasks: Sequence[Any]) -> list[dict[str, Any]]:
    """Extract analyzer identity fields from ExperimentMatrix TaskSpec objects."""
    manifest = []
    for index, task in enumerate(tasks):
        task_id = getattr(task, "task_id", None)
        payload = getattr(task, "payload", None)
        if not isinstance(task_id, str) or not isinstance(payload, Mapping):
            raise ValueError(f"tasks[{index}] must be a TaskSpec-like object")
        required = {"track", "condition", "seed"}
        if not required <= payload.keys():
            raise ValueError(f"tasks[{index}] payload lacks track/condition/seed")
        manifest.append({"task_id": task_id, "track": payload["track"],
                         "condition": payload["condition"], "seed": payload["seed"]})
    if not manifest:
        raise ValueError("tasks must not be empty")
    return manifest


def analyze_raw_observations(
    observations: Sequence[Mapping[str, Any]],
    *,
    task_manifest: Sequence[Mapping[str, Any]],
    task_set_digest: str,
    treatment_condition: str,
    baseline_condition: str,
    metric: str,
    metric_direction: str,
    predicted_direction: str = "positive",
    min_seeds: int = 10,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Create evidence rows from matched raw task observations.

    Required observation keys: observation_id, task_id, split, control, metric, metric_value,
    status, preregistered, parameter_count, compute_budget, split_source,
    control_family. Track/condition/seed are read from the authoritative
    task_manifest generated from ExperimentMatrix.to_tasks().
    """
    if not isinstance(task_set_digest, str) or not task_set_digest.strip():
        raise ValueError("task_set_digest must be a non-empty string")
    for name, value in (("treatment_condition", treatment_condition),
                        ("baseline_condition", baseline_condition), ("metric", metric)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if treatment_condition == baseline_condition:
        raise ValueError("treatment and baseline conditions must differ")
    if not isinstance(metric_direction, str) or metric_direction not in {"higher", "lower"}:
        raise ValueError("metric_direction must be higher or lower")
    if not isinstance(predicted_direction, str) or predicted_direction not in {"positive", "negative"}:
        raise ValueError("predicted_direction must be positive or negative")
    if isinstance(min_seeds, bool) or not isinstance(min_seeds, int) or min_seeds < 2:
        raise ValueError("min_seeds must be an integer >= 2")
    if isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float)) or not 0.5 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0.5 and 1")

    manifest: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(task_manifest):
        if not isinstance(item, Mapping):
            raise ValueError(f"task_manifest[{index}] must be an object")
        task_id, track, condition, seed = (item.get("task_id"), item.get("track"),
                                            item.get("condition"), item.get("seed"))
        if not all(isinstance(x, str) and x.strip() for x in (task_id, track, condition)):
            raise ValueError(f"task_manifest[{index}] has invalid identity fields")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"task_manifest[{index}].seed must be a non-negative integer")
        if task_id in manifest:
            raise ValueError(f"duplicate task ID in manifest: {task_id}")
        manifest[task_id] = {"track": track, "condition": condition, "seed": seed}
    if not manifest:
        raise ValueError("task_manifest must not be empty")

    seen_observations: set[str] = set()
    seen_task_ids: set[str] = set()
    seen_task_dimensions: set[tuple[str, str, str]] = set()
    joined: dict[tuple[Any, ...], dict[str, Any]] = {}
    required = {"observation_id", "task_id", "split", "control", "metric", "metric_value", "status",
                "preregistered", "parameter_count", "compute_budget", "split_source",
                "control_family"}
    excluded: list[dict[str, str]] = []
    for index, raw in enumerate(observations):
        if not isinstance(raw, Mapping) or not required <= raw.keys():
            raise ValueError(f"observations[{index}] is missing required fields")
        task_id = raw["task_id"]
        observation_id = raw["observation_id"]
        if not isinstance(task_id, str) or task_id not in manifest:
            raise ValueError(f"observations[{index}] references unknown task_id")
        if not isinstance(observation_id, str) or not observation_id.strip():
            raise ValueError(f"observations[{index}].observation_id must be non-empty")
        if observation_id in seen_observations:
            raise ValueError(f"duplicate observation_id: {observation_id}")
        seen_observations.add(observation_id)
        seen_task_ids.add(task_id)
        meta = manifest[task_id]
        split, control = raw["split"], raw["control"]
        if (not isinstance(split, str) or split not in {"iid", "ood"} or not isinstance(control, str) or control not in {"none", "shuffled", "random"}):
            raise ValueError(f"{task_id}: unsupported split or control")
        if raw["metric"] != metric:
            raise ValueError(f"{task_id}: metric mismatch")
        task_dimension = (task_id, split, control)
        if task_dimension in seen_task_dimensions:
            raise ValueError(f"duplicate task/split/control observation: {task_dimension}")
        seen_task_dimensions.add(task_dimension)
        if not isinstance(raw["status"], str):
            raise ValueError(f"{task_id}: status must be a string")
        if not isinstance(raw["preregistered"], bool):
            raise ValueError(f"{task_id}: preregistered must be boolean")
        if not isinstance(raw["split_source"], str) or not raw["split_source"].strip():
            raise ValueError(f"{task_id}: split_source is required")
        if split == "ood" and "ood" not in raw["split_source"].lower():
            raise ValueError(f"{task_id}: OOD split requires OOD provenance")
        if raw["control_family"] != control:
            raise ValueError(f"{task_id}: control_family mismatch")
        parameter_count = raw["parameter_count"]
        if isinstance(parameter_count, bool) or not isinstance(parameter_count, int) or parameter_count < 0:
            raise ValueError(f"{task_id}: parameter_count must be a non-negative integer")
        compute_budget = _number(raw["compute_budget"], "compute_budget")
        if compute_budget <= 0:
            raise ValueError(f"{task_id}: compute_budget must be positive")
        if raw["status"] != "succeeded":
            excluded.append({"task_id": task_id, "observation_id": observation_id, "reason": "task_not_succeeded"})
            continue
        value = _number(raw["metric_value"], "metric_value")
        key = (meta["track"], meta["seed"], split, control, parameter_count, compute_budget)
        bucket = joined.setdefault(key, {})
        condition = meta["condition"]
        if condition not in {treatment_condition, baseline_condition}:
            excluded.append({"task_id": task_id, "observation_id": observation_id, "reason": "condition_not_in_contrast"})
            continue
        if condition in bucket:
            raise ValueError(f"duplicate condition in matched pair: {key}")
        bucket[condition] = {"task_id": task_id, "observation_id": observation_id, "value": value,
                             "preregistered": raw["preregistered"],
                             "split_source": raw["split_source"]}

    groups: dict[tuple[str, str, str, int, float], list[dict[str, Any]]] = defaultdict(list)
    for key, pair in joined.items():
        track, seed, split, control, parameter_count, compute_budget = key
        if set(pair) != {treatment_condition, baseline_condition}:
            excluded.extend({"task_id": item["task_id"], "observation_id": item["observation_id"], "reason": "unmatched_pair"}
                            for item in pair.values())
            continue
        treatment, baseline = pair[treatment_condition], pair[baseline_condition]
        # Preserve the conventional raw estimand: treatment minus baseline.
        # Whether a positive effect is desirable is determined by metric_direction.
        delta = treatment["value"] - baseline["value"]
        groups[(track, split, control, parameter_count, compute_budget)].append({
            "seed": seed, "delta": delta,
            "task_ids": [treatment["task_id"], baseline["task_id"]],
            "observation_ids": [treatment["observation_id"], baseline["observation_id"]],
            "preregistered": treatment["preregistered"] and baseline["preregistered"],
            "split_source": treatment["split_source"],
            "parameter_count": parameter_count, "compute_budget": compute_budget,
        })

    evidence_rows = []
    for (track, split, control, parameter_count, compute_budget), pairs in sorted(groups.items()):
        pairs.sort(key=lambda item: item["seed"])
        if len(pairs) < 2:
            excluded.extend({"task_id": task_id, "observation_id": observation_id, "reason": "fewer_than_two_matched_seeds"}
                            for pair in pairs for task_id, observation_id in zip(pair["task_ids"], pair["observation_ids"]))
            continue
        values = [pair["delta"] for pair in pairs]
        mean, lower, upper = _paired_t_interval(values, float(confidence_level))
        seeds = [pair["seed"] for pair in pairs]
        task_ids = [task_id for pair in pairs for task_id in pair["task_ids"]]
        observation_ids = [observation_id for pair in pairs for observation_id in pair["observation_ids"]]
        evidence_id = hashlib.sha256(_canonical({
            "task_set_digest": task_set_digest, "track": track, "split": split,
            "control": control, "treatment": treatment_condition,
            "baseline": baseline_condition, "metric": metric, "parameter_count": parameter_count, "compute_budget": compute_budget,
        })).hexdigest()[:20]
        evidence_rows.append({
            "evidence_id": evidence_id, "track": track, "split": split,
            "control": control, "effect_mean": mean, "ci_lower": lower,
            "ci_upper": upper, "seeds": len(seeds), "valid": len(seeds) >= min_seeds,
            "preregistered": all(pair["preregistered"] for pair in pairs),
            "task_ids": task_ids,
            "observation_ids": observation_ids,
            "expected_seeds": sorted({item["seed"] for item in manifest.values()
                                      if item["track"] == track and item["condition"] in
                                      {treatment_condition, baseline_condition}}),
            "observed_seeds": seeds, "metric": metric,
            "metric_direction": metric_direction,
            "effect_direction": predicted_direction,
            "split_source": pairs[0]["split_source"],
            "control_family": control,
            "parameter_count": parameter_count,
            "compute_budget": compute_budget,
            "confidence_level": float(confidence_level),
            "interval_method": "paired Student-t confidence interval",
        })

    return {
        "schema_version": 1, "analysis_kind": "paired_raw_observation_analysis",
        "task_set_digest": task_set_digest,
        "input_observation_digest": hashlib.sha256(_canonical(list(observations))).hexdigest(),
        "manifest_task_count": len(manifest), "observed_task_count": len(seen_task_ids),
        "observation_count": len(seen_observations),
        "missing_task_ids": sorted(set(manifest) - seen_task_ids),
        "treatment_condition": treatment_condition,
        "baseline_condition": baseline_condition, "metric": metric,
        "metric_direction": metric_direction, "predicted_direction": predicted_direction,
        "min_seeds": min_seeds, "confidence_level": float(confidence_level),
        "evidence_rows": evidence_rows, "excluded": excluded,
        "limitations": [
            "Intervals assume independent, approximately normal paired differences; inspect raw distributions and outliers.",
            "The analyzer does not establish that task manifests, split labels, budgets or preregistration claims are truthful.",
            "Only exact matched track/seed/split/control/parameter-count/compute-budget pairs contribute.",
            "Missing, failed, unmatched and non-contrast tasks are never silently imputed.",
            "Multiple comparisons, power analysis and preregistration governance remain separate responsibilities.",
        ],
    }
