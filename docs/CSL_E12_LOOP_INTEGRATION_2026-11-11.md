# CSL + E12-Loop: Unified Cognitive Structure Lifecycle and Closed-Loop Benchmark

Date: 2026-11-11  
Status: research design / preregistration candidate  
Parent: `research/cpg-ei-cross-track-synthesis-2026-11-11`  
Scope: architecture contract and benchmark protocol; no claim of implementation or measured advantage.

## 1. Research question

Can E12 primitive induction, E11 concept construction, E10 structural mapping, E02 relation induction, E09 evidence-driven revision, and E03 parallel arbitration operate as one auditable learning system without silently overwriting knowledge, leaking evaluator truth, or promoting unsupported structures?

The proposed integration object is **Cognitive Structure Lifecycle (CSL)**. CSL is a cross-track state machine for versioned cognitive hypotheses. It is not a new learner by itself and does not imply that every structure is a valid concept.

Primary hypothesis H1: a shared lifecycle contract reduces inconsistent updates and improves delayed-counterexample recovery relative to independently managed track-local structures, under matched evidence and compute budgets.

Secondary hypotheses:
- H2: explicit ambiguity retention reduces false identification under observational equivalence.
- H3: role- and provenance-preserving lineage improves transfer diagnosis under nuisance and identity shifts.
- H4: conflict-aware arbitration improves calibrated selective accuracy over majority voting and best-single-path selection.
- H5: lifecycle gates reduce structural churn without preventing recovery from genuine distribution changes.

All hypotheses are falsifiable. A result that merely passes unit tests establishes protocol correctness, not learning capability.

## 2. Cross-track responsibilities

| Track | CSL contribution | Output contract |
|---|---|---|
| E12 | Propose executable primitives and measurement operators | typed candidate + executable semantics + provenance |
| E11 | Compose accepted predicates into concepts and hierarchies | concept candidate + scope + counterexamples |
| E10 | Align roles and structures across tasks/worlds | mapping candidate + role alignment + uncertainty |
| E02 | Induce sparse, high-order and non-contiguous relations | relation candidate + ordered roles + evidence lineage |
| E09 | Process streaming evidence and propose revisions | versioned update proposal or abstention |
| E03 | Compare parallel hypotheses and resolve conflicts | arbitration record + calibrated decision |
| E04 / YF / TX | Supply optional, controlled inductive priors | prior variant + version + measurable contribution |

These are logical responsibilities. They do not imply that each track is complete, mutually compatible, or independently beneficial.

## 2.1 Existing implementation audit: do not duplicate E12-A6 or E09 protocol

A review of the active research PRs changes the implementation recommendation:

- **E12-A6 already defines a typed candidate lifecycle ledger.** Its `CandidateState` includes OBSERVED, PROPOSED, DISCRIMINATION_PENDING, TRAIN_SUPPORTED, GATE_VALIDATED, REUSED, CHALLENGED, REVISED, SPECIALIZED, RETIRED, and REVALIDATION_PENDING. Its `ActionType` defines legal transitions, and it checks TRAIN / GATE_FINAL evidence roles. The in-memory ledger is append-only at the action level, but it is not itself a durable cross-track event store.
- **E12-A6 × E02-D has an end-to-end finite-world runner.** The recorded 100-seed sweep reports 2,700 episodes per support size. At support=2, 16.63% of episodes have a common query prediction while no episode uniquely identifies the mechanism; at support=4, the fixed 27-rule family is fully identifiable. This is a useful demonstration that prediction agreement and mechanism identification must remain separate, but the benchmark is deliberately finite and enumerable.
- **E09 already has a shared SQLite evidence protocol v0.2 adapter.** It persists observation, prediction_commit, evidence_reveal, structure_version, and revision events, with track identity, parent version references, and reveal-before-revision checks. It is a local durable store, not a distributed broker, evaluator/learner security boundary, or crash-resumable live learner.

Therefore CSL must **not** create a second CandidateState enum, a competing SQLite ledger, or a second predict/commit/reveal protocol. The correct design is a thin cross-track orchestration layer over these existing contracts.

### Proposed semantic mapping (not a replacement enum)

| CSL semantic phase | Existing E12-A6 state/action | Shared protocol representation |
|---|---|---|
| Proposed | PROPOSED / PROPOSE | candidate proposal metadata (not currently a first-class shared event) |
| Evidence-supported | TRAIN_SUPPORTED / TRAIN_SUPPORT | evidence_reveal events tagged by track and split metadata |
| Gate-validated | GATE_VALIDATED / GATE_VALIDATE | Gate evidence references plus structure_version metadata |
| In-use | REUSED / REUSE | version use/dependency event (extension required) |
| Challenged | CHALLENGED / CHALLENGE | evidence_reveal + lifecycle action event (extension required) |
| Revised | REVISED / REVISE | new immutable structure_version + revision |
| Specialized | SPECIALIZED / SPECIALIZE | new child structure_version + revision lineage |
| Revalidation pending | REVALIDATION_PENDING / REQUEST_REVALIDATION | lifecycle action event (extension required) |
| Retired | RETIRED / RETIRE | lifecycle action event (extension required) |

