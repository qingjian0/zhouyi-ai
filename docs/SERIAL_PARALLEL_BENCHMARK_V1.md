# Serial / Parallel Benchmark v1

Status: implementation candidate; local execution and CI validation pending.

## Contract

The benchmark accepts one already-expanded TaskSpec list and one handler
mapping. It executes that exact task set with concurrency 1 and with a
configurable parallelism >= 2. Every repetition uses a fresh Scheduler,
TaskGraph and isolated checkpoint path. The execution order alternates by
repetition to reduce simple warm-up/order bias.

## Handler requirements

Handlers must be deterministic and side-effect-free, or explicitly
idempotent. The scheduler may retry handlers according to TaskSpec policy;
the benchmark repeats every task several times. Do not use this harness for
non-idempotent external actions such as charging, sending messages, or
mutating a shared remote resource.

## Equivalence

The result projection includes each task's terminal status, JSON result and
error. It excludes attempts and timestamps. Canonical JSON (sorted keys,
compact separators, finite numbers only) is hashed per run. A comparison is
equivalent only when each serial/parallel pair matches and all repetitions
within each mode are repeatable.

## Metrics

The report includes per-run wall-clock seconds, task counts, success/failure/
blocked counts, output digests, median serial and parallel wall time, and
descriptive speedup = serial median / parallel median. A speedup value is not
a reasoning-quality metric and is not meaningful when outputs differ.

## Limitations

- This is an in-process async benchmark, not a multi-process or distributed
  scheduler benchmark.
- CPU, memory, Python version, machine identity and system load are not
  currently sampled; record them externally for publishable comparisons.
- Checkpoints are temporary and deleted after the call; this harness is not
  a durable experiment archive.
- The harness does not guarantee handler purity or idempotency; callers own
  that contract.

## Next gate

Run the new tests and the existing full test suite. Then add a durable
experiment archive with manifest digest, code revision, environment metadata,
and raw per-task outputs before using the harness for CPG-EI claims.
