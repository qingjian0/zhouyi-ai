# CPG-EI Cross-Track Research Synthesis (2026-11-11)

Status: research synthesis and implementation contract. This document is based on the current main README/ROADMAP and static reviews of E09-B, E10-A, E11-A0, plus the E02-K protocol. It is not a benchmark result and does not claim that any new experiment has passed.

## 0. Repository truth and scope

The current `main` branch describes CPG-EI v0.3 as a research draft at M1/M2: mathematical theory is under review; E01 is the minimal composition baseline; no scaled model or performance advantage is established. E02/E03/E04/E09/E10/E11 work exists on separate research branches. Those branches are not an integrated implementation and must not be described as one running system.

This synthesis is deliberately isolated on `research/cpg-ei-cross-track-synthesis-2026-11-11`. It does not modify main or any existing research branch.

## 1. Cross-track audit: what is actually established

### E02 — relation discovery and lifecycle

The repository contains increasingly careful synthetic relation-discovery experiments, including nuisance controls, environment-conditioned relations, rule-family OOD, relation identity/lifecycle, and E02-K adaptive evidence accumulation.

E02-K currently validates a bounded evidence-controller state machine, not an end-to-end learner advantage over fixed-window controls. Its LLR-like accumulator is explicitly an engineering score: clipping, adaptive candidate search, and repeated comparisons invalidate a classical SPRT error-rate interpretation. It must be calibrated empirically in an integrated generator → learner → independent gate → locked test pipeline.

### E09 — non-gradient / counterexample learning

The E09-B independent audit identifies the current learner more accurately as batch rule induction with counterexample constraints. It searches a caller-specified finite DSL and re-fits on the combined old-plus-new dataset. This does not yet demonstrate online structural revision, open grammar discovery, or self-invented operators.

The next meaningful milestone is not a larger DSL. It is a two-stage prequential interface:
1. predict before label reveal;
2. record the prediction and abstention state;
3. reveal the label;
4. append immutable evidence;
5. emit a versioned rule-structure diff with provenance.

Batch refit must remain as a control. A claimed incremental learner must show lower or bounded marginal update cost and auditable state changes without replaying all historical examples.

### E10 — analogy and structure induction

The E10-A audit found a critical evaluation-semantic issue. Participant-set grouping is not source-instance grouping. A role-near-miss derived from a base positive can replace one participant and therefore cross the current partition boundary. The full episode object table can also expose Query object identities/attributes through Support payloads.

The split tracks must remain distinct:
- A-P: participant-set group disjoint;
- A-S: source-instance group disjoint, including all derived near-miss observations;
- A-O: object-ID disjoint;
- A-C: connected-component disjoint.

A-P must not be reported as unseen-object transfer. A-S requires evaluator-only source provenance created at generation time. A-O requires disjoint object pools at world-generation time, not post-hoc filtering. Evaluator truth must be held outside the learner process, not merely hidden in a Python object field.

### E11 — concept induction

E11-A0 is a useful transparent frequent-conjunction baseline. Its learner API receives object views rather than truth labels, and its evaluator has added one-to-one matching safeguards. However:
- the initial generator has planted conjunction concepts;
- the hypothesis class is bounded attribute conjunctions;
- variable hidden concept count is a generator condition, not proof the learner estimates concept count;
- co-resident evaluator truth is an API convention, not a process boundary;
- MDL, predictive compression, relational concepts, and open-world induction remain unimplemented.

The next E11 step must test whether the learner selects concept count and boundaries from evidence under competing explanations, not merely recover planted attribute bundles.

## 2. Core conceptual correction: separate six levels of discovery

The project should not use “autonomous concept discovery” as one undifferentiated claim. Use the following capability ladder:

1. **Observation parsing** — turn raw input into stable, provenance-bearing observations.
2. **Feature/predicate induction** — propose reusable predicates from observations. A “new primitive” is operationally a new testable predicate, not a newly named token.
3. **Relation induction** — discover role-sensitive relations among predicates/objects/events.
4. **Concept induction** — discover recurring relational structures with a boundary, scope, and counterexamples.
5. **Operator induction** — discover state-transition rules that predict changes, with preconditions and postconditions.
6. **Transfer and revision** — reuse, compose, split, weaken, or retire learned structures in genuinely new worlds.

A system cannot infer an ungrounded primitive from nothing. It can only propose a new predicate over available observations/measurements, then test whether that predicate compresses and predicts held-out evidence. This prevents “invented concept” from becoming a naming exercise.

## 3. Proposed integrated computational loop

The research target should be an evidence-governed structure learner with parallel candidate search, not a monolithic “Yijing neural network”.

```text
Raw input / environment
        |
        v
Observation encoder + provenance
        |
        v
Candidate predicate and role generator
        |
        +------------------------------+
        | parallel candidate paths     |
        |                              |
        | feature conjunctions         |
        | role-sensitive motifs        |
        | event/state transitions      |
        | Yijing-inspired transforms   |
        +------------------------------+
                       |
                       v
             Identifiability analysis
        IDENTIFIABLE / AMBIGUOUS /
        INCONSISTENT / BUDGET_EXHAUSTED
                       |
                       v
             Independent evidence gate
                       |
                       v
              Immutable evidence ledger
                       |
                       v
            Structure lifecycle manager
       CREATE / KEEP / MODIFY / SPLIT /
       MERGE / SUSPEND / RETIRE / ABSTAIN
                       |
                       v
             Global path coordinator
                       |
                       v
          prediction, explanation, action
                       |
                       +---- feedback ----> next observation
```

Important: the Yijing-inspired transforms are candidate inductive biases within the candidate generator/coordinator. They must not bypass identifiability checks, evidence gates, or abstention.

## 4. Concept selection: MDL is a criterion, not an oracle

A useful objective is a pre-registered, held-out description-length comparison:

```text
Score(M) = L(M) + L(D_train | M) + lambda * L(D_gate | M)
```

This expression is only a design placeholder until a concrete coding scheme and data protocol are fixed. In particular:
- `L(M)` must charge for the number of concepts, predicate complexity, relation arity, exceptions, and operator preconditions;
- `L(D_train | M)` measures residual encoding on training evidence;
- Gate data selects among candidates but must be independent of candidate generation;
- locked Test is used once after selection;
- lambda and all complexity costs must be fixed on development seeds, not optimized on locked Test.