The shared protocol currently has five core event types. If lifecycle actions are persisted, extend it compatibly with an explicit `lifecycle_action` event (or a versioned generic event envelope); do not overload `revision` to represent proposal, challenge, reuse, or retirement. Add schema-versioned migration and replay tests before any adapter adopts the extension.

### Boundary between local candidate ledger and shared event store

- E12-A6 remains the domain-level transition validator and candidate/evidence model.
- Shared SQLite protocol remains the durable event sequence and cross-track lineage store.
- CSL coordinates adapters, dependencies, and arbitration; it must not duplicate their state.
- A candidate state snapshot should be reconstructible from the event stream or verified against it. If not, label it as a derived cache, never as the source of truth.
- E09 adapter's current fail-closed semantics and fresh-episode-only limitation must remain visible. Do not claim crash recovery or evaluator isolation.
- Cross-track dependencies need explicit IDs and invalidation policy; E12-A6's current candidate ledger alone does not provide global dependency invalidation.

This audit narrows the first implementation milestone: **CSL-0 should be a compatibility/conformance layer and mapping specification, not a fresh lifecycle implementation.**

### E03-A audit: coordination advantage is not yet demonstrated

The cross-branch audit for PR #18 reports a 30-seed E03-A comparison:
- Global coordinator Test accuracy: 0.9787109375.
- Independent Gate selection Test accuracy: 0.9787109375.
- Both methods achieved 1.0 member recovery and 1.0 complete-rule recovery.
- Independent selection satisfied the shared feature budget in all 30 seeds.
- The adjacency-only ablation had 0.0 member recovery and approximately 0.719314 Test accuracy.

Interpretation: the experiment supports recovery of the fixed non-contiguous relation by multi-head candidate generation, but it does **not** establish that global coordination improves on independent selection. The shared budget was inactive. Therefore E03 must not be treated as evidence that CSL arbitration is already useful.

The next coordination benchmark must include a genuine conflict condition where individually attractive candidates exceed the shared budget or are mutually incompatible, plus a no-conflict control where coordination should not harm performance. Compare independent greedy selection, budget-constrained optimization, global enumeration on tiny instances, random feasible selection, and an oracle upper bound. Keep Gate and Locked-Test separate.

### E02-I2-C audit implication: metadata is part of the threat model

The cross-branch audit also identifies a generalization/leakage risk in identity-event work: removing obvious event strings from IDs does not establish metadata-label independence if IDs or other fields can encode low-entropy seeds, episode order, window, or hidden event class. CSL provenance must distinguish evaluator-only generator metadata from learner-visible source metadata. The E12-Loop evaluator must include attacks over all observable fields—not just candidate IDs—and should use opaque IDs independent of hidden truth and episode seed. Metadata must be audited as model input, not treated as harmless bookkeeping.

## 3. Typed cognitive structure

Every candidate must declare a structure kind:

- `PREDICATE`: executable test over declared observation channels.
- `MEASUREMENT_OPERATOR`: permitted action that returns an observation with a declared cost.
- `RELATION`: predicate over two or more role-bearing participants.
- `CONCEPT`: reusable bundle of accepted predicates/relations with scope.
- `MAPPING`: role-sensitive correspondence between structures.
- `HYPOTHESIS`: explanatory candidate that may not yet be executable.

Minimum record:

```text
StructureRecord {
  structure_id, structure_kind, semantic_version,
  status, definition_digest, parent_structure_ids,
  role_schema, scope, assumptions,
  supporting_evidence_ids, contradicting_evidence_ids,
  provenance, proposer_track, created_at_step,
  compute_cost, uncertainty, calibration_summary
}
```

Identity and version are separate. A changed definition creates a new immutable version; it must not mutate the old definition in place. Candidate IDs are not proof of semantic equivalence. Equivalence requires a declared test domain and an explicit equivalence result.

## 4. Lifecycle state machine

States:

1. `PROPOSED`: generated by a track; not yet accepted.
2. `UNDER_TEST`: passed schema and executable-contract checks; evaluation pending.
3. `PROVISIONAL`: passed a declared Gate on independent evidence; scope remains limited.
4. `ACTIVE`: survived the promotion policy and has a versioned scope.
5. `CHALLENGED`: new evidence conflicts with at least one declared prediction.
6. `SUSPENDED`: no longer eligible for unqualified inference pending diagnosis.
7. `REVISED`: superseded by a new version with explicit parent lineage.
8. `SPLIT`: replaced by multiple narrower descendants.
9. `MERGED`: replaced by a new structure with multiple parents.
10. `RETIRED`: no longer proposed for use; historical record remains queryable.

