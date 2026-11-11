# Hyper-Speed R&D Orchestrator v2 — Architecture and Acceptance Plan

Date: 2026-11-11  
Status: design proposal; no performance claim  
Branch: research/hyper-speed-orchestrator-v2-design-2026-11-11  
Parent: feature/hyper-speed-orchestrator-p0

## 1. Executive decision

Keep the existing P0 scheduler small and deterministic. Do not turn it into a general-purpose execution engine. Build v2 as a layered research-workflow coordinator with four separable planes:

1. **Control plane** — DAG validation, task admission, priorities, cancellation, deadlines, retry policy and adaptive concurrency.
2. **Execution plane** — registered handlers, provider-neutral agent calls, experiment runners and isolated workspaces.
3. **Evidence plane** — immutable task events, content-addressed artifacts, experiment manifests, metrics and provenance.
4. **Governance plane** — capability-scoped permissions, patch validation, independent review and explicit approval gates.

The orchestrator accelerates research throughput; it is not itself the CPG-EI cognitive architecture and does not establish model intelligence.

## 2. Why P0 is not yet "hyper-speed"

P0 already provides dependency-aware async execution, a concurrency cap, bounded retries, atomic JSON checkpoints, resume, a safe handler registry and a plan-only CLI. This is a useful scheduler foundation.

The current design does not yet provide:
- workload/resource-aware admission or adaptive concurrency;
- experiment matrix expansion and seed-level fan-out;
- cache keys tied to code, data, config and environment;
- explicit timeouts, cancellation propagation or task deadlines;
- durable append-only attempt/event history;
- manifest digest validation on resume;
- queue priority/fairness across research tracks;
- provider quotas, token/cost budgets or rate-limit backpressure;
- a reproducible serial-vs-parallel throughput benchmark.

Therefore no numeric speedup should be claimed until these mechanisms are implemented and measured.

## 3. Target workflow

A research program is compiled into a versioned task DAG:

```text
Research question
  -> protocol + preregistration
  -> generator / dataset validation
  -> baseline matrix
  -> candidate matrix (seed x condition x model)
  -> metric aggregation
  -> independent audit
  -> synthesis and next-gap proposal
```

Each stage emits typed artifacts. Downstream stages consume artifact references and declared metadata, not hidden in-memory mutable objects. The same experiment manifest must be runnable serially and in parallel.

## 4. Task contract v2

Every task should declare:

- `task_id`, `handler_id`, `handler_version`;
- `depends_on` and optional `priority`;
- immutable JSON payload and input artifact digests;
- `resource_class` (CPU, memory, provider-call, IO, GPU);
- `timeout_seconds`, `deadline`, `max_attempts`;
- idempotency key and retry classification;
- capability requirements (read artifact, write task workspace, call provider);
- expected output schema and acceptance predicate;
- experiment identity: protocol version, code commit, data digest, seed, condition.

Reject unknown fields in strict manifest versions. Compute a canonical manifest digest. Resume is permitted only when the manifest digest, scheduler schema, and handler versions match; otherwise require an explicit migration or fresh checkpoint.

## 5. Scheduling policy

### 5.1 Ready queue

Use a priority queue with deterministic tie-breaking:
1. dependency readiness;
2. deadline urgency;
3. explicit research priority;
4. estimated critical-path reduction;
5. stable task ID.

Avoid starvation by aging lower-priority tasks. Keep deterministic mode available for reproducibility.

### 5.2 Resource-aware admission

Replace one global concurrency number with independent budgets:
- CPU worker slots;
- memory reservation;
- provider concurrency and requests/minute;
- provider token/cost budget;
- GPU slots / VRAM reservation;
- IO slots.

A task is admitted only if all declared resource reservations are available. Resource estimates must be measured or conservatively configured; do not infer GPU availability from task labels alone.

### 5.3 Adaptive concurrency

Start with a conservative per-resource cap. Adjust only from observed telemetry:
- queue wait time;
- task service time;
- CPU and memory pressure;
- provider throttling / 429 rate;
- timeout and retry rate;
- throughput and tail latency.

Use bounded additive increase / multiplicative decrease. Reduce concurrency quickly under throttling or memory pressure; increase slowly after a stable observation window. Keep hard maximums and an operator override. Adaptive mode must never change experiment semantics or seed allocation.

### 5.4 Critical path and batching

Prioritize tasks that shorten the DAG critical path. Batch only tasks whose handler declares batch equivalence and whose outputs can be mapped back to individual task IDs. For seed sweeps, fan out independent seeds, then aggregate only after every expected seed has a terminal status.

Do not batch heterogeneous tasks merely to reduce orchestration overhead.

## 6. Reliability and recovery

- Use explicit task states: PENDING, READY, RUNNING, SUCCEEDED, FAILED, BLOCKED, CANCELLED, TIMED_OUT.
- Persist every attempt as an append-only event; derive the current projection from events.
- Use leases/heartbeats for long-running remote work. Expired leases become recoverable, but retries remain at-least-once.
- Require idempotency keys for side-effecting handlers. Never describe recovery as exactly-once.
- Classify retryable errors (transient network, provider throttling, worker loss) separately from permanent errors (schema failure, invalid input, deterministic test failure).
- Apply exponential backoff with jitter and respect provider retry-after headers.
- Cancellation stops admission first, then requests cooperative cancellation, then records any non-cooperative worker as uncertain rather than claiming it stopped.
- Store checkpoints with atomic replacement and manifest/schema digests. Verify artifact hashes on every read.

## 7. Experiment registry and cache

