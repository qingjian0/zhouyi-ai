"""Parent-side JSONL client for a separate E10-A learner process.

This enforces a narrow serialized data-flow interface. It is not an OS sandbox:
the child still runs with the same user privileges and can access inherited
filesystem/network capabilities unless deployment adds external restrictions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_LINE_BYTES = 2 * 1024 * 1024


class LearnerProcessError(RuntimeError):
    pass


class SubprocessRelationalVersionSpace:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[1]
        worker = Path(__file__).with_name("e10a_learner_worker.py")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            if key in os.environ:
                env[key] = os.environ[key]
        self._process = subprocess.Popen(
            [sys.executable, "-I", str(worker)],
            cwd=str(root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="strict",
            bufsize=1,
            close_fds=True,
        )
        self._request_number = 0
        self._closed = False

    def _request(self, operation: str, payload: dict[str, Any]) -> Any:
        if self._closed or self._process.poll() is not None:
            raise LearnerProcessError("learner worker is not running")
        self._request_number += 1
        request_id = f"request-{self._request_number:08d}"
        envelope = {
            "request_id": request_id,
            "operation": operation,
            "payload": payload,
        }
        try:
            line = json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False) + "\n"
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                raise LearnerProcessError("learner IPC request exceeds size limit")
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            self._process.stdin.write(line)
            self._process.stdin.flush()
            response_line = self._process.stdout.readline(MAX_LINE_BYTES + 1)
            if not response_line:
                raise LearnerProcessError(
                    f"learner worker exited without response (code={self._process.poll()})"
                )
            if len(response_line.encode("utf-8")) > MAX_LINE_BYTES:
                raise LearnerProcessError("learner IPC response exceeds size limit")
            response = json.loads(response_line)
            if not isinstance(response, dict) or response.get("request_id") != request_id:
                raise LearnerProcessError("learner IPC response ID mismatch")
            if response.get("ok") is not True:
                raise LearnerProcessError(
                    f"learner worker rejected {operation}: "
                    f"{response.get('error_type', 'WorkerError')}: {response.get('error', 'unknown error')}"
                )
            return response.get("result")
        except Exception:
            self.close(force=True)
            raise

    def fit(self, support_payload: dict[str, Any]) -> "SubprocessRelationalVersionSpace":
        self._request("fit", {"support": support_payload})
        return self

    def predict(self, observation: dict[str, Any],
                query_objects: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("predict", {
            "observation": observation,
            "query_objects": query_objects,
        })

    def update(self, observation: dict[str, Any], label: bool,
               query_objects: list[dict[str, Any]], *,
               mode: str = "INCREMENTAL_FILTER") -> dict[str, Any]:
        return self._request("update", {
            "observation": observation,
            "label": label,
            "query_objects": query_objects,
            "mode": mode,
        })

    def snapshot(self) -> dict[str, Any]:
        return self._request("snapshot", {})

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if force:
            self._process.kill()
        elif self._process.poll() is None:
            try:
                if self._process.stdin is not None:
                    self._process.stdin.close()
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
        try:
            self._process.wait(timeout=3)
        except Exception:
            self._process.kill()

    def __enter__(self) -> "SubprocessRelationalVersionSpace":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close(force=True)
        except Exception:
            pass