Permitted transitions:

- PROPOSED -> UNDER_TEST or REJECTED
- UNDER_TEST -> PROVISIONAL, PROPOSED (needs more evidence), or REJECTED
- PROVISIONAL -> ACTIVE, CHALLENGED, or SUSPENDED
- ACTIVE -> CHALLENGED, SUSPENDED, SPLIT, MERGED, REVISED, or RETIRED
- CHALLENGED -> ACTIVE (challenge resolved), SUSPENDED, REVISED, SPLIT, MERGED, or RETIRED
- SUSPENDED -> UNDER_TEST (revalidation), REVISED, SPLIT, MERGED, or RETIRED

No direct transition from PROPOSED to ACTIVE is allowed. A transition is an append-only event, not an in-place status edit.

### 4.1 Transition gates

- Schema gate: type, roles, scope, executable contract, and provenance are valid.
- Evidence gate: evidence IDs exist, are visible to the learner at decision time, and are not evaluator-only.
- Identifiability gate: distinguish IDENTIFIABLE, AMBIGUOUS, INCONSISTENT, and BUDGET_EXHAUSTED. Agreement on current queries does not prove mechanism identity.
- Generalization gate: Gate evidence is separate from Support and Locked Test.
- Revision gate: every changed definition names its parent version, triggering evidence, expected scope change, and rollback path.
- Promotion gate: requires preregistered thresholds and at least one independent evaluation slice; thresholds are task-specific and fixed before test.
- Retirement gate: preserve historical predictions, evidence, and downstream dependency references.

### 4.2 No silent overwrite

When contradictory evidence arrives:
1. append the observation and prediction/reveal events;
2. mark affected structures CHALLENGED;
3. suspend unsupported downstream uses where required;
4. generate competing diagnoses (noise, scope violation, role mismatch, latent regime change, faulty measurement, or wrong structure);
5. choose a discriminating permitted measurement if available and budgeted;
6. revise, split, restore, or retire only after the declared gate.

A contradiction is not automatically proof that the old structure is false. It may indicate that the observation is noisy, the scope was exceeded, or the environment changed.

## 5. Event ledger and causal ordering

The shared event ledger must be append-only and replayable. Minimum event kinds:

- `OBSERVATION_RECORDED`
- `PREDICTION_COMMITTED`
- `MEASUREMENT_REQUESTED`
- `MEASUREMENT_REVEALED`
- `EVIDENCE_REVEALED`
- `CANDIDATE_PROPOSED`
- `GATE_EVALUATED`
- `LIFECYCLE_TRANSITIONED`
- `ARBITRATION_RECORDED`
- `STRUCTURE_VERSION_CREATED`
- `DEPENDENCY_INVALIDATED`

Required ordering for a held-out label:
`observation -> prediction_commit -> evaluator_reveal -> evidence_append -> lifecycle_decision`.

The learner-facing API must not expose evaluator truth, locked-test labels, hidden generator state, or future event IDs. A same-process benchmark runner is a trusted prototype, not a security boundary; high-integrity experiments should isolate evaluator truth in a separate process and communicate only through a narrow protocol.

Each event records:
`event_id, episode_id, sequence_no, track_id, event_type, payload_digest, source_ids, parent_event_ids, schema_version, timestamp_or_step`.

Content digests aid integrity checks but are not authentication. Track identity must be explicit. Event sequence allocation and append must be atomic. Replay must reproduce structure versions and decisions from the same ordered event stream and configuration.

## 6. E12-Loop benchmark

### 6.1 Episode phases

- **World setup (evaluator only):** sample a hidden mechanism, nuisance variables, sensor model, and permitted measurements.
- **Schema release:** disclose observable channels, types, action descriptions, and costs only.
- **Support:** disclose observations and labels under the preregistered support protocol.
- **Prediction:** learner proposes candidates, measurements, and predictions without access to Gate or Test.
- **Gate:** evaluator releases an independent validation slice only after candidate/prediction commit.
- **Locked Test:** labels are released only after final prediction commit; never used for candidate generation, selection, or threshold tuning.
- **Delayed challenge:** after provisional/active promotion, reveal a preregistered scope violation or counterexample in selected episodes.

### 6.2 Episode families

A. Unary predicate discovery: thresholds, parity, equality, invariants, change points.  
B. Sparse non-contiguous relation: relevant participants separated by irrelevant distractors.  
C. Role-sensitive relation: permuting roles changes outcomes.  
D. Observational equivalence: multiple mechanisms agree on all currently available evidence.  
E. Discriminating passive measurement: a permitted observation separates candidates.  
F. Nuisance shift: irrelevant channel order, scale, object identity, or missingness changes.  
G. Delayed counterexample: an accepted structure fails outside its declared scope.  
H. Concept composition: previously induced predicates combine into held-out concepts.  
I. Cross-world mapping: role structure transfers to disjoint objects or environments.  
J. Conflicting paths: multiple candidate paths share correlated evidence or make incompatible claims.