Compare at least:
1. frequency-only itemset baseline;
2. fixed concept-count baseline;
3. MDL / predictive-compression selection;
4. random and simple-feature baselines;
5. role-sensitive relational motif learner;
6. bounded exact-search oracle on tiny tasks.

Report both predictive quality and structural recovery. A model that predicts well using the wrong latent structure has not demonstrated concept recovery.

## 5. Identifiability and abstention are first-class outputs

For a finite observation set, several distinct latent structures may produce the same observations. The learner must not be forced to pick one.

Every candidate episode should return one of:
- `IDENTIFIABLE`: one structure is supported within the declared grammar and evidence resolution;
- `AMBIGUOUS`: multiple materially different structures remain observationally equivalent;
- `INCONSISTENT`: no candidate in the declared grammar explains the evidence within tolerance;
- `BUDGET_EXHAUSTED`: search budget ended before a defensible decision.

The evaluator should test these states with paired worlds that are observationally indistinguishable under Support but diverge under a specified intervention or new context. This separates genuine discovery from accidental fit.

## 6. Yijing-inspired computational hypotheses

Do not hard-code traditional correspondences as truths. Treat each as a hypothesis family with matched controls.

| Yijing concept | Computational hypothesis | Required control |
|---|---|---|
| Yin/Yang | complementary binary state factorization | ordinary binary features; learned two-state code |
| Four Images | coarse phase/state partition | k-state clustering with same capacity |
| Eight Trigrams | structured factorization of multi-axis state | generic factorized latent code |
| 64 Hexagrams | compositional high-order state code | same-size unconstrained codebook |
| Line change / Gua change | sparse state-transition operators | generic finite-state transition learner |
| Mutual/overall/opposite transforms | alternative views / structured transformations | random transforms and learned transforms |
| Five phases | directed transition/interaction prior | unconstrained learned relation matrix |

For every hypothesis, run:
- no Yijing prior;
- fixed Yijing-inspired prior;
- learnable Yijing-inspired prior;
- parameter- and compute-matched generic prior.

Measure sample efficiency, OOD transfer, calibration, abstention, compute cost, and robustness to deliberately incorrect correspondences. A prior that cannot be rejected is a source of confirmation bias.

## 7. Parallel candidate paths: avoid both serial bottlenecks and combinatorial explosion

The user's original design allows simultaneous combinations and skipping intermediate elements. Operationalize it as sparse candidate hyperedges over typed observations, not exhaustive enumeration of every subset.

Each path has:
- candidate structure;
- source evidence IDs;
- generation method;
- compute budget;
- predictive score on its permitted split;
- counterexamples;
- novelty relative to existing paths;
- status and version lineage.

The coordinator should compare candidates on shared Gate evidence, penalize redundant extensions, preserve genuinely distinct hypotheses when evidence is insufficient, and abstain when the budget is exhausted. Candidate paths must not see locked Test or evaluator truth.

A fair comparison should include:
- serial greedy search;
- parallel independent search with fixed total compute;
- parallel search with shared adaptive budget;
- random candidate search;
- exact enumeration on tiny spaces.

The key question is not “does parallel search create more candidates?” but “does it improve the best defensible structure found at the same total compute budget?”

## 8. Priority order: fix validity before adding sophistication

### P0 — evaluation integrity
1. E10-A source_group provenance and A-S regression tests.
2. E10-A learner payload isolation and separate evaluator process.
3. E11 evaluator truth process boundary.
4. E11 threshold sensitivity and locked-seed preregistration.
5. Every benchmark reports split semantics and failure/abstention counts.

### P1 — genuine learning over time
1. E09 immutable evidence ledger integration.
2. E09 observe-before-feedback prequential interface.
3. Rule/concept version lineage with support and counterexample IDs.
4. Batch-refit versus incremental-update compute comparison.

### P2 — actual concept induction
1. E11 unknown concept-count estimation.
2. MDL / predictive-compression versus frequency-only.
3. Role-sensitive relational concept grammar.
4. Identifiability/ambiguity benchmark.
5. World-family-disjoint and object-disjoint transfer.

### P3 — architecture-level claims
1. E03 global coordinator against equal-budget serial/parallel controls.
2. E04 Yijing-inspired priors as ablation arms.
3. E10 analogy and operator induction on validated split tracks.
4. Integrated end-to-end pipeline only after each component has a stable contract.

## 9. Release and claim policy

- Main remains the v0.3 M1/M2 research baseline until an explicit review and integration decision.
- No research branch is assumed merged because its PR exists.
- No unit test, CI, or benchmark is called passed unless the exact commit/run is inspected.
- Synthetic Boolean/conjunction success must not be described as natural-language understanding, causal discovery, general intelligence, or open-world autonomy.
- Report confidence intervals at the independent episode/world-seed level, not by pretending correlated rows are independent.
- Keep failed seeds, ambiguous episodes, budget exhaustion, and null controls in the report.

## 10. Immediate next implementation contract

The highest-leverage next implementation is **E10-A provenance + E09 evidence protocol as shared infrastructure**, not another layer of Yijing symbolism.

Suggested independent implementation sequence:
1. Add evaluator-only `source_group_id` at generator creation time.
2. Implement A-S split while retaining A-P as a separate baseline.
3. Serialize learner Support and Query payloads separately from evaluator truth.
4. Add recursive payload-canary tests and truth-mutation invariance tests.
5. Define a shared immutable evidence record schema for E09/E10/E11.
6. Add prequential `predict → reveal → append → revise` contract.
7. Only then connect E11 concept candidates and E10 analogy/operator candidates to the shared coordinator.

This is the shortest path to making the project's autonomy claims scientifically testable. It is intentionally conservative: improve the trustworthiness of the learning loop before increasing the expressive power of its hypothesis language.


---

## 11. 2026-11-11 update: E10-A / E12 evidence changes

This addendum records the newer open-PR evidence inspected after the initial cross-track synthesis. It does not retroactively change the status of earlier branches or imply that open PRs are integrated.

