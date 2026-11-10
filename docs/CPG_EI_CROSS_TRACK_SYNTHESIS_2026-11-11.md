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
