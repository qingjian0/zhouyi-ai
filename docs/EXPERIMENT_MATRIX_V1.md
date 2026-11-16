# Experiment Matrix v1

Status: implementation candidate; benchmark integration pending.

## Purpose

Expand a research specification into a deterministic Cartesian product of
independent scheduler tasks. The matrix engine does not execute experiments,
select winners, or interpret Zhouyi/Yixue semantics.

## Identity

The SHA-256 manifest digest covers schema version, experiment name, handler,
ordered tracks, ordered conditions, ordered seeds, payload, and expected task
count. Input order is intentionally significant. Reordering a dimension
changes the digest and therefore identifies a distinct run.

## Expansion

The stable expansion order is:

1. track
2. condition
3. seed

Each task receives the experiment name, matrix digest, track, condition, seed,
and a JSON-isolated copy of the shared payload. Task IDs are deterministic
ordinal IDs and do not embed user-supplied labels.

## Integrity constraints

- Seeds are unique, non-negative integers; booleans are rejected.
- Tracks and conditions are non-empty tuples of unique non-empty strings.
- Payload must be a JSON object containing only finite JSON values.
- Expansion count is exactly tracks × conditions × seeds.
- Tasks are passed through the existing TaskGraph validation before execution.

## Next integration gate

The next stage must add a serial reference runner and a parallel runner using
the same TaskSpec list, then compare canonical per-task output digests. Do not
claim speedup until output equivalence and repeated timing runs are recorded.