### 11.1 E12-A3: adaptive proposal allocation has a negative first result

PR #68 reports a matched 31-proposal-slot comparison over 40 episodes (20 seeds × 2 task families):

| Method | Mean Locked-Test accuracy |
|---|---:|
| EQUAL | 91.72% |
| ROUND_ROBIN | 91.72% |
| UCB1 adaptive, mean batch reward | 90.47% |
| BOUNDED_ENUM | 90.08% |

The UCB1-minus-EQUAL contrast is -1.25 percentage points, with a paired 95% t interval of [-2.94, +0.44] pp. Five reward ablations also failed to exceed the fixed-allocation controls. This is evidence against the current context-free adaptive allocator, not evidence against all adaptive allocation.

The proposed M1.2 Support-context router is a better next test because it asks whether task-local evidence can identify a specialist proposer. It must be compared against equal allocation with identical context-probe and proposal-slot costs. Its Gate-Final and Locked-Test partitions must remain inaccessible to routing.

### 11.2 E12-A2: active measurement is more mature, but remains finite-world

PR #62 reports successful workflow runs for exact finite-world measurement selection and a noisy-prior stress benchmark. The expanded noisy-prior sweep reports 13,500 episodes and 120 paired prior-vs-uniform contrasts. The key caution is that an anti-aligned prior can worsen proper scores and increase confident errors; a uniform contamination floor can mitigate some harm but is task-dependent.

The engineering implication is important: Yixiang priors should be treated as defeasible proposal distributions, not as privileged truth. The learner must preserve a uniform/no-prior arm, expose prior provenance, and allow evidence to overturn the prior. These experiments use finite synthetic worlds and do not yet establish a benefit from a Yijing prior.

### 11.3 E12-M2: motif discovery is a candidate generator, not semantic discovery

PR #84 adds bounded discrete motif mining, a degree-preserving conditional null, max-statistic correction, and synthetic calibration. The branch explicitly distinguishes a statistical co-occurrence motif from a semantic primitive. Latest Wilson-interval assertions and the dedicated CI smoke step were added after the last reported passing run, so the exact latest head is not yet CI-verified.

Before treating M2 as a reliable primitive proposer, require:
- calibrated type-I error under the exact full search procedure;
- power curves across planted effect sizes and sample sizes;
- null robustness under heterogeneous row degrees and dependence;
- runtime, memory, and permutation-chain diagnostics;
- independent-world transfer and comparison with simpler frequency/association baselines.

### 11.4 E10-A: richer feature composition increases the need for provenance and isolation

PR #83 adds bounded prequential primitive expansion over visible relation symbols and supplied attribute keys. PR #89 adds conjunctive object-feature composition where single attributes alias roles but feature pairs can distinguish them. Both remain finite symbolic search over generator-supplied features; neither learns raw sensory encoders or open-world semantics.

PR #89's eight-seed benchmark and random-proposal comparison remain future work, and its tests are authored without a claimed pass. PR #90 is a validation-only mirror and must not be merged. The earlier P0 requirements remain binding: source-instance provenance at generation time, object-disjoint evaluation where claimed, and evaluator/learner process isolation.

### 11.5 E12-A5: residual diagnosis and operator expansion need statistical and temporal controls

PR #87 diagnoses numeric feature pairs from prequential or out-of-fold residuals; PR #88 applies a full-scan max-statistic permutation correction. PR #82 consumes the diagnosed pairs to expand a bounded operator family. These form a useful candidate loop:

`predict → residual → diagnose → propose operator → independent Gate → locked evaluation`

However, maxT's global-null interpretation is not automatically strong FWER control under arbitrary partial nulls. Exchangeability is also not guaranteed for temporal, clustered, or repeated-entity streams. Block/cluster permutation and provenance-enforced prequential integration remain required. This is association diagnosis, not causal attribution.

## 12. Revised execution order

1. **Finish evidence integrity first:** E10-A source-instance split and evaluator isolation; shared immutable evidence/provenance contract across E09/E10/E11/E12.
2. **Close the E12-A3 negative-result loop:** inspect M1.2 Support-context router under equal total cost. Do not keep tuning UCB1 against the same Gate-Final/Locked-Test data.
3. **Integrate E12-A2 only as a defeasible observation policy:** compare uniform, learned, Yixiang-prior, and contaminated-prior arms on identical sensor streams and report calibration as well as accuracy.
4. **Harden E12-M2 statistics:** complete calibration and power analysis before allowing motif candidates to enter the semantic concept pool.
5. **Connect E12-A5 to the prequential ledger:** ensure residual provenance is machine-enforced, then add block/cluster permutation for dependent observations.
6. **Run one small end-to-end benchmark only after contracts stabilize:** parallel proposers (feature, relation, motif, operator, Yixiang transform) share a fixed compute budget; coordinator selects on Gate-Dev; Gate-Final freezes the structure; Locked Test evaluates once.
7. **Measure the user's core non-autoregressive claim directly:** compare sparse non-contiguous candidate composition and parallel path aggregation against serial greedy, fixed-local, random, and exact-small-space controls at matched compute. Keep the language model only as an external parser/decoder control, and report its contribution separately.

### 12.1 Updated minimum acceptance record

Every integrated episode must log:
- immutable observation and evidence IDs, source-instance and object-group IDs;
- candidate generator family, candidate expression, parent lineage, and prior version;
- proposal count, unique evaluations, CPU time/FLOPs proxy, memory, and wall-clock time;
- Support / Gate-Dev / Gate-Final / Locked-Test provenance;
- prediction made before reveal, abstention, reveal event, append event, and revision diff;
- ambiguity, inconsistency, budget exhaustion, counterexamples, and all failed seeds;
- separate predictive accuracy, structural recovery, calibration, transfer, and compute metrics.

No aggregate accuracy alone is sufficient to claim concept induction or architectural superiority.

---

## 13. Second-round repository audit: shared protocol versus duplicated prototypes

Audit date: 2026-11-11. This is a static source audit of E09, E10-A, E03-A, E11-A0/A-B, and open PR #53. No new tests or benchmark runs are claimed.

### 13.1 Current implementation facts

