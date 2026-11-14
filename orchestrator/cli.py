"""CLI for planning and running JSON task manifests."""
import argparse, asyncio, json
from pathlib import Path
from typing import Any
from orchestrator.core.scheduler import Scheduler, TaskGraph, TaskSpec

async def record(payload: dict[str, Any]) -> dict[str, Any]:
    return {"recorded": True, "payload": payload}

def main() -> None:
    parser = argparse.ArgumentParser(description="Zhouyi-AI R&D orchestrator")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint", type=Path, default=Path(".zhouyi-orchestrator-state.json"))
    args = parser.parse_args(); raw = json.loads(args.manifest.read_text(encoding="utf-8"))
    graph = TaskGraph([TaskSpec.from_dict(x) for x in raw.get("tasks", [])])
    if args.plan:
        print(json.dumps(graph.plan(), ensure_ascii=False, indent=2)); return
    scheduler = Scheduler(graph, {"record": record}, args.checkpoint, int(raw.get("concurrency",4)))
    result = asyncio.run(scheduler.run(resume=args.resume))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(v["status"] in {"failed","blocked"} for v in result.values()): raise SystemExit(1)

if __name__ == "__main__": main()
