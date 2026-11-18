# Zhouyi-AI training readiness audit and convergence gates

Date: 2026-11-12
Branch: `research/training-readiness-gates-2026-11-12`
Base: `main`
Status: research specification; no production-readiness claim

## Executive decision

Zhouyi-AI has several independently trainable research components, but the repository is not yet ready to claim a unified end-to-end training system. The immediate blockers are not a lack of model ideas. They are (1) lifecycle state that still scales with event history in Python memory, (2) experiment input/evaluation contracts that are component-level rather than corpus-scale, and (3) relation discovery that is still bounded to a predefined candidate universe.

Proceed with three parallel workstreams and one shared acceptance protocol:

1. E12-A6/ZPCM: replace full-ledger restore with a transactionally maintained, rebuildable SQLite state projection.
2. N0.10/SROK: make data ingestion and evaluation scalable and leakage-resistant; keep exact search as a small-instance oracle.
3. CPG-EI/Yixiang: distinguish learning weights over supplied relation candidates from discovering new relation structure.
4. Shared training gate: deterministic datasets, split provenance, multi-seed evaluation, matched baselines, resource curves, and reproducible run manifests.

Do not merge experimental work to stable `main` merely because unit tests pass.

## Evidence-based current state

### E12-A6 lifecycle restore

The current `PersistentLifecycleLedger._restore()` iterates the complete lifecycle stream, constructs a fresh `LifecycleLedger`, and repopulates candidate/evidence/action collections. The indexed projection in PR #349/#350 is useful lookup infrastructure, but it is not yet used to eliminate this full materialization.

The RSS benchmark reported in PR #349 measured approximately:

| Events | RSS after ZPCM init | RSS after E12-A6 restore |
|---:|---:|---:|
| 1,000 | 23.97 MB | 25.09 MB |
| 10,000 | 25.06 MB | 34.17 MB |
| 50,000 | 25.19 MB | 70.69 MB |

The 50K restore delta is about 45.5 MB. These are environment-specific process RSS measurements, not a universal memory guarantee.

A further projection-schema issue must be addressed before relying on the new index: the current projection derives `entity_id` from `action.action_id` for `action_applied`. That is suitable for locating an action by action ID, but it does not index the candidate affected by that action. The partial candidate-history index is therefore not sufficient to reconstruct candidate transition history without another indexed relation. Store distinct identity columns rather than overloading one `entity_id`.

### N0.10 experiment runner

PR #347 provides a deterministic component-level runner with train/dev/locked-test separation, checkpointing, exact product search and bounded beam search. Its documented optimizer is full-batch gradient descent without momentum/adaptive state; epoch-boundary resume is exact only while code, data, configuration and optimizer semantics remain unchanged.

The current loader reads the entire JSONL file with `Path.read_bytes()`, decodes it, and constructs in-memory row lists for each split. This is acceptable for a small benchmark, not a corpus-scale streaming contract. The runner records rule-family provenance but does not enforce group-disjoint OOD splits. The documentation correctly states that parameter/FLOP-matched MLP, graph, tensor and Transformer baselines remain outstanding.

### CPG-EI

The current learnable-gate work selects among a predefined 35-candidate relation set (15 pairwise and 20 third-order candidates). Its synthetic sparse-teacher result is evidence that the gates can suppress some supplied candidate groups in that benchmark. It is not evidence of open-ended relation discovery, semantic truth probabilities, or general reasoning.

The next experiment must separate:
- candidate generation (what relations are proposed),
- candidate evaluation (what evidence supports them),
- structure selection (what is retained),
- transfer/generalization (whether the selected structure works on unseen worlds).

## Workstream A — bounded E12-A6 state projection

### Target architecture

Keep `memory_events` as the sole authoritative append-only event log. Add a rebuildable SQLite projection for current lifecycle state and indexed relationships. The projection is a cache, never a second authority.

Recommended normalized tables:

- `e12a6_lifecycle_projection_meta(scope, schema_version, high_water_seq, event_chain_digest, generation)`
- `e12a6_candidate_current(scope, candidate_id, version, state, canonical_payload_digest, source_seq)`
- `e12a6_evidence_current(scope, evidence_id, split_role, episode_id, source_seq)`
- `e12a6_action_index(scope, action_id, candidate_id, candidate_version, action_type, from_state, to_state, source_seq)`
- `e12a6_action_evidence(scope, action_id, evidence_id)`
- `e12a6_candidate_evidence(scope, candidate_id, version, evidence_id)`
- `e12a6_authorization_consumptions` remains the unique receipt/nonce projection.

