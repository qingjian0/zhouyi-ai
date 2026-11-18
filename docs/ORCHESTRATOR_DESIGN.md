# Hyper-Speed R&D Orchestrator — P0

## Purpose
Add an external research-and-engineering scheduler without changing the CPG-EI runtime. It coordinates explicitly registered task handlers; model-provider adapters and repository-writing agents are later, separately permissioned integrations.

## P0 scope
- Declarative task manifests and dependency DAG validation.
- Parallel execution of independent tasks with a configurable concurrency cap.
- Dependency-aware scheduling; failed dependencies block descendants.
- Per-task bounded retries and atomic JSON checkpoints.
- Dry planning output and deterministic tests.
- Safe handler registry: no arbitrary shell execution and no implicit repository write access.

## Execution contract
Each task has task_id, handler, optional depends_on, payload, and max_retries. A task becomes eligible only after all dependencies succeed. Failed dependencies block descendants. Checkpoints are atomically replaced after state transitions. Task payloads and results must be JSON-serializable.

## Resume and delivery semantics
A checkpoint is accepted only when its version and task IDs match the current manifest. Tasks left running at interruption return to pending; completed tasks remain completed. Failed and blocked tasks remain terminal on resume. Use a fresh checkpoint when intentionally changing a manifest. Recovery is **at-least-once**, not exactly-once: a handler may have performed an external side effect before interruption. Therefore, handlers must be idempotent (for example, use task_id as an idempotency key) or explicitly reconcile their side effects before retrying.

## Security boundaries
No eval, arbitrary shell commands, or dynamic imports. Handlers receive a copy of their JSON payload. Repository modifications require later branch-scoped adapters. Secrets must never be stored in manifests or checkpoints.

## Next phases
P1: agent protocol, provider adapters, artifact contracts, isolated workspaces.
P2: experiment registry, matrix execution, metrics and reproducibility metadata.
P3: autonomous gap detection, replanning, budget controls and approval gates.

## Current limitation
The included record handler is a wiring/demo handler, not an AI agent. P0 proves orchestration mechanics; it does not itself create model intelligence or guarantee a speedup. Measure throughput against serial execution on representative workloads.
