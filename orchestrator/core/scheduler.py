"""Dependency-aware async scheduler with validated atomic checkpoints."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

Handler = Callable[[dict[str, Any]], Awaitable[Any]]
_ALLOWED_STATUSES = {"pending", "running", "succeeded", "failed", "blocked"}


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    handler: str
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TaskSpec":
        if not isinstance(raw, Mapping):
            raise ValueError("each task must be an object")
        task_id, handler = raw.get("task_id"), raw.get("handler")
        depends_on = raw.get("depends_on", ())
        payload = raw.get("payload", {})
        retries = raw.get("max_retries", 0)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(handler, str) or not handler.strip():
            raise ValueError(f"{task_id}: handler must be a non-empty string")
        if not isinstance(depends_on, (list, tuple)) or not all(
            isinstance(dep, str) and dep.strip() for dep in depends_on
        ):
            raise ValueError(f"{task_id}: depends_on must contain task ID strings")
        if not isinstance(payload, dict):
            raise ValueError(f"{task_id}: payload must be an object")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"{task_id}: max_retries must be a non-negative integer")
        try:
            json.dumps(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{task_id}: payload must be JSON-serializable") from exc
        return cls(task_id, handler, tuple(depends_on), dict(payload), retries)


class TaskGraph:
    def __init__(self, tasks: list[TaskSpec]):
        self.tasks = {task.task_id: task for task in tasks}
        if len(self.tasks) != len(tasks):
            raise ValueError("task_id values must be unique")
        for task in tasks:
            if not task.task_id.strip() or not task.handler.strip():
                raise ValueError("task_id and handler must be non-empty")
            if task.max_retries < 0:
                raise ValueError(f"{task.task_id}: max_retries must be non-negative")
            if len(set(task.depends_on)) != len(task.depends_on):
                raise ValueError(f"{task.task_id}: duplicate dependencies")
            missing = set(task.depends_on) - self.tasks.keys()
            if missing:
                raise ValueError(f"{task.task_id}: unknown dependencies: {sorted(missing)}")
            if task.task_id in task.depends_on:
                raise ValueError(f"{task.task_id}: self dependency")
            try:
                json.dumps(task.payload)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{task.task_id}: payload must be JSON-serializable") from exc
        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        visiting, visited = set(), set()

        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError(f"dependency cycle detected at {key}")
            if key in visited:
                return
            visiting.add(key)
            for dep in self.tasks[key].depends_on:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in self.tasks:
            visit(key)

    def plan(self) -> list[list[str]]:
        remaining, completed, waves = set(self.tasks), set(), []
        while remaining:
            wave = sorted(
                key for key in remaining
                if set(self.tasks[key].depends_on) <= completed
            )
            if not wave:
                raise ValueError("task graph cannot make progress")
            waves.append(wave)
            completed.update(wave)
            remaining.difference_update(wave)
        return waves


class Scheduler:
    TERMINAL = {"succeeded", "failed", "blocked"}

    def __init__(
        self,
        graph: TaskGraph,
        handlers: Mapping[str, Handler],
        checkpoint: str | Path = ".zhouyi-orchestrator-state.json",
        concurrency: int = 4,
    ):
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
            raise ValueError("concurrency must be a positive integer")
        self.graph, self.handlers = graph, dict(handlers)
        self.checkpoint, self.concurrency = Path(checkpoint), concurrency
        unknown = {task.handler for task in graph.tasks.values()} - self.handlers.keys()
        if unknown:
            raise ValueError(f"unregistered handlers: {sorted(unknown)}")
        self.state = {
            key: {"status": "pending", "attempts": 0, "result": None, "error": None}
            for key in graph.tasks
        }

    def _save(self) -> None:
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=self.checkpoint.name, dir=self.checkpoint.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    {"version": 1, "tasks": self.state},
                    stream,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.checkpoint)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def resume(self) -> None:
        if not self.checkpoint.exists():
            return
        try:
            saved = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("checkpoint is unreadable or invalid JSON") from exc
        if (
            not isinstance(saved, dict)
            or saved.get("version") != 1
            or not isinstance(saved.get("tasks"), dict)
            or set(saved["tasks"]) != set(self.state)
        ):
            raise ValueError("checkpoint version or task set does not match manifest")
        restored = {}
        for key, item in saved["tasks"].items():
            if not isinstance(item, dict) or item.get("status") not in _ALLOWED_STATUSES:
                raise ValueError(f"checkpoint has invalid state for task {key}")
            attempts = item.get("attempts")
            if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
                raise ValueError(f"checkpoint has invalid attempts for task {key}")
            if item["status"] == "running":
                # At-least-once recovery: handlers may have performed side effects
                # before interruption. Handlers must therefore be idempotent.
                item = dict(item)
                item["status"] = "pending"
                item["error"] = "interrupted; retrying (handler must be idempotent)"
            restored[key] = item
        self.state.update(restored)

    async def run(self, resume: bool = False) -> dict[str, dict[str, Any]]:
        if resume:
            self.resume()
        running: dict[asyncio.Task[Any], str] = {}

        async def execute(spec: TaskSpec) -> Any:
            result = await self.handlers[spec.handler](dict(spec.payload))
            # Validate before marking success so a bad result cannot break checkpointing.
            json.dumps(result, ensure_ascii=False, allow_nan=False)
            return result

        while True:
            for key, spec in self.graph.tasks.items():
                item = self.state[key]
                if item["status"] == "pending" and any(
                    self.state[dep]["status"] in {"failed", "blocked"}
                    for dep in spec.depends_on
                ):
                    item.update(status="blocked", error="dependency failed or blocked")

            capacity = self.concurrency - len(running)
            ready = [
                spec for key, spec in self.graph.tasks.items()
                if self.state[key]["status"] == "pending"
                and all(self.state[dep]["status"] == "succeeded" for dep in spec.depends_on)
            ][:max(0, capacity)]
            for spec in ready:
                item = self.state[spec.task_id]
                item.update(status="running", error=None)
                item["attempts"] += 1
                running[asyncio.create_task(execute(spec))] = spec.task_id

            if ready or not running:
                self._save()
            if not running:
                if all(item["status"] in self.TERMINAL for item in self.state.values()):
                    break
                pending = [key for key, value in self.state.items() if value["status"] == "pending"]
                if pending:
                    raise RuntimeError(f"scheduler stalled: {pending}")
                break

            done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for future in done:
                key = running.pop(future)
                spec, item = self.graph.tasks[key], self.state[key]
                try:
                    item.update(status="succeeded", result=future.result(), error=None)
                except Exception as exc:
                    item["error"] = f"{type(exc).__name__}: {exc}"
                    item["status"] = (
                        "pending" if item["attempts"] <= spec.max_retries else "failed"
                    )
                item["updated_at"] = time.time()
                self._save()
        return self.state
