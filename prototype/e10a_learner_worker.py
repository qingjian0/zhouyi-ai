"""JSONL worker process for the E10-A relational learner.

The worker receives Support once, then only one current Query observation and
its participant objects per prediction/update. Evaluator truth is not part of
this protocol. This process boundary is a data-flow boundary, not a sandbox.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MAX_LINE_BYTES = 2 * 1024 * 1024
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace


def _write(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    learner: FiniteRelationalVersionSpace | None = None
    while True:
        raw = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_LINE_BYTES:
            _write({"request_id": None, "ok": False,
                    "error": "request_too_large"})
            return
        request: Any = None
        try:
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {
                "request_id", "operation", "payload"
            }:
                raise ValueError("invalid request envelope")
            request_id = request["request_id"]
            operation = request["operation"]
            payload = request["payload"]
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("request_id must be non-empty")
            if not isinstance(operation, str) or not isinstance(payload, dict):
                raise ValueError("invalid operation or payload")
            if operation == "fit":
                if learner is not None:
                    raise ValueError("fit may only be called once")
                learner = FiniteRelationalVersionSpace().fit(payload["support"])
                result: Any = {"fitted": True}
            elif operation == "predict":
                if learner is None:
                    raise ValueError("learner is not fitted")
                result = learner.predict(payload["observation"],
                                         payload["query_objects"])
            elif operation == "update":
                if learner is None:
                    raise ValueError("learner is not fitted")
                result = learner.update(
                    payload["observation"], payload["label"],
                    payload["query_objects"], mode=payload["mode"],
                )
            elif operation == "snapshot":
                if learner is None:
                    raise ValueError("learner is not fitted")
                result = learner.snapshot()
            elif operation == "close":
                _write({"request_id": request_id, "ok": True,
                        "result": {"closed": True}})
                return
            else:
                raise ValueError("unsupported operation")
            _write({"request_id": request_id, "ok": True, "result": result})
        except Exception as exc:
            _write({
                "request_id": request.get("request_id") if isinstance(request, dict) else None,
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })


if __name__ == "__main__":
    main()
