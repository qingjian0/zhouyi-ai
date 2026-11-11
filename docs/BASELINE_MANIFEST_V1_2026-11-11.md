# Zhouyi-AI Baseline Manifest

Audit date: 2026-11-11 (UTC)
Repository: `qingjian0/zhouyi-ai`

This file is the single reference for branch and commit identity. Other documents should link here rather than independently redefining the active baseline.

## Canonical refs

| Role | Ref | Commit | Meaning |
|---|---|---|---|
| Stable line | `main` | `69837916464d9be5fdf82e288eee836a2306a386` | Stable early research baseline; untouched by this convergence work |
| Source integration line | `integration/e09-v03-evidence-binding-2026-11-11` | `e90f7eb210db456a541eb9f45ec39f64ebb934a5` | Selected code baseline for convergence |
| Convergence work line | `integration/zhouyi-unified-convergence-2026-11-11` | `330866ab9b90ad8058667e8e2d41c639b9cc4c9b` | Head at the start of this audit; this branch advances as audit fixes are committed |
| Integration PR | [#206](https://github.com/qingjian0/zhouyi-ai/pull/206) | head was `330866a` at audit start | Draft integration PR; base is the E09 integration line |

## Precedence rules

1. The E09 source-code baseline is exactly `e90f7eb210db456a541eb9f45ec39f64ebb934a5`.
2. The convergence branch is the only target for this documentation reconciliation. Do not write to `main`.
3. The convergence branch HEAD is mutable. Use the live GitHub branch/PR metadata for its current HEAD; do not freeze a later HEAD into this manifest as though it were the source baseline.
4. `50104ed486db3d5b28527eb9785e1fe3a199990b` is a historical earlier E09 reference and is superseded as the convergence source baseline.
5. `8b0aa2aef42edddcbbead8fde5c6944ae786dd50` is an earlier code commit recorded by the E09 roadmap snapshot; the selected source baseline includes the subsequent documentation reconciliation commit `e90f7eb`.
6. A successful CI run on a parent/source commit is not evidence that the current convergence head passes CI.

## Audit findings carried forward

- The architecture document previously referenced `50104ed`, while the execution baseline selected `e90f7eb`. This discrepancy is resolved by the precedence above.
- The roadmap and integration registry contain historical status snapshots. Their status claims must be read with their dated commit context, not as live branch metadata.
- E17 / PR #185 contains CandidateBundle governance material worth reusing, but its independent lifecycle state transitions conflict with the E12-A6 single-owner rule. Do not integrate its lifecycle state machine as a second authority.
- SROK-0 remains a bounded deterministic role-slot composition kernel; multi-origin composition, branch deltas, cross-branch merge/recombination and skipped-element semantics remain separate gaps.
- N0.10 remains a constrained learnable scoring prototype; higher-order necessity is not established because unary shortcuts remain a risk.
- ZPCM is a durable projection/retrieval layer over the authoritative E09 event history, not a second evidence ledger.
- PR #202 adds trusted single-process crash-resume capability. It does not establish OS-level evaluator/learner isolation, authenticated IPC or an atomic cross-process outbox.

## Verification status

This manifest records a repository/document audit and ref identity. It does not claim that tests or CI were run on the post-audit convergence HEAD, nor that the P1 end-to-end closure is complete.