**E09-B2 evidence ledger**
- Append-only behavior is implemented in an in-memory ledger.
- Stable sample IDs, idempotent replay, conflicting-label isolation, source-count metadata, and atomic batch validation are specified.
- The ledger is not persistent, signed, concurrency-safe, or a trusted source-authentication mechanism.
- Its research note says tests are authored but not yet run.

**E09-B0.2 prequential runner**
- A predict-and-commit, reveal, revise state machine is implemented.
- Prediction records retain observation ID, model version, decision/abstention state, and step order.
- Revision snapshots retain before/after structure and cost proxies.
- The only revision strategy is BATCH_REFIT, which re-fits on all eligible historical evidence. This is a valid baseline, not an incremental learner.
- Candidate-evaluation count and training-row count are not substitutes for measured latency, memory, or actual compute.

**E10-A prequential ledger**
- A separate in-memory ledger prototype enforces commit-before-reveal, one-time reveal, immutable prediction commits, evidence-bounded revisions, detached snapshots, monotonic steps, and fail-closed validation.
- It has no integrated learner, evaluator process, persistent event store, structure-version registry, or benchmark runner.
- Its design note explicitly states that a single ledger object is a trusted-runner state machine, not a security boundary.

**E03-A parallel coordination**
- The experiment has three output channels, each with an unknown non-affine three-variable Boolean relation.
- Each channel considers 84 two-/three-feature subsets, retains up to eight candidates, and the coordinator enumerates at most 8^3 combinations under a shared feature budget of five.
- The target relations deliberately include non-contiguous feature sets.
- The coordinator is an explicit bounded optimizer over a researcher-specified candidate space. This does not yet show that the coordinator policy itself is learned.

**E11-A0 and E11-A/B**
- E11-A0 is a frequent-conjunction baseline over a generator that plants exactly three concepts, each a conjunction of three opaque attributes.
- Its evaluator's best-match F1 is diagnostic and is not yet an operational candidate-to-concept assignment rule.
- E11-A/B defines a richer concept schema with typed slots, predicates, role-sensitive relations, boundaries, invariants, context, and evidence; it remains a specification/preregistration draft without a learner implementation or benchmark result.

### 13.2 Architectural decision: one protocol, multiple learners

Do not merge E09's and E10-A's current ledger implementations as-is, and do not create one monolithic learner.

Adopt a versioned shared event protocol with track-specific adapters:

- Shared: observation envelope, prediction commit, reveal event, evidence reference, structure-version reference, revision event, provenance rules, and cost accounting.
- E09 adapter: predicate/rule AST and counterexample repair.
- E10 adapter: role-sensitive relation, analogy, and operator structures.
- E11 adapter: concept schema, boundary, and typed hierarchy edges.
- E02 adapter: relation identity, adjudication, and evidence sufficiency.
- E03 coordinator: candidate-path scheduling and shared-budget arbitration.

The protocol defines semantics and invariants, not one storage library, model family, or hypothesis grammar.

### 13.3 Required event envelope

Every event should have a deterministic envelope:

- protocol_version
- event_id
- episode_id
- sequence_no
- event_type
- actor_role
- causation_refs
- payload_schema
- payload_digest
- created_at
- integrity_metadata

The event body is typed by event class. Evaluator-only source IDs and labels must never appear in learner event serialization. A digest detects accidental mutation; it does not authenticate an actor unless backed by a trusted signature/key boundary.

Required invariants:
1. Event IDs are unique within the declared namespace.
2. Sequence numbers are strictly increasing within an episode.
3. A reveal references exactly one committed prediction.
4. A revision references only evidence already revealed at its sequence number.
5. An identical replay is idempotent; same ID with different content is a hard integrity error.
6. Historical commits and revisions are never overwritten.
7. A split/merge creates new immutable structure versions and explicit lineage.
8. ABSTAIN is a valid decision, not a missing prediction.
9. Event persistence acknowledgment occurs before the evaluator reveals the target.
10. Recovery after process restart reproduces the same event order and model-version references.

### 13.4 The next vertical slice: E09 first, E10-A second

**Slice A — E09**
- Preserve the current batch-refit runner as the immutable baseline.
- Put the shared protocol adapter around it without changing its learning semantics.
- Add a second, separately named incremental candidate-maintenance strategy.
- Instrument actual per-update wall-clock time, peak memory, candidate evaluations, and historical evidence scanned.
- Test restart/replay and event-log reconstruction.
- Compare frozen, batch-refit, periodic replay, and incremental revision at equal cumulative compute.

**Slice B — E10-A**
- Reuse the protocol adapter, not E09's rule AST.
- Run strict A-S source-instance and A-O object-disjoint tracks.
- Put evaluator truth and source provenance in a separate process.
- Verify learner payload bytes are invariant under mutation of evaluator-only truth.
- Add structure-version lineage for relation and operator revisions.

**Slice C — E11**
- Feed concept proposals through the same event protocol.
- Remove the planted fixed concept count as a learner-visible assumption.
- Add nuisance-correlated and overlapping concepts, unknown concept counts, missing attributes, and relational/non-conjunctive concepts.
- Replace evaluator best-match scoring with a frozen matching procedure plus assignment-free set metrics.
- Test whether hierarchy edges add predictive/compositional value over a flat concept set at matched information and compute.

### 13.5 Research update from external literature

The 2026 ICML paper **INDUCTION: Finite-Structure Concept Synthesis in First-Order Logic** provides a useful benchmark-design reference. It separates full observation, contrastive induction, and existential completion; it also evaluates formula validity and complexity, and reports that compact formulas generalize better than bloated fits. CPG-EI should borrow the separation of structural validity from predictive fit, while extending it with prequential revision, evidence provenance, ambiguity, and non-contiguous composition.

Reference: https://proceedings.mlr.press/v306/batzoglou26a.html

The March 2026 systematic review **Continual learning: A systematic literature review** surveys continual-learning work from 2010–2025 and highlights the need to reason about forgetting mechanisms and learning settings rather than report one aggregate score. CPG-EI should distinguish task-incremental, class-incremental, domain/stream drift, and structural-concept revision; these are not interchangeable evaluation settings.