Do not overload a single `entity_id` to represent both action identity and candidate identity. Preserve both. Do not store duplicate full event bodies in projections; resolve source events through the byte-limited, digest-verifying ZPCM reader.

### Restore algorithm

1. Start a read/write transaction and read projection metadata.
2. Validate schema version, high-water sequence, generation, and checkpoint digest against authoritative event-log metadata.
3. If valid, serve normal current-state reads from the projection; do not replay the entire history into Python.
4. If missing/stale/corrupt, rebuild in bounded keyset pages. Decode and validate one event at a time (or a strictly byte-bounded page), update projection rows and high-water metadata in the same transaction.
5. Commit the projection and checkpoint atomically. On any validation failure, roll back and fail closed; never publish a partially rebuilt state.
6. On normal append, validate the transition against the current projection, append the immutable event, update projection/index rows, and advance the checkpoint in one `BEGIN IMMEDIATE` transaction.
7. Keep `ledger` and `snapshot()` as explicit compatibility/materialization APIs. Ordinary startup and reads must not call them.

Important: SQL triggers may maintain mechanical indexes, but they must not silently replace Python/domain lifecycle validation. Domain validation remains explicit and testable.

### Required APIs

- `get_candidate(candidate_id, version)`
- `get_current_candidate(candidate_id)`
- `iter_candidates(after_key, limit, max_bytes)`
- `get_evidence(evidence_id)`
- `iter_actions(candidate_id, after_sequence, limit)`
- `snapshot()` (explicitly materializing and documented as O(total state))

All iterators must have deterministic ordering, enforce count and aggregate-byte limits, and expose continuation cursors. Missing/corrupt projection rows must trigger audit/rebuild or fail closed, never silently become NOT_FOUND.

### Acceptance tests

- Restore 1K/10K/50K/100K/500K events in fresh processes.
- Measure current RSS, peak RSS, Python allocation peak, SQLite page/cache size and restore latency separately.
- Demonstrate that post-initialization Python RSS does not grow linearly with historical event count for the normal projection-backed startup path.
- Corrupt/delete projection rows and checkpoint metadata; verify deterministic rebuild from authoritative events.
- Inject crashes before append, after append, during projection mutation and before checkpoint publication.
- Verify append + projection + checkpoint atomicity under concurrent writers and multiple readers.
- Preserve all existing E09 receipt binding, nonce/receipt uniqueness, evidence split rules, state-transition rules, idempotency and digest verification.
- Verify the compatibility `snapshot()` still matches replay oracle output on small generated histories.

A bounded-memory claim is accepted only after OS-level RSS results and crash/rebuild tests pass on the exact commit.

## Workstream B — N0.10/SROK training pipeline

### Separate algorithmic correctness from scale

Keep exact product enumeration as an oracle for small candidate pools. Beam search is approximate and must report pruning/abstention explicitly. Do not compare beam accuracy alone while hiding coverage or budget exhaustion.

### Data pipeline changes

- Add a versioned JSONL manifest with dataset digest, source-group IDs, episode IDs, rule-family IDs, feature schema, role schema, and split policy.
- Support group-disjoint splitting by source group/world family, not only row-level split labels.
- Add a streaming/two-pass loader. For full-batch gradient descent, accumulate gradients/loss in deterministic order without retaining all examples; alternatively use deterministic sharded batches and explicitly version the optimizer semantics.
- Do not load locked-test labels into the learner process. Evaluation should be a separate post-fit stage with a narrow prediction/label boundary.
- Validate finite features, node IDs, evidence references, role arity, duplicate examples and group leakage before training.
- Make dataset sharding deterministic and bind every shard to a digest.

### Training and evaluation

For each model/configuration, report:
- exact-match accuracy,
- covered accuracy,
- coverage and abstention rate,
- budget exhaustion and beam-pruning rate,
- calibration/error by role and rule family,
- train/dev/locked-test metrics,
- parameter count, operation/expansion budget, wall time, peak RSS,
- seed-level mean, standard deviation and confidence interval.

