# CPG-EI v1 convergence foundation — 2026-11-11

Status: integration foundation proposal. Implementation is intentionally limited to immutable cross-track DTOs. This is not a claim that the full CPG-EI system is integrated or that any research hypothesis has passed.

## Why this change exists

The repository now has many active research branches and stacked draft PRs. The main integration risk is incompatible interfaces and duplicated state ownership. Main remains a conservative baseline while E09/E10/E12, E02/E03, Zhouyi/Taixuan/Yinfu and orchestration work continue on separate branches.

This change adds a small, track-neutral interchange contract. It deliberately does not introduce a second candidate lifecycle state machine or a second evidence ledger.

## Ownership boundaries

| Concern | Owner | Cross-track rule |
|---|---|---|
| Candidate lifecycle transitions | E12-A6 lifecycle ledger | Other tracks reference immutable candidate versions; do not invent another shared state enum |
| Durable prediction/reveal/revision events | E09 shared evidence protocol | This package carries references and validates binding; it is not a replacement store |
| Primitive and relation proposals | E12 / E02 / E10 adapters | Emit versioned candidate references and provenance |
| Factor graph and belief propagation | E12-A20 | Emit ranked hypotheses, explicit ambiguity and resource counters |
| Representation and observation policies | Zhouyi / Taixuan / Yinfu tracks | Remain separate experimental axes; no bundled prior claim |
| Task scheduling and execution | Hyper-Speed orchestrator | Schedule declared handlers; no implicit shell or repository authority |

## Contracts added

prototype/cpg_interop.py provides immutable DTOs for:
- CandidateProposal: versioned candidate reference, track, scope, grammar, definition digest, evidence references and estimated cost;
- PredictionCommit: a prediction or explicit abstention, frozen before reveal, with a deterministic digest;
- EvidenceReveal: canonical outcome payload and split metadata bound to a prediction commit;
- StructureVersion: immutable version and parent/evidence lineage;
- InferenceResult: ranked hypothesis references, epistemic status, evidence references and explicit resource counters.

The module also provides canonical JSON hashing, reveal/commit binding validation, and a metadata visibility policy:
- learner: SUPPORT only;
- selector: SUPPORT + GATE_DEV;
- evaluator: all splits.

This policy is a testable contract, not a security boundary. Production isolation still requires separate learner/evaluator processes or services and an authenticated evidence channel.

## Important non-goals

- No SQLite database, event replay, or durable ledger is added.
- No E12-A6 lifecycle states or transition rules are duplicated.
- No factor graph / belief propagation implementation is copied into main.
- No candidate scores are called calibrated probabilities.
- No evaluator truth is made safe merely by storing a split label in the same process.
- No Transformer replacement or speedup claim is made.
- No Zhouyi/Taixuan/Yinfu prior is enabled by default.

## Integration sequence

1. Contract conformance: each track adapter maps its native objects into these DTOs and passes the same conformance tests.
2. E12-A20 adapter: map factor-graph/BP output into InferenceResult; preserve AMBIGUOUS, INCONSISTENT and BUDGET_EXHAUSTED.
3. E12-A6 adapter: map candidate versions and lifecycle evidence references without reimplementing its state machine.
4. E09 adapter: bind prediction commits and evidence reveals to the existing shared protocol; retain append-only semantics and fail-closed behavior.
5. E02/E10/E11 adapters: emit proposals and immutable structure versions with source-group, role, scope and evidence lineage.
6. CSL coordinator: orchestrate the existing track-owned components; persist lifecycle actions only through a versioned extension to the shared protocol.
7. E03 arbitration: compare candidate utility under matched budgets, with abstention and independent gate evidence.
8. Representation arbitration: keep state cardinality, structural prior and observation policy as orthogonal factors. Zhouyi, Taixuan and Yinfu must not be conflated.
9. MTS-0 acceptance: run complete train → commit → reveal → revise → held-out transfer episodes with evaluator/learner isolation.
10. MTS-1+: only after MTS-0 passes, connect continuous encoders and neural proposal models.

## Current repository evidence and limits

Active research branches already contain:
- E12-A16–A20 work on open-set primitives, typed relation graphs, transition motifs, multi-rule controls, factor graphs, synchronous sum-product belief propagation and typed hypothesis graphs;
- E09 prequential learning and a shared SQLite protocol v0.2 adapter on a separate integration line;
- CSL specifications for composing E12 lifecycle and E09 evidence events without duplicated state;
- cross-representation research separating Zhouyi structural priors, Taixuan state cardinality and Yinfu observation policy;
- Hyper-Speed P0 scheduling and a v2 design for resource-aware, evidence-backed research orchestration.

These are branch-local artifacts, not one merged runtime. Their individual CI passes validate only the code and tests included in those branches. Before integration, each source head must be pinned, its base divergence reconciled, and its focused tests rerun on the composed commit.

## Acceptance gates

A PR is not integrated merely because it merges cleanly. Each integration slice must:
- preserve source commit and protocol version metadata;
- pass the full unit suite plus focused adapter conformance tests;
- reject cross-scope evidence and mismatched commit/reveal bindings;
- demonstrate that learner-visible inputs are invariant to changes in locked-test truth;
- preserve ambiguity and abstention instead of forcing a single answer;
- report actual proposal, evaluation, inference and wall-clock costs;
- retain a simple baseline and an explicit falsification condition.

## Recommended merge policy

Keep main stable. Merge only small, independently reviewed integration slices after parent dependencies are available and CI passes. Do not merge all research branches in one batch: the repository contains stacked PRs with differing base branches, protocol versions and validation boundaries.