Reference: https://www.sciencedirect.com/science/article/pii/S0893608025011074

A 2025 PMLR paper, **Causality in Flux: Continual Adaptation of Causal Knowledge via Evidence Matching**, is a relevant conceptual comparator for evidence-conditioned knowledge revision. Its scope is causal-model adaptation, not proof that CPG-EI's symbolic event ledger provides causal discovery.

Reference: https://proceedings.mlr.press/v268/seng25a.html

### 13.6 New benchmark matrix

| Dimension | Required levels |
|---|---|
| Observation stream | static / sequential / drift / noisy |
| Concept structure | conjunction / relational / temporal / operator |
| Composition | adjacent / non-contiguous / role-sensitive / multi-output |
| Identifiability | identifiable / ambiguous / inconsistent |
| Split | instance / source-group / object / world-family |
| Learning mode | frozen / batch-refit / replay / incremental |
| Search mode | greedy serial / independent parallel / shared-budget adaptive |
| Yixiang prior | absent / fixed / learnable / randomized / deliberately wrong |
| Feedback | immediate / delayed / partial / contradictory |
| Budget | proposal slots / measured time / memory / total compute |

Report prediction quality, structure recovery, calibration, abstention, revision quality, transfer, and compute separately. Do not collapse these into one headline score.

### 13.7 New falsifiable hypotheses

- H13-1 Protocol sufficiency: different learner tracks can use the same event semantics without sharing their hypothesis representations.
- H13-2 Incremental benefit: incremental candidate maintenance can match or approach batch-refit quality with lower marginal update cost on at least one pre-registered stream family.
- H13-3 Revision stability: evidence-gated revisions reduce unnecessary structure oscillation under transient noise without blocking adaptation to persistent drift.
- H13-4 Concept utility: concepts selected by predictive compression improve held-out relational prediction over frequency-only patterns at matched search budget.
- H13-5 Parallel value: parallel proposer coordination improves the best defensible held-out structure at equal total measured compute, not merely candidate count.
- H13-6 Yixiang contribution: Yixiang-inspired priors provide reproducible sample-efficiency or transfer gains over parameter/compute-matched generic priors, while remaining rejectable under wrong-prior controls.

Each hypothesis must be tested on independent world seeds, with locked tests used only after selection. Null results and failed episodes remain in the report.

### 13.8 Immediate next action

Before implementing another new learner, reconcile PR #53 with the existing E09 and E10-A ledger prototypes:
1. compare every event invariant against both prototypes;
2. mark which are already enforced, only documented, or absent;
3. define a minimal compatibility adapter and migration test;
4. avoid duplicating event storage or changing track-specific candidate schemas;
5. run exact focused tests and CI only after the adapter exists.

This is now the project's highest-leverage engineering task. The next model-level innovation should wait until the evidence protocol is trustworthy and shared.


### 14. Third-round audit: PR #53 compatibility against E09 and E10-A implementations

Audit date: 2026-11-11. Method: read-only source and test inspection across the independent E09 and E10-A research branches. This is a static audit; no tests were executed in this audit.

#### 14.1 Branch and scope clarification

PR #53 is still a draft design-only change. Its head branch contains the shared contract document and the repository baseline, but it does not contain the E09 prequential implementation or E10-A ledger implementation. Those implementations live on separate research branches:

- E09 prequential runner: `research/e09-prequential-runner-2026-11-11`
- E09 incremental learner arm: `research/e09-incremental-conjunction-index-2026-11-11`
- E10-A prequential ledger: `research/e10a-prequential-ledger-prototype-2026-11-11`
- E10-A phase-gated runner: `research/e10a-phase-gated-runner-2026-11-11`

Therefore PR #53 cannot be treated as an integration commit or as evidence that its contract is enforced by either implementation.

#### 14.2 Compatibility matrix

Legend: **E** = enforced by inspected implementation; **P** = partial or narrower semantics; **D** = documented only; **M** = missing in inspected implementation.

| Contract invariant / capability | E09-B runner + ledger | E10-A ledger | Shared contract target |
|---|---|---|---|
| Prediction commit precedes reveal | E, in runner memory | E, event order | E |
| Reveal references a prior commit | E | E | E |
| One reveal per prediction | E | E | E |
| One commit per observation | E, runner checks observation IDs | P, duplicate commits for one observation are possible before reveal | E |
| Immutable prediction history | P, separate in-memory dictionary, not in evidence ledger | E, append-only event list in memory | E |
| Stable event ID and monotonic sequence | P, generated prediction/reveal IDs and runner step | E, per-episode generated IDs and step | E |
| Global event envelope (actor, causation, schema, integrity metadata) | M | P, schema version only; lacks actor, causation refs, per-event payload schema and integrity metadata | E |
| Identical event replay is idempotent | P, evidence records only; runner commands are not replay-idempotent | M, duplicate IDs are rejected rather than accepted as identical replay | E |
| Same ID with different content is rejected | E for evidence sample IDs | E for prediction/reveal/revision IDs | E |
| Conflicting labels are quarantined from fitting | E | M | Track-specific adapter policy |
| Structure versions with immutable parent/child lineage | M, model snapshots are not a structure registry | M, before/after version IDs are references only | E |
| Revision may cite only already revealed evidence | E, reveal required before revise | E, unknown/unrevealed reveal IDs rejected | E |
| Durable persistence acknowledged before reveal | M | M | E |
| Deterministic restart and replay | M | M | E |
| Evaluator/learner process isolation | M | M; explicitly documented as not a security boundary | E |
| Payload canary against evaluator-only truth | M | M | E |
| Actual update latency and peak memory | M | M; caller-supplied cost dictionary only | E |
| Historical scan / replay work counted | P, training row and candidate evaluation counters only | M | E |

Important distinction: a monotonic in-memory step counter is not durable ordering. A snapshot hash is not a hash chain, an event signature, or proof of source authenticity. Caller-supplied cost metadata is not measured resource usage.

#### 14.3 Implementation-specific findings

**E09-B**

Inspected files:
- `prototype/e09_evidence_ledger.py`
- `prototype/e09_prequential.py`
- `tests/test_e09_evidence_ledger.py`
- `tests/test_e09_prequential.py`

