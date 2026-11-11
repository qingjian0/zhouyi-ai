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


## Active PR dependency snapshot

Live metadata checked during this audit:

| PR | Base ref / SHA | Head ref / SHA | State | Integration interpretation |
|---|---|---|---|---|
| #185 E17 | `main` / `6983791` | `research/e17-candidate-bundle-contract-2026-11-11` / `9855f53` | Draft, mergeable | Separate from E09 line; review/reuse content contract, but remove its competing lifecycle authority before integration |
| #206 Convergence | E09 / `e90f7eb` | `integration/zhouyi-unified-convergence-2026-11-11` / `c907478` | Draft, mergeable | This documentation convergence PR |
| #208 CSG-GCR | E09 / `e90f7eb` | `integration/csg-gcr-executable-slice-2026-11-11` / `5f886df` | Draft, mergeable | Parallel integration candidate; not based on #206 and not yet wired to E09/E12-A6/ZPCM |
| #212 Typed unification | CSG-GCR branch / `91f6ae4` | `integration/csg-typed-hyperedge-unification-2026-11-11` / `dd29958` | Draft, mergeable | Stacked on an earlier #208 branch commit; reference kernel is explicitly not yet connected to CSG-GCR |
| #213 YJ-07 | YJ-06 / `77bb683` | `research/yj07-autonomous-role-schema-induction-2026-11-11` / `876cde8` | Draft, mergeable | Independent research stack; not part of the current P1 runtime closure |
| #215 YJ-08 | YJ-07 / `876cde8` | `research/yj08-dynamic-role-evolution-2026-11-11` / `87fdaac` | Draft, mergeable | Stacked research follow-up; mergeability does not imply readiness |

The #212 base commit is an ancestor of #208 head; comparison shows #208 is one commit ahead of the #212 base. Before combining them, re-evaluate the complete stack against the live branch heads and run the combined tests. All listed PRs remain Draft. `mergeable=true` is only a GitHub mergeability signal, not an architecture or validation approval.

## CSG-GCR implementation boundary

PR #208 is an R1 candidate bounded coordinator. Its own scope records the following as not yet implemented: canonical semantic deduplication, typed hyperedge unification, incremental branch deltas and structural merge, Pareto/diversity selection, E09 integration, E12-A6 lifecycle adaptation and ZPCM persistence. PR #212 supplies a standalone typed-unification reference kernel, but its own specification states that CSG-GCR does not yet call it. Therefore PR #212 does not close the typed-unification integration gate.


## Code-level CSG-GCR review

Inspected PR #208 source and tests, plus PR #212 source and tests:

- `CandidateCoordinator` is a deterministic bounded depth-first subset search. It validates immutable proposals, parent-state consistency, string-key binding conflicts, explicit requires/excludes, cardinality/cost/state budgets, and emits an explicit `BUDGET_EXHAUSTED` status.
- Its binding contract remains `(string key, string value)`; branch IDs are labels, not persisted branch-delta objects. The implementation does not yet provide semantic deduplication, typed role/type unification, branch-delta merge/recombination, Pareto selection or diversity control.
- `proposal_from_srok` requires caller-supplied role-to-variable string mappings. It does not retain member types or construct the typed hyperedge contract.
- PR #212 adds a separate namespaced `VariableRef` / `VariableSpec` / `RoleBinding` unifier with subtype checks, equality/inequality constraints, role requirements, common temporal intersection and evidence-reference preservation. It is a reference kernel only; its own document explicitly says CSG-GCR is not wired to call it.
- Therefore the next code gate is not another independent coordinator: it is a typed SROK→hyperedge proposal adapter, a CSG-GCR validation hook using the typed unifier, and differential/negative tests proving that typed conflicts are rejected without dropping evidence provenance. The adapter must preserve parent-state and branch semantics and must not infer semantic identity from equal labels alone.

## Exact-head CI observation

At audit time, PR #206 head was `6e14c4a9c2363b15d46eee0bbff4417a4907ea6a`. No PR-triggered workflow run or combined status check was returned for that exact commit. An intermediate head `c907478` had a tests workflow reported in progress, but that is not evidence of CI success on the final head. No local test suite was executed during this audit.


## P1 typed CSG-GCR bridge status

A new Draft integration PR was opened after the code-level review:

| PR | Base | Head | Scope | Status |
|---|---|---|---|---|
| [#217](https://github.com/qingjian0/zhouyi-ai/pull/217) | #208 branch at `5f886df` | `integration/csg-gcr-typed-hyperedge-bridge-2026-11-11` at `4c61f75` | Typed hyperedge unifier + typed CSG-GCR bridge + focused tests | Draft; exact-head CI not yet reported |

PR #217 is stacked on the #208 CSG-GCR executable slice. It is not yet based on #206 or the E09 branch. Do not merge it independently to main or treat it as end-to-end E09 integration.

The bridge filters completed bounded CSG-GCR candidate sets through the typed unifier and preserves explicit budget exhaustion. It currently does not prune typed-infeasible partial sets during DFS; this is a known efficiency limitation, not a correctness claim about global search completeness. The exact PR head currently has no workflow run or combined status returned by GitHub; tests are therefore pending, not passing.


## P1 typed bridge and branch-delta stack update (2026-11-11)

| PR | Base | Head | Scope | Status |
|---|---|---|---|---|
| [#217](https://github.com/qingjian0/zhouyi-ai/pull/217) | #208 branch at `5f886df` | typed bridge branch at `ecc20f3` | Typed hyperedge unifier wired to bounded CSG-GCR candidate-set filtering | Draft; syntax error found in earlier CI and corrected at `ecc20f3`; exact corrected-head CI pending |
| [#218](https://github.com/qingjian0/zhouyi-ai/pull/218) | #217 corrected head at `ecc20f3` | branch-delta stack at `164e28b` | Immutable parent references, typed append-only deltas, stale/read-write/write-write conflict checks, idempotent replay | Draft; exact-head CI in progress at audit time |

PR #218 is stacked on PR #217 and inherits the #208 dependency. Neither PR is independently mergeable to main as a complete architecture slice. The branch-delta kernel validates structural edit compatibility only; it does not own E09 evidence, E12-A6 lifecycle, or ZPCM persistence. Exact-head CI and review remain mandatory.
