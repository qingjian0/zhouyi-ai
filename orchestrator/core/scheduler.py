"""Dependency-aware async scheduler with atomic checkpoints."""
from __future__ import annotations
import asyncio, json, os, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

Handler = Callable[[dict[str, Any]], Awaitable[Any]]

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    handler: str
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TaskSpec":
        return cls(str(raw["task_id"]), str(raw["handler"]), tuple(raw.get("depends_on", ())), dict(raw.get("payload", {})), int(raw.get("max_retries", 0)))

class TaskGraph:
    def __init__(self, tasks: list[TaskSpec]):
        self.tasks = {task.task_id: task for task in tasks}
        if len(self.tasks) != len(tasks): raise ValueError("task_id values must be unique")
        for task in tasks:
            if not task.task_id or not task.handler: raise ValueError("task_id and handler must be non-empty")
            if task.max_retries < 0: raise ValueError(f"{task.task_id}: max_retries must be non-negative")
            missing = set(task.depends_on) - self.tasks.keys()
            if missing: raise ValueError(f"{task.task_id}: unknown dependencies: {sorted(missing)}")
            if task.task_id in task.depends_on: raise ValueError(f"{task.task_id}: self dependency")
        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        visiting, visited = set(), set()
        def visit(key: str) -> None:
            if key in visiting: raise ValueError(f"dependency cycle detected at {key}")
            if key in visited: return
            visiting.add(key)
            for dep in self.tasks[key].depends_on: visit(dep)
            visiting.remove(key); visited.add(key)
        for key in self.tasks: visit(key)

    def plan(self) -> list[list[str]]:
        remaining, completed, waves = set(self.tasks), set(), []
        while remaining:
            wave = sorted(k for k in remaining if set(self.tasks[k].depends_on) <= completed)
            if not wave: raise ValueError("task graph cannot make progress")
            waves.append(wave); completed.update(wave); remaining.difference_update(wave)
        return waves

class Scheduler:
    TERMINAL = {"succeeded", "failed", "blocked"}
    def __init__(self, graph: TaskGraph, handlers: Mapping[str, Handler], checkpoint: str | Path = ".zhouyi-orchestrator-state.json", concurrency: int = 4):
        if concurrency < 1: raise ValueError("concurrency must be at least 1")
        self.graph, self.handlers = graph, dict(handlers)
        self.checkpoint, self.concurrency = Path(checkpoint), concurrency
        unknown = {t.handler for t in graph.tasks.values()} - self.handlers.keys()
        if unknown: raise ValueError(f"unregistered handlers: {sorted(unknown)}")
        self.state = {k: {"status":"pending","attempts":0,"result":None,"error":None} for k in graph.tasks}

    def _save(self) -> None:
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=self.checkpoint.name, dir=self.checkpoint.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version":1,"tasks":self.state}, stream, ensure_ascii=False, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, self.checkpoint)
        finally:
            if os.path.exists(temp): os.unlink(temp)

    def resume(self) -> None:
        if not self.checkpoint.exists(): return
        saved = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        if saved.get("version") != 1 or set(saved.get("tasks", {})) != set(self.state):
            raise ValueError("checkpoint version or task set does not match manifest")
        for key, item in saved["tasks"].items():
            if item.get("status") == "running": item["status"] = "pending"
            self.state[key] = item

    async def run(self, resume: bool = False) -> dict[str, dict[str, Any]]:
        if resume: self.resume()
        running: dict[asyncio.Task[Any], str] = {}
        async def execute(spec: TaskSpec) -> Any:
            return await self.handlers[spec.handler](dict(spec.payload))
        while True:
            for key, spec in self.graph.tasks.items():
                item = self.state[key]
                if item["status"] == "pending" and any(self.state[d]["status"] in {"failed","blocked"} for d in spec.depends_on):
                    item.update(status="blocked", error="dependency failed or blocked")
            capacity = self.concurrency - len(running)
            ready = [spec for key, spec in self.graph.tasks.items() if self.state[key]["status"] == "pending" and all(self.state[d]["status"] == "succeeded" for d in spec.depends_on)][:max(0,capacity)]
            for spec in ready:
                item = self.state[spec.task_id]; item.update(status="running",error=None); item["attempts"] += 1
                running[asyncio.create_task(execute(spec))] = spec.task_id
            if ready or not running: self._save()
            if not running:
                if all(item["status"] in self.TERMINAL for item in self.state.values()): break
                pending = [k for k,v in self.state.items() if v["status"] == "pending"]
                if pending: raise RuntimeError(f"scheduler stalled: {pending}")
                break
            done, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for future in done:
                key = running.pop(future); spec = self.graph.tasks[key]; item = self.state[key]
                try: item.update(status="succeeded",result=future.result(),error=None)
                except Exception as exc:
                    item["error"] = f"{type(exc).__name__}: {exc}"
                    item["status"] = "pending" if item["attempts"] <= spec.max_retries else "failed"
                item["updated_at"] = time.time(); self._save()
        return self.state