The evidence ledger has useful properties: immutable sample IDs, idempotent identical evidence append, conflicting sample-ID rejection, conservative quarantine of contradictory labels for the same input, same-label deduplication for fitting, source-ID counts, and atomic validation of batch extension.

The prequential runner wraps the learner with predict/commit/reveal/revise. However:
- Prediction commits, reveals, and revisions live in runner-owned in-memory collections, not in a single durable event store.
- Reveal appends the training evidence to the evidence ledger, but prediction and revision history remain separate structures.
- Revision mode is explicitly `BATCH_REFIT`; it calls the existing full-data `fit()`.
- Candidate-evaluation and training-row counts are not latency, memory, or historical-scan measurements.
- No restart/replay mechanism or evaluator process boundary is implemented.
- The runner increments its step before evidence append completes; a rejected append can leave a step gap. The adapter should make state transition and event append atomic from the caller's perspective.

**E10-A**

Inspected files:
- `prototype/e10a_prequential_ledger.py`
- `tests/test_e10a_prequential_ledger.py`
- `docs/E10A_PREQUENTIAL_LEDGER_PROTOTYPE_2026-11-11.md`

The ledger has a cleaner unified in-memory event list, detached snapshots, canonical snapshot hashing, unique event IDs within an episode, prediction-before-reveal checks, one reveal per observation, explicit abstention states, and rejection of revisions that cite unrevealed evidence.

However:
- Two commits for the same observation can be created before that observation is revealed; the shared contract should require one canonical prediction commit per observation unless a named multi-candidate protocol explicitly allows otherwise.
- Duplicate IDs are rejected even if the event payload is byte-identical; this is not idempotent replay.
- Event IDs are generated locally and scoped by episode; no cross-episode namespace or externally supplied idempotency key is defined.
- The snapshot hash covers the event list but there is no per-event hash chain, durable store, signature, or restart recovery.
- The ledger holds both prediction and revealed target in one object. It is explicitly a trusted-runner state machine, not evaluator/learner isolation.
- Revision events refer to version ID strings, but no registry verifies that versions exist, that parent links are valid, or that a split/merge creates immutable lineage records.
- Resource-cost dictionaries are accepted from callers; the ledger does not measure actual cost.

#### 14.4 Minimal compatibility adapter: contract, not another learner

Do not replace either learner or merge the two ledgers directly. Introduce a protocol adapter with the following narrow surface:

- `append_observation(observation_envelope) -> event_receipt`
- `commit_prediction(prediction_commit, idempotency_key) -> durable_receipt`
- `reveal_evidence(reveal, commit_receipt) -> event_receipt`
- `append_revision(revision_event) -> event_receipt`
- `replay_episode(episode_id, from_sequence) -> ordered_events`
- `snapshot_structure(episode_id, structure_version_id) -> immutable_structure_record`

Adapter rules:

1. Validate a versioned envelope before touching the event store.
2. Make the idempotency key stable across retries. Same key plus same canonical payload returns the original receipt; same key plus different payload is an integrity error.
3. Persist and acknowledge the prediction commit before evaluator reveal is permitted.
4. Keep evaluator-only target and source provenance out of learner-facing serialization.
5. Enforce one prediction commit per observation by default. Any multi-hypothesis or multi-view exception must use a distinct protocol mode and explicit parent observation reference.
6. Keep protocol events generic. Put E09 rule AST, E10 relation/operator AST, and E11 concept AST in versioned, track-specific payload schemas.
7. Record StructureVersion creation as its own event. Validate parent versions, support/counterexample evidence references, and split/merge lineage.
8. Use a transactional append or compare-and-append sequence check so concurrent writers cannot create duplicate sequence numbers.
9. Treat payload digests as mutation-detection metadata only. Authentication requires a separately specified trust/key boundary.
10. Separate measured telemetry from declared budget: record wall-clock duration, peak memory, candidate evaluations, evidence rows scanned, bytes read/written, and replay work with measurement provenance.

#### 14.5 Migration strategy

**M0 — freeze semantics**
- Define canonical envelope and payload schemas.
- Define ID namespaces, idempotency, sequence scope, and error behavior.
- Add compatibility fixtures for existing E09 and E10 snapshots.

**M1 — protocol conformance tests**
- Commit-before-reveal and durable acknowledgement.
- Duplicate retry with identical payload.
- Duplicate retry with conflicting payload.
- Concurrent append / stale sequence rejection.
- One commit per observation.
- No future evidence references in revisions.
- Structure parent/child lineage and split/merge invariants.
- Deterministic replay from a clean process.
- Evaluator-only truth mutation leaves learner payload bytes unchanged.

**M2 — E09 adapter**
- Wrap current E09 ledger without changing the learner's rule grammar.
- Preserve `BATCH_REFIT` as a named baseline.
- Integrate the separate incremental candidate-maintenance arm only as a distinct strategy.
- Add restart/replay and actual cost instrumentation.

**M3 — E10-A adapter**
- Reuse the protocol adapter, not the E09 learner representation.
- Integrate the phase-gated A-O runner and strict A-S source-instance split.
- Move evaluator truth and source provenance behind a separate process/service boundary.
- Add versioned relation/operator structures.

**M4 — cross-track acceptance**
- Run the same conformance suite against both adapters.
- Compare behavior and compute under frozen, batch-refit, replay, and incremental arms.
- Do not merge until both adapters pass the protocol suite and their own track-specific split/evaluator controls.

#### 14.6 Research implications: incremental is a hypothesis, not a default objective

The literature reinforces a caution relevant to E09. The 2025 survey/update on supervised learning from data streams distinguishes instance-incremental from batch-incremental updates and argues that online updates should be justified against traditional alternatives, including replay and retraining. The 2025 ICML work on retraining decisions frames update choice as a trade-off under limited evidence, unknown drift, and retraining cost. A 2026 empirical preprint comparing refresh policies likewise emphasizes update mode, budget, and deployment latency rather than assuming a reactive policy is automatically superior.

Implication for Zhouyi-AI: the acceptance target is not "incremental beats batch in every setting". It is a pre-registered operating-region map showing when incremental maintenance, periodic replay, or batch refit gives the best structure quality under the same total measured budget.

