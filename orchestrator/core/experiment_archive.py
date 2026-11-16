"""Append-only JSON archive for benchmark reports."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("archive data must be finite JSON values") from exc

def archive_benchmark_report(report: Mapping[str, Any], archive_dir: str | Path, *, run_id: str, code_revision: str | None = None) -> dict[str, Any]:
    """Persist one report without overwriting an existing run ID."""
    if not isinstance(run_id, str) or not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise ValueError("run_id must contain only letters, digits, hyphens and underscores")
    if not isinstance(report, Mapping):
        raise ValueError("report must be a mapping")
    report_bytes = _canonical(dict(report))
    envelope = {
        "archive_schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_revision": code_revision,
        "environment": {"python": sys.version, "implementation": platform.python_implementation(), "platform": platform.platform()},
        "task_set_digest": report.get("task_set_digest"),
        "report_digest": hashlib.sha256(report_bytes).hexdigest(),
        "report": json.loads(report_bytes),
    }
    data = _canonical(envelope) + b"\n"
    root = Path(archive_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{run_id}.json"
    temp = root / f".{run_id}.{os.getpid()}.tmp"
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, target)
    except FileExistsError as exc:
        raise FileExistsError(f"archive run already exists: {run_id}") from exc
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return {"run_id": run_id, "path": str(target), "report_digest": envelope["report_digest"], "task_set_digest": envelope["task_set_digest"]}