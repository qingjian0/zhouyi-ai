"""Validate archived experiment provenance before evaluating evidence rows."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from .evidence import evaluate_evidence


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("archive contains non-canonical JSON data") from exc


def evaluate_archived_evidence(
    archive_path: str | Path,
    *,
    expected_task_set_digest: str,
    predicted_direction: str,
    min_seeds: int = 10,
) -> dict[str, Any]:
    """Evaluate only archived, digest-verified, provenance-complete evidence."""
    if not isinstance(expected_task_set_digest, str) or not expected_task_set_digest:
        raise ValueError("expected_task_set_digest must be a non-empty string")
    path = Path(archive_path)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read experiment archive: {path}") from exc
    if not isinstance(envelope, dict) or envelope.get("archive_schema_version") != 1:
        raise ValueError("unsupported archive envelope")
    report = envelope.get("report")
    if not isinstance(report, dict):
        raise ValueError("archive report must be an object")
    actual_report_digest = hashlib.sha256(_canonical(report)).hexdigest()
    if envelope.get("report_digest") != actual_report_digest:
        raise ValueError("archive report digest mismatch")
    if envelope.get("task_set_digest") != expected_task_set_digest or report.get("task_set_digest") != expected_task_set_digest:
        raise ValueError("task-set digest mismatch")
    rows = report.get("evidence_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("archive report must contain non-empty evidence_rows")

    evaluator_rows = []
    seen_observations: set[str] = set()
    seen_tasks: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"evidence_rows[{index}] must be an object")
        required = {"task_ids", "observation_ids", "expected_seeds", "observed_seeds", "metric", "metric_direction", "split_source", "control_family"}
        if not required <= row.keys():
            raise ValueError(f"evidence_rows[{index}] is missing provenance fields")
        task_ids = row["task_ids"]
        expected_seeds = row["expected_seeds"]
        observed_seeds = row["observed_seeds"]
        if not isinstance(task_ids, list) or not task_ids or any(not isinstance(x, str) or not x for x in task_ids) or len(set(task_ids)) != len(task_ids):
            raise ValueError(f"evidence_rows[{index}].task_ids must be unique non-empty strings")
        seen_tasks.update(task_ids)
        observation_ids = row["observation_ids"]
        if (not isinstance(observation_ids, list) or len(observation_ids) != len(task_ids)
                or any(not isinstance(x, str) or not x for x in observation_ids)
                or len(set(observation_ids)) != len(observation_ids)):
            raise ValueError(f"evidence_rows[{index}].observation_ids must uniquely match task_ids")
        observation_overlap = seen_observations.intersection(observation_ids)
        if observation_overlap:
            raise ValueError(f"observation IDs reused across evidence rows: {sorted(observation_overlap)}")
        seen_observations.update(observation_ids)
        if not isinstance(expected_seeds, list) or not expected_seeds or any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in expected_seeds) or len(set(expected_seeds)) != len(expected_seeds):
            raise ValueError(f"evidence_rows[{index}].expected_seeds must be unique non-negative integers")
        if not isinstance(observed_seeds, list) or any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in observed_seeds) or len(set(observed_seeds)) != len(observed_seeds):
            raise ValueError(f"evidence_rows[{index}].observed_seeds must be unique non-negative integers")
        if set(observed_seeds) - set(expected_seeds):
            raise ValueError(f"evidence_rows[{index}] contains unexpected observed seeds")
        if len(observed_seeds) != row.get("seeds"):
            raise ValueError(f"evidence_rows[{index}] seed count does not match observed seeds")
        if not isinstance(row["metric"], str) or not row["metric"].strip():
            raise ValueError(f"evidence_rows[{index}].metric must be non-empty")
        # New schema separates raw metric polarity from the hypothesized effect direction.
        if "effect_direction" in row:
            if row["effect_direction"] != predicted_direction:
                raise ValueError(f"evidence_rows[{index}] effect direction conflicts with hypothesis")
            if row["metric_direction"] not in {"higher", "lower"}:
                raise ValueError(f"evidence_rows[{index}] metric direction must be higher or lower")
        elif row["metric_direction"] != predicted_direction:
            raise ValueError(f"evidence_rows[{index}] legacy metric direction conflicts with hypothesis")
        if not isinstance(row["split_source"], str) or not row["split_source"].strip():
            raise ValueError(f"evidence_rows[{index}].split_source is required")
        if row["split"] == "ood" and "ood" not in row["split_source"].lower():
            raise ValueError(f"evidence_rows[{index}] OOD split lacks OOD provenance")
        expected_control = row["control"]
        if expected_control in {"shuffled", "random"} and row["control_family"] != expected_control:
            raise ValueError(f"evidence_rows[{index}] control family mismatch")
        evaluator_rows.append({key: row[key] for key in ("evidence_id", "split", "control", "effect_mean", "ci_lower", "ci_upper", "seeds", "valid", "preregistered")})

    result = evaluate_evidence(predicted_direction=predicted_direction, evidence=evaluator_rows, min_seeds=min_seeds)
    result["archive"] = {
        "run_id": envelope.get("run_id"),
        "report_digest": actual_report_digest,
        "task_set_digest": expected_task_set_digest,
        "code_revision": envelope.get("code_revision"),
        "evidence_row_count": len(evaluator_rows),
        "unique_task_count": len(seen_tasks),
        "unique_observation_count": len(seen_observations),
    }
    result["limitations"].append("Provenance fields are structurally checked, but their truth depends on the archive producer and raw-run audit.")
    return result
