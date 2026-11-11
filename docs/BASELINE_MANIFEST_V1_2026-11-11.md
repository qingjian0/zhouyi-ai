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
| [#217](https://github.com/qingjian0/zhouyi-ai/pull/217) | #208 branch at `5f886df` | typed bridge branch at `ecc20f3` | Typed hyperedge unifier wired to bounded CSG-GCR candidate-set filtering | Draft; syntax correction at `ecc20f3` verified by workflow run 43027843058 (unit-tests and full prototype evaluation job success) |
| [#218](https://github.com/qingjian0/zhouyi-ai/pull/218) | #217 corrected head at `ecc20f3` | branch-delta stack at `fdda7a4` | Immutable parent references, typed append-only deltas, stale/read-write/write-write conflict checks, idempotent replay | Draft; runs 43028239730 and 43028627937 exposed fixture-version and stale-variable-name defects; both corrected, delta payloads made deeply immutable, and exact latest head `fdda7a4` is under workflow run 43028753187 |

PR #218 is stacked on PR #217 and inherits the #208 dependency. Neither PR is independently mergeable to main as a complete architecture slice. The branch-delta kernel validates structural edit compatibility only; it does not own E09 evidence, E12-A6 lifecycle, or ZPCM persistence. Exact-head CI and review remain mandatory.


## P1 integration stack audit refresh (2026-11-11 21:45 UTC+8)

| PR | Exact head | Base | CI evidence | Status |
|---|---|---|---|---|
| [#208](https://github.com/qingjian0/zhouyi-ai/pull/208) | `5f886df80bd89f2bcefdaddaf6f62a33fdff3ab2` | E09 integration branch | Prior bounded-coordinator baseline | Draft |
| [#217](https://github.com/qingjian0/zhouyi-ai/pull/217) | `ecc20f333629bb6cd199342d0deb847f3d5f1983` | #208 head | Workflow `43027843058` success | Draft; typed unifier bridge |
| [#218](https://github.com/qingjian0/zhouyi-ai/pull/218) | `e433361931fc47f5f2819abc1597f8a8b601dfd9` | #217 head | Workflow `43030468165` success | Draft; branch delta with parent digest, provenance checks, deterministic conflict handling |
| [#221](https://github.com/qingjian0/zhouyi-ai/pull/221) | `7e65c22f7a3a01782d59306ada3401899134392e` | #218 head | Workflow `43031651288` running at audit time; unit tests had started | Draft; monotonic typed partial pruning |

PR #221 adds a bounded coordinator callback with an explicit monotonicity contract and a typed adapter that prunes only contradictions proven irreversible under extension. It intentionally retains final typed unification as the complete-set authority. The exhaustive subset monotonicity test and pruned/unpruned differential oracle are part of the new test suite.

This stack remains layered: #221 -> #218 -> #217 -> #208. No PR in this chain has been merged to `main`; mergeability flags do not constitute integration approval. The E09 evidence commit/reveal, E12-A6 candidate lifecycle, and ZPCM durable event-history end-to-end wiring remain open integration work.


## PR #221 exact-head validation result

PR #221 head `7e65c22f7a3a01782d59306ada3401899134392e` completed workflow run `43031651288` with conclusion `success`. The run includes the full repository unit-test and E01/E02 evaluation sequence. This validates that exact PR head only; it does not imply the PR stack has been merged or that E09/E12-A6/ZPCM end-to-end integration is complete.


## P1 typed branch-delta bridge update

| PR | Head | Base | Status |
|---|---|---|---|
| [#221](https://github.com/qingjian0/zhouyi-ai/pull/221) | `7e65c22f7a3a01782d59306ada3401899134392e` | #218 head `e433361` | Draft; exact-head workflow `43031651288` success |
| [#222](https://github.com/qingjian0/zhouyi-ai/pull/222) | `38c5aeae0a7f980cbf377235ffd338a8c3559344` | #221 head `7e65c22` | Draft; exact-head CI pending |

PR #222 connects branch snapshots to typed CSG-GCR candidate results. Cross-branch composition requires a scoped BranchMergeAuthorization receipt expected from E09; the adapter validates declared scope but does not authenticate the issuer. Accepted candidates carry the structural MergeResult and authorization reference. Candidate lifecycle and durable event persistence remain unimplemented in this adapter.


## PR #222 exact-head refresh

PR #222 latest head is `44166f27f1b9892782080a312fc80a15c0e19f2b`, based on PR #221 head `7e65c22f7a3a01782d59306ada3401899134392e`. Workflow `43032951104` was running at audit time; the unit-test step had completed and the workflow had advanced to E01-B. Do not mark the latest head fully validated until the complete workflow concludes.


## PR #222 exact-head validation result

PR #222 head `44166f27f1b9892782080a312fc80a15c0e19f2b` completed workflow run `43032951104` with conclusion `success`. The run includes the repository unit-test and E01/E02 evaluation sequence. The typed candidate result preserves merged branch-delta evidence references and the E09 authorization reference/evidence references. This is still a Draft prototype adapter, not E09 cryptographic authorization, E12-A6 lifecycle integration, or ZPCM persistence.


## PR #223 exact-head audit

PR #223 head `1e23b23c515e3b339c52850d98ba9981176495b5`, base PR #222 head `44166f27f1b9892782080a312fc80a15c0e19f2b`. Workflow `43034178683` was running at audit time, currently in the unit-test step. The adapter creates an E12-A6 OBSERVED candidate and read-only CPG-EI projection; raw CSG-GCR score remains uncalibrated metadata and E12-A6 remains the only lifecycle authority.


## PR #223 and #226 lifecycle persistence stack refresh

| PR | Exact head | Base | Exact-head workflow | Status |
|---|---|---|---|---|
| [#223](https://github.com/qingjian0/zhouyi-ai/pull/223) | `1e23b23c515e3b339c52850d98ba9981176495b5` | #222 head `44166f27f1b9892782080a312fc80a15c0e19f2b` | `43034178683` success | Draft; read-only typed CSG-GCR → E12-A6 OBSERVED projection |
| [#226](https://github.com/qingjian0/zhouyi-ai/pull/226) | `0a03c61382fcccc8b99ac5669cbfccef4167c606` | #223 head `1e23b23c515e3b339c52850d98ba9981176495b5` | `43036878778` success | Draft; E12-A6 lifecycle events persisted and replayed through ZPCM |

PR #226 reuses the existing ZPCM memory_events append-only table and adds a dedicated, unbounded lifecycle replay API. It does not use bounded semantic retrieval for event restoration. Lifecycle mutations are validated on a staged E12-A6 ledger, durably appended, and only then swapped into memory. Restart replays the event stream through the existing E12-A6 LifecycleLedger. Evidence outcome/provenance values are replaced with opaque references in lifecycle persistence; E09 remains evidence payload authority.

The validated boundary is a trusted single-process SQLite reference implementation. It does not provide distributed consensus, OS-level process isolation, authenticated E09 evidence/branch authorization, or a cross-process transactional outbox. PR #226 remains Draft and is not merged to main.


## E09 evidence binding continuation

| PR | Exact head | Base | Exact-head workflow | Status |
|---|---|---|---|---|
| [#226](https://github.com/qingjian0/zhouyi-ai/pull/226) | `f4406ab9e9a8eb89329d767bfe5e11cef10964ee` | #223 head `1e23b23c515e3b339c52850d98ba9981176495b5` | `43037972184` success | Draft; ZPCM lifecycle append/replay and E12-A6 transactional adapter |
| [#227](https://github.com/qingjian0/zhouyi-ai/pull/227) | `bc5114f846464c366469f08da82b1fd37c1479ef` | #226 head `f4406ab9e9a8eb89329d767bfe5e11cef10964ee` | `43038201790` success | Draft; strict E09 reveal-chain verification and redacted E12-A6 evidence projection |

PR #227 recomputes the E09 event-envelope fingerprint for observation, prediction commit, and reveal before projection. It requires the evaluator reveal role, strict v0.3, exact scope/track/query/split linkage, sequence ordering, semantic commit digest, durable commit-envelope digest, and causation reference. E09 SUPPORT maps explicitly to E12-A6 TRAIN; GATE_DEV/GATE_FINAL/LOCKED_TEST remain separate. World family is caller-supplied rather than inferred.

This closes the evidence-reference verification slice only. It does not authenticate the E09 database operator, validate BranchMergeAuthorization issuer credentials, or yet provide one atomic ingestion operation combining a typed CSG-GCR candidate with all its E09-verified evidence.


## P1 atomic CSG-GCR ingestion validation

| PR | Exact head | Base | Exact-head workflow | Status |
|---|---|---|---|---|
| [#227](https://github.com/qingjian0/zhouyi-ai/pull/227) | `6a4b0dce8dd1255daaa613a2649796a07e37de85` | #226 head `f4406ab9e9a8eb89329d767bfe5e11cef10964ee` | `43038677702` success | Draft; E09 reveal chain verification and redacted E12 evidence DTO |
| [#228](https://github.com/qingjian0/zhouyi-ai/pull/228) | `d68819c34275a6b69482b28a33dbeeaec8c7659e` | #227 head `6a4b0dce8dd1255daaa613a2649796a07e37de85` | `43039470802` success | Draft; atomic typed CSG-GCR candidate + verified E09 evidence ingestion |

PR #228 adds a ZPCM all-new/all-replayed batch append contract and stages the candidate plus verified evidence on an E12-A6 ledger copy. It commits the full event bundle in one SQLite transaction, then swaps the staged ledger. Tests include second-insert rollback and crash-after-batch-commit replay. Cross-branch candidates are explicitly rejected until E09 authorization issuer verification exists.

The P1 runtime now has a tested single-branch path from typed CSG-GCR proposal evidence references through E09 strict reveal verification, E12-A6 candidate/evidence registration, and ZPCM atomic persistence/replay. This remains a trusted single-process reference path; it is not a production multi-process or distributed transaction system. All PRs remain Draft and unmerged.


## End-to-end lifecycle verification

| PR | Exact head | Base | Exact-head workflow | Status |
|---|---|---|---|---|
| [#228](https://github.com/qingjian0/zhouyi-ai/pull/228) | `8edf52c3ee83bc8063d14d249a2edc7676f1e9d8` | #227 head `6a4b0dce8dd1255daaa613a2649796a07e37de85` | `43040120573` success | Draft; atomic CSG-GCR + E09 evidence ingestion |
| [#229](https://github.com/qingjian0/zhouyi-ai/pull/229) | `561ecc4e51c5d2af39139cb367ec0d430571ec38` | #228 head `8edf52c3ee83bc8063d14d249a2edc7676f1e9d8` | `43040339295` success | Draft; end-to-end lifecycle transitions and restart/replay |

PR #229 validates the full single-branch lifecycle: OBSERVED → PROPOSED → DISCRIMINATION_PENDING → TRAIN_SUPPORTED → GATE_VALIDATED → CHALLENGED. SUPPORT-derived TRAIN evidence, GATE_FINAL, and LOCKED_TEST are used only for their intended transitions. A negative test confirms GATE_DEV cannot satisfy GATE_FINAL and that rejected transitions do not append events. Restart restores the exact lifecycle state and action history from ZPCM.


## P1 lifecycle and authorization integration audit (2026-11-11)

| PR | Exact head | Exact-head workflow | Result |
|---|---|---|---|
| #223 typed CSG-GCR → E12-A6 OBSERVED projection | `1e23b23c515e3b339c52850d98ba9981176495b5` | `43034178683` | success |
| #226 E12-A6 lifecycle append/replay through ZPCM | `f4406ab9e9a8eb89329d767bfe5e11cef10964ee` | `43037972184` | success |
| #227 strict E09 reveal verification + redacted E12 evidence | `6a4b0dce8dd1255daaa613a2649796a07e37de85` | `43038677702` | success |
| #228 atomic typed candidate + E09 evidence ingestion | `8edf52c3ee83bc8063d14d249a2edc7676f1e9d8` | `43040120573` | success |
| #229 end-to-end CSG-GCR → E09 → E12-A6 → ZPCM lifecycle/replay | `561ecc4e51c5d2af39139cb367ec0d430571ec38` | `43040339295` | success |
| #230 authenticated E09 cross-branch merge grants | `541ba18d790fc2b713051d5489a7543e2205c3e1` | `43050136136` | success |

PR #229 verifies the full single-branch lifecycle through restart/replay and confirms split isolation: SUPPORT→TRAIN, GATE_FINAL→gate, LOCKED_TEST→challenge; GATE_DEV cannot satisfy GATE_FINAL.

PR #230 closes the earlier unsigned authorization gap. Plain BranchMergeAuthorization claims are no longer sufficient. Cross-branch composition requires an E09 v0.3 signed grant with exact parent/scope/branch set, prior verified evidence references and a valid expiry window. Signature verification is delegated to an injected trusted issuer-keyring verifier; test callbacks are not production cryptography.

**Remaining gate:** deployable issuer trust configuration, public-key rotation/revocation, evaluator process isolation, authenticated IPC and remote tamper-evident replication are not implemented. Current E09/ZPCM stores remain trusted single-process SQLite reference components. All listed PRs remain Draft and unmerged.


## P1 Ed25519 issuer verification milestone

| PR | Exact head | Exact-head workflow | Result |
|---|---|---|---|
| #231 concrete Ed25519 keyring + real cross-branch E2E | `99249112754fb747a791c75205309313820501ed` | `43050925777` | success |

PR #231 implements an immutable issuer→Ed25519 public-key keyring, Base64 signature verification, fail-closed unknown/revoked issuers, and deterministic verifier configuration fingerprints. Its integration test signs a strict E09 grant with an ephemeral private key, verifies it with the concrete keyring, composes two branch deltas, and atomically ingests the resulting typed candidate and verified E09 evidence into E12-A6/ZPCM.

This validates the cryptographic interface and the single-process end-to-end reference path. It does not validate production key provisioning, secure configuration delivery, multi-key overlap/rotation orchestration, process isolation, authenticated IPC or remote anti-rollback storage.