An experiment run identity is:

`H(code_commit, protocol_version, data_digest, config_digest, seed, environment_fingerprint)`

Cache only pure, deterministic stages whose complete inputs are represented in the key. Never cache hidden evaluator state, unlocked test outcomes, provider outputs without an explicit policy, or nondeterministic tasks as if they were reproducible.

Keep raw per-seed outputs immutable. Aggregates are derived artifacts and must record exactly which seed artifacts they include. Missing or failed seeds cannot silently disappear from denominators.

## 8. Agent collaboration and multi-model work

Use the provider-neutral Agent Protocol as the adapter boundary. Research, architecture, implementation, experiment and review roles are task contracts, not assumed separate model instances.

A multi-agent DAG should look like:

```text
parallel research tracks
  -> evidence normalization
  -> architecture synthesis
  -> implementation proposal
  -> isolated patch artifact
  -> tests + independent review
  -> human approval bound to patch digest
```

Do not send private chain-of-thought between agents. Exchange concise rationale, claims, evidence references, metrics, artifacts and blockers. Model disagreement is evidence to preserve, not noise to average away.

## 9. Security boundary

The orchestrator must not gain ambient repository or host authority.

- No arbitrary shell execution in the core scheduler.
- No dynamic imports from task payloads.
- Explicit handler registration and capability checks.
- Task-scoped workspace roots; reject path traversal and symlink escapes.
- Separate evaluator truth from learner-visible payloads.
- Provider credentials injected only at runtime from a secret manager.
- Repository writes occur only through a separately permissioned branch adapter.
- Patch application, test execution and merge each have distinct gates.
- Human approval must bind to the exact commit/patch digest, not a mutable branch name.
- This design is not an OS sandbox; use OS/container isolation, resource limits and trusted runners for untrusted code.

## 10. Performance measurement protocol

Benchmark the same manifest in serial and parallel modes on identical hardware and inputs.

Report:
- wall-clock makespan and speedup (T_{serial}/T_{parallel});
- total CPU time and peak memory;
- throughput (completed tasks / second);
- p50/p95 task latency and queue wait;
- provider calls, tokens and cost;
- retry, timeout and failure rates;
- cache hit rate and cold/warm results;
- critical-path length and utilization by resource class.

Use at least 5 independent repetitions for timing-sensitive comparisons, report median and dispersion, and preserve raw run records. Include tiny DAGs where scheduling overhead dominates, balanced independent matrices, skewed workloads, provider-limited workloads and memory-constrained workloads.

A speedup claim is accepted only if correctness/output digests match the serial reference and the improvement reproduces across workloads. Parallelism may increase total compute or cost even when wall time falls; report both.

## 11. Implementation phases

### P0 — existing foundation
DAG validation, async execution, bounded retries, atomic checkpoint, resume, safe registered handlers and plan-only CLI.

### P1 — finish collaboration boundary
Typed request/result/artifact contracts, provider adapter interface, task-scoped workspace and conservative patch validation. Keep provider credentials and repository writes outside the scheduler.

### P2 — experiment matrix
Versioned experiment manifest, seed/condition fan-out, per-seed artifacts, deterministic aggregation, resource classes and serial reference runner.

### P3 — resilient adaptive scheduler
Deadlines, cancellation, leases, append-only event log, manifest digest, classified retry/backoff, resource-aware admission and telemetry-driven bounded concurrency.

### P4 — reproducibility and caching
Content-addressed data/artifact store, complete cache keys, environment fingerprints, cache audit and immutable experiment ledger.

### P5 — autonomous research loop
Gap detection from failed acceptance criteria, proposal generation, budgeted task-graph replanning, independent audit and approval-gated branch delivery.

Do not start P5 before P2/P3 reliability and measurement gates pass.

## 12. Acceptance gates

- **G1 Correctness:** all existing tests pass; deterministic scheduler tests cover dependency failure, timeout, cancellation, retry classification, resume, manifest mismatch and concurrent checkpoint safety.
- **G2 Reproducibility:** serial and parallel executions produce identical canonical outputs for deterministic tasks.
- **G3 Throughput:** publish measured results across the workload matrix; no fixed speedup target before baseline data.
- **G4 Resource safety:** enforce CPU/memory/provider/GPU limits and prove backpressure under saturation.
- **G5 Security:** path traversal, symlink escape, unregistered handler, secret leakage and patch-digest mutation tests pass.
- **G6 Research integrity:** evaluator truth and locked-test labels remain outside learner-facing task payloads; raw per-seed artifacts remain available.
- **G7 Governance:** no automatic merge to main; branch-scoped writes and human approval bound to exact patch digest.

## 13. Immediate implementation order

1. Add manifest schema v2 and canonical digest; reject unsafe resume on mismatch.
2. Add timeout/cancellation states and explicit retry classification.
3. Add resource-class admission while retaining the current global concurrency option as a compatibility default.
4. Add a matrix runner that expands `seeds x conditions x tracks` into deterministic tasks.
5. Add serial/parallel benchmark and output-digest equivalence checks.
6. Add event ledger and artifact cache only after the matrix runner has stable contracts.

## 14. Explicit non-claims

This design does not claim:
- a measured speedup;
- an autonomous coding agent already connected to a real model provider;
- exactly-once task execution;
- an OS-level security sandbox;
- that parallel agents improve answer quality;
- that orchestrator throughput translates directly into better CPG-EI cognition.

The next milestone is a reproducible experiment-matrix runner with serial equivalence, not a larger number of loosely coordinated agents.
