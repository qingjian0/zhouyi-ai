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