References:
- Supervised Learning from Data Streams: An Overview and Update (2025): https://doi.org/10.1145/3737279
- When to retrain a machine learning model (ICML 2025): https://proceedings.mlr.press/v267/regol25a.html
- When to Retrain: An Empirical Study of Retraining Policies for Streaming ML Under Concept Drift, Budget, and Latency Constraints (2026 preprint): https://arxiv.org/abs/2608.19488
- Online Event Processing (Communications of the ACM, 2019): https://www.cl.cam.ac.uk/~arb33/papers/KleppmannBeresfordSvingen-OnlineEventProcessing-CACM2019.pdf

#### 14.7 Decision and next gate

Decision: PR #53 is a useful protocol design contract, but it is not yet an implementation specification detailed enough to serve as a conformance target without the additions above.

The next engineering step should be a small, independent protocol-conformance package and adapter tests, not another learner and not a third ledger implementation. Keep PR #53 draft until the envelope, idempotency, durable commit, replay, and structure-lineage semantics are made precise. Keep all learner-specific candidate representations separate.

Status after this audit:
- Static source audit: completed.
- Compatibility matrix: documented here.
- Adapter implementation: not started.
- Protocol conformance tests: not started.
- Tests/CI: not run in this audit.
- Main branch: unchanged.
- PR #53: unchanged and unmerged.


### 14. Third-round audit: PR #53 compatibility against E09 and E10-A implementations

Audit date: 2026-11-11. Method: read-only source and test inspection across the independent E09 and E10-A research branches. This is a static audit; no tests were executed in this audit.

#### 14.1 Branch and scope clarification

PR #53 is still a draft design-only change. Its head branch contains the shared contract document and the repository baseline, but it does not contain the E09 prequential implementation or E10-A ledger implementation. Those implementations live on separate research branches:

- E09 prequential runner: `research/e09-prequential-runner-2026-11-11`
- E09 incremental learner arm: `research/e09-incremental-conjunction-index-2026-11-11`
- E10-A prequential ledger: `research/e10a-prequential-ledger-prototype-2026-11-11`
- E10-A phase-gated runner: `research/e10a-phase-gated-runner-2026-11-11`

Therefore PR #53 cannot be treated as an integration commit or as evidence that its contract is enforced by either implementation.

#### 14.2 Compatibility matrix

Legend: **E** = enforced by inspected implementation; **P** = partial or narrower semantics; **D** = documented only; **M** = missing in inspected implementation.

| Contract invariant / capability | E09-B runner + ledger | E10-A ledger | Shared contract target |
|---|---|---|---|
| Prediction commit precedes reveal | E, in runner memory | E, event order | E |
| Reveal references a prior commit | E | E | E |
| One reveal per prediction | E | E | E |
| One commit per observation | E, runner checks observation IDs | P, duplicate commits for one observation are possible before reveal | E |
| Immutable prediction history | P, separate in-memory dictionary, not in evidence ledger | E, append-only event list in memory | E |
| Stable event ID and monotonic sequence | P, generated prediction/reveal IDs and runner step | E, per-episode generated IDs and step | E |
| Global event envelope (actor, causation, schema, integrity metadata) | M | P, schema version only; lacks actor, causation refs, per-event payload schema and integrity metadata | E |
| Identical event replay is idempotent | P, evidence records only; runner commands are not replay-idempotent | M, duplicate IDs are rejected rather than accepted as identical replay | E |
| Same ID with different content is rejected | E for evidence sample IDs | E for prediction/reveal/revision IDs | E |
| Conflicting labels are quarantined from fitting | E | M | Track-specific adapter policy |
| Structure versions with immutable parent/child lineage | M, model snapshots are not a structure registry | M, before/after version IDs are references only | E |
| Revision may cite only already revealed evidence | E, reveal required before revise | E, unknown/unrevealed reveal IDs rejected | E |
| Durable persistence acknowledged before reveal | M | M | E |
| Deterministic restart and replay | M | M | E |
| Evaluator/learner process isolation | M | M; explicitly documented as not a security boundary | E |
| Payload canary against evaluator-only truth | M | M | E |
| Actual update latency and peak memory | M | M; caller-supplied cost dictionary only | E |
| Historical scan / replay work counted | P, training row and candidate evaluation counters only | M | E |

Important distinction: a monotonic in-memory step counter is not durable ordering. A snapshot hash is not a hash chain, an event signature, or proof of source authenticity. Caller-supplied cost metadata is not measured resource usage.

#### 14.3 Implementation-specific findings

**E09-B**

Inspected files:
- `prototype/e09_evidence_ledger.py`
- `prototype/e09_prequential.py`
- `tests/test_e09_evidence_ledger.py`
- `tests/test_e09_prequential.py`

The evidence ledger has useful properties: immutable sample IDs, idempotent identical evidence append, conflicting sample-ID rejection, conservative quarantine of contradictory labels for the same input, same-label deduplication for fitting, source-ID counts, and atomic validation of batch extension.

The prequential runner wraps the learner with predict/commit/reveal/revise. However:
- Prediction commits, reveals, and revisions live in runner-owned in-memory collections, not in a single durable event store.
- Reveal appends the training evidence to the evidence ledger, but prediction and revision history remain separate structures.
- Revision mode is explicitly `BATCH_REFIT`; it calls the existing full-data `fit()`.
- Candidate-evaluation and training-row counts are not latency, memory, or historical-scan measurements.
- No restart/replay mechanism or evaluator process boundary is implemented.
- The runner increments its step before evidence append completes; a rejected append can leave a step gap. The adapter should make state transition and event append atomic from the caller's perspective.

**E10-A**

Inspected files:
- `prototype/e10a_prequential_ledger.py`
- `tests/test_e10a_prequential_ledger.py`
- `docs/E10A_PREQUENTIAL_LEDGER_PROTOTYPE_2026-11-11.md`

The ledger has a cleaner unified in-memory event list, detached snapshots, canonical snapshot hashing, unique event IDs within an episode, prediction-before-reveal checks, one reveal per observation, explicit abstention states, and rejection of revisions that cite unrevealed evidence.