Use independent episode-level seeds and source groups. Avoid counting correlated observations from one episode as independent samples.

### 6.3 Required baselines

- frozen primitive set;
- random proposal under the same candidate budget;
- bounded correlation/frequent-pattern learner;
- support-only exact search on tiny worlds (oracle upper bound);
- no active measurement / random measurement / fixed measurement;
- one-step EIG and cost-normalized EIG;
- static relation model, ordinary graph, and sparse hypergraph;
- local track-specific lifecycle without shared CSL;
- shared CSL with majority arbitration;
- shared CSL with conflict-aware evidence arbitration;
- capacity- and compute-matched generic learned priors;
- optional Yijing/太玄/阴符 prior arms only after the generic loop is validated.

### 6.4 Primary metrics

- candidate recall, false discovery, and candidate-evaluation cost;
- identifiable-case accuracy and false-identification rate;
- ambiguity retention and abstention coverage;
- measurements-to-identification and acquisition cost;
- relation recovery and role-permutation robustness;
- held-out composition and cross-world transfer;
- nuisance-shift degradation;
- counterexample detection delay and recovery accuracy;
- structure churn: revisions/splits/merges per 100 evidence events;
- stale-dependency use after challenge;
- arbitration selective accuracy, Brier/log loss, and calibration;
- replay determinism, event-integrity failures, latency, memory, and compute.

Report episode-level paired differences and uncertainty intervals. Predeclare primary metrics and correct for multiple comparisons where confirmatory claims are made. Accuracy without coverage and cost is insufficient.

## 7. Preregistered falsification criteria

- Reject H1 if CSL does not reduce invalid transitions, stale dependency use, or contradictory state after matched workloads; do not infer benefit from code centralization alone.
- Reject H2 if ambiguity retention does not reduce false identification, or if it merely increases abstention without improving selective risk.
- Reject H3 if lineage does not improve diagnosis or transfer under identity/nuisance shifts versus metadata-matched controls.
- Reject H4 if conflict-aware arbitration fails to improve calibration or selective accuracy at matched compute, or if it only wins by using more evidence.
- Reject H5 if cooldown/gates suppress true regime adaptation or do not reduce unnecessary churn.

A result can support protocol correctness while falsifying the learning hypothesis. Publish negative and inconclusive results.

## 8. Yijing, Taixuan, and Yinfu prior isolation

The base E12-Loop must run without classical priors first. Then add separate arms:
- Zhouyi: binary complement, trigram factorization, hexagram state transitions.
- Taixuan: ternary state encoding and learnable state transitions.
- Yinfu-inspired: observation timing, context-conditioned interaction, and change-point hypotheses.

For every prior arm include no-prior, capacity-matched generic learned prior, random/permuted symbols, deliberately mismatched prior, and learnable/rejectable prior controls. Keep prior-specific labels out of the target generator unless the experiment explicitly tests a symbolic rule family. Report incremental benefit, calibration, and compute. A failed prior arm must be removable without changing the generic lifecycle contract.

## 9. Implementation sequence

1. **CSL-0 contract:** schema, status enum, legal transition table, event ordering, and validation tests.
2. **CSL-1 ledger adapter:** map existing E09 shared evidence protocol and E12 candidate/evidence/action records without copying evaluator-only data.
3. **CSL-2 lifecycle gate:** immutable versions, parent lineage, challenge/suspend/revalidate transitions, and dependency invalidation.
4. **E12-Loop-A:** unary + ambiguity + passive measurement episodes.
5. **E12-Loop-B:** sparse non-contiguous and role-sensitive relation episodes.
6. **E12-Loop-C:** held-out concept composition and nuisance shift.
7. **E12-Loop-D:** delayed counterexamples, structural revision, and replay.
8. **E03 integration:** conflict graph, evidence dependence, budget allocation, and calibrated arbitration.
9. **Prior trials:** Zhouyi, Taixuan, Yinfu arms only after the generic loop passes its controls.

Do not start large-model training before the CPU-scale loop is deterministic, leakage-audited, and independently reproducible.

## 10. Immediate decision

The next implementation target should be **CSL-0 + CSL-1**, not a new end-to-end neural model. First define one minimal typed contract and prove that existing E09/E12 records can pass through it without losing evidence lineage, phase separation, ambiguity, or track identity.

This document is a research proposal. It does not claim that CSL, E12-Loop, or the cross-track architecture is implemented, validated, or superior to existing approaches.