Run at least 5 seeds for screening and 10+ for final claims. Use paired seeds and identical examples across baselines.

Required baselines:
1. unary-only SROK,
2. pairwise-only SROK,
3. pairwise + third-order SROK,
4. MLP with matched parameter budget,
5. graph/message-passing baseline with matched compute budget,
6. exact product search as the small-instance oracle,
7. beam search at multiple widths.

Required ablations:
- remove third-order terms,
- shuffle relation labels,
- permute feature dimensions,
- remove type/tag constraints,
- vary candidate pool size,
- hold out entire rule families and object identities,
- compare random vs structured train/test splits.

A claimed third-order gain must survive matched baselines, multiple seeds, rule-family OOD, and label/permutation controls.

## Workstream C — CPG-EI and Yixiang relation discovery

Current gate learning is candidate selection over a fixed universe. The next design must introduce a bounded proposal mechanism that can generate candidate relation/hyperedge descriptors from typed observations, then score and falsify them.

Use a staged loop:

1. Extract typed entities, features and evidence-backed observations.
2. Generate bounded candidate relations of arity 1..K under an explicit proposal budget.
3. Canonicalize candidates and deduplicate under declared symmetry policy.
4. Estimate support on TRAIN only.
5. Use DEV for candidate selection and complexity/regularization tuning.
6. Freeze the selected structure before LOCKED_TEST.
7. Report support recovery, false discovery rate, exact relation recovery, structural OOD and compute per discovered relation.

Keep pairwise and higher-order models under comparable proposal and compute budgets. Include negative controls with shuffled labels and synthetic worlds where higher-order terms are provably unnecessary. A relation gate is a selection parameter, not a calibrated probability of truth.

For Yixiang/class-image mapping, maintain the distinction between:
- structural isomorphism under an explicit typed graph/hypergraph contract,
- statistical invariance under sampled environments,
- semantic analogy supported by evidence,
- causal equivalence.

Passing one level must not be described as proving the next.

## Shared training-readiness gates

### Gate 0 — executable component
- deterministic unit tests,
- schema and input validation,
- explicit resource budgets,
- small synthetic smoke test.

### Gate 1 — reproducible experiment
- immutable dataset manifest and Git SHA,
- train/dev/locked-test isolation,
- exact checkpoint/resume semantics,
- multi-seed report and baseline comparison.

### Gate 2 — robust generalization
- group-disjoint OOD,
- adversarial/permutation controls,
- ablations,
- calibrated uncertainty/abstention,
- confidence intervals.

### Gate 3 — operational scale
- RSS/latency curves at increasing data sizes,
- crash/restart and corruption recovery,
- bounded iteration and I/O,
- concurrency and durability checks.

### Gate 4 — integrated system
- evidence ingestion → typed representation → candidate discovery → learning → evaluation → lifecycle persistence,
- provenance retained across every boundary,
- no hidden-label path into training,
- end-to-end reproducibility from a clean checkout.

Only Gate 4 justifies saying the integrated Zhouyi-AI training system is ready for its declared target domain. It does not imply a general-purpose language model or Transformer replacement.

## Immediate execution order

Parallelize without mixing authorities:

1. E12-A6: design and implement normalized candidate/action/evidence projections plus checkpointed restore.
2. N0.10: add group-disjoint manifest validation and a streaming full-batch experiment path.
3. CPG-EI: add candidate proposal budget, canonicalization, and exact support-recovery benchmark.
4. Integration: publish a shared experiment manifest and run matrix; do not merge until all exact-head workflows pass.

## Source PRs reviewed

- [PR #347 — N0.10 checkpoints, joint retrieval and experiment runner](https://github.com/qingjian0/zhouyi-ai/pull/347)
- [PR #348 — SQLite-backed receipt metadata](https://github.com/qingjian0/zhouyi-ai/pull/348)
- [PR #349 — E12-A6 RSS benchmark and indexed lifecycle projection](https://github.com/qingjian0/zhouyi-ai/pull/349)
- [PR #350 — indexed lifecycle projection contract](https://github.com/qingjian0/zhouyi-ai/pull/350)
- [PR #344 — CPG-EI learnable gates](https://github.com/qingjian0/zhouyi-ai/pull/344)

This document is a research audit and implementation contract. It does not claim that the changes above have already been implemented or that the repository has passed the gates.