However:
- Two commits for the same observation can be created before that observation is revealed; the shared contract should require one canonical prediction commit per observation unless a named multi-candidate protocol explicitly allows otherwise.
- Duplicate IDs are rejected even if the event payload is byte-identical; this is not idempotent replay.
- Event IDs are generated locally and scoped by episode; no cross-episode namespace or externally supplied idempotency key is defined.
- The snapshot hash covers the event list but there is no per-event hash chain, durable store, signature, or restart recovery.
- The ledger holds both prediction and revealed target in one object. It is explicitly a trusted-runner state machine, not evaluator/learner isolation.
- Revision events refer to version ID strings, but no registry verifies that versions exist, that parent links are valid, or that a split/merge creates immutable lineage records.
- Resource-cost dictionaries are accepted from callers; the ledger does not measure actual cost.

#### 14.4 Minimal compatibility adapter: contract, not another learner

Do not replace either learner or merge the two ledgers directly. Introduce a protocol adapter with the following narrow surface:

- `append_observation(observation_envelope) -> event_receipt`
- `commit_prediction(prediction_commit, idempotency_key) -> durable_receipt`
- `reveal_evidence(reveal, commit_receipt) -> event_receipt`
- `append_revision(revision_event) -> event_receipt`
- `replay_episode(episode_id, from_sequence) -> ordered_events`
- `snapshot_structure(episode_id, structure_version_id) -> immutable_structure_record`

Adapter rules:

1. Validate a versioned envelope before touching the event store.
2. Make the idempotency key stable across retries. Same key plus same canonical payload returns the original receipt; same key plus different payload is an integrity error.
3. Persist and acknowledge the prediction commit before evaluator reveal is permitted.
4. Keep evaluator-only target and source provenance out of learner-facing serialization.
5. Enforce one prediction commit per observation by default. Any multi-hypothesis or multi-view exception must use a distinct protocol mode and explicit parent observation reference.
6. Keep protocol events generic. Put E09 rule AST, E10 relation/operator AST, and E11 concept AST in versioned, track-specific payload schemas.
7. Record StructureVersion creation as its own event. Validate parent versions, support/counterexample evidence references, and split/merge lineage.
8. Use a transactional append or compare-and-append sequence check so concurrent writers cannot create duplicate sequence numbers.
9. Treat payload digests as mutation-detection metadata only. Authentication requires a separately specified trust/key boundary.
10. Separate measured telemetry from declared budget: record wall-clock duration, peak memory, candidate evaluations, evidence rows scanned, bytes read/written, and replay work with measurement provenance.

#### 14.5 Migration strategy

**M0 — freeze semantics**
- Define canonical envelope and payload schemas.
- Define ID namespaces, idempotency, sequence scope, and error behavior.
- Add compatibility fixtures for existing E09 and E10 snapshots.

**M1 — protocol conformance tests**
- Commit-before-reveal and durable acknowledgement.
- Duplicate retry with identical payload.
- Duplicate retry with conflicting payload.
- Concurrent append / stale sequence rejection.
- One commit per observation.
- No future evidence references in revisions.
- Structure parent/child lineage and split/merge invariants.
- Deterministic replay from a clean process.
- Evaluator-only truth mutation leaves learner payload bytes unchanged.

**M2 — E09 adapter**
- Wrap current E09 ledger without changing the learner's rule grammar.
- Preserve `BATCH_REFIT` as a named baseline.
- Integrate the separate incremental candidate-maintenance arm only as a distinct strategy.
- Add restart/replay and actual cost instrumentation.

**M3 — E10-A adapter**
- Reuse the protocol adapter, not the E09 learner representation.
- Integrate the phase-gated A-O runner and strict A-S source-instance split.
- Move evaluator truth and source provenance behind a separate process/service boundary.
- Add versioned relation/operator structures.

**M4 — cross-track acceptance**
- Run the same conformance suite against both adapters.
- Compare behavior and compute under frozen, batch-refit, replay, and incremental arms.
- Do not merge until both adapters pass the protocol suite and their own track-specific split/evaluator controls.

#### 14.6 Research implications: incremental is a hypothesis, not a default objective

The literature reinforces a caution relevant to E09. The 2025 survey/update on supervised learning from data streams distinguishes instance-incremental from batch-incremental updates and argues that online updates should be justified against traditional alternatives, including replay and retraining. The 2025 ICML work on retraining decisions frames update choice as a trade-off under limited evidence, unknown drift, and retraining cost. A 2026 empirical preprint comparing refresh policies likewise emphasizes update mode, budget, and deployment latency rather than assuming a reactive policy is automatically superior.

Implication for Zhouyi-AI: the acceptance target is not "incremental beats batch in every setting". It is a pre-registered operating-region map showing when incremental maintenance, periodic replay, or batch refit gives the best structure quality under the same total measured budget.

References:
- Supervised Learning from Data Streams: An Overview and Update (2025): https://doi.org/10.1145/3737279
- When to retrain a machine learning model (ICML 2025): https://proceedings.mlr.press/v267/regol25a.html
- When to Retrain: An Empirical Study of Retraining Policies for Streaming ML Under Concept Drift, Budget, and Latency Constraints (2026 preprint): https://arxiv.org/abs/2608.19488
- Online Event Processing (Communications of the ACM, 2019): https://www.cl.cam.ac.uk/~arb33/papers/KleppmannBeresfordSvingen-OnlineEventProcessing-CACM2019.pdf

#### 14.7 Decision and next gate

Decision: PR #53 is a useful protocol design contract, but it is not yet an implementation specification detailed enough to serve as a conformance target without the additions above.

The next engineering step should be a small, independent protocol-conformance package and adapter tests, not another learner and not a third ledger implementation. Keep PR #53 draft until the envelope, idempotency, durable commit, replay, and structure-lineage semantics are made precise. Keep all learner-specific candidate representations separate.

Status after this audit:
- Static source audit: completed.
- Compatibility matrix: documented here.
- Adapter implementation: not started.
- Protocol conformance tests: not started.
- Tests/CI: not run in this audit.
- Main branch: unchanged.
- PR #53: unchanged and unmerged.
