# E12 — Grounded Primitive Induction (2026-11-11)

Status: research design and falsifiable implementation protocol. No learner or benchmark result is claimed in this document.

## 0. Research question

Can a system construct useful, reusable, testable representational primitives from raw observations, rather than receiving a fixed inventory of semantic atoms such as object, attribute, relation, event, role, and state?

The target is **grounded primitive induction**. It is not creation of meaning from nothing. A learner can only propose distinctions that are supported by its observation channels, actions, labels, or measurable consequences. If two latent worlds produce identical observations under every available measurement and intervention, their difference is not identifiable and the learner must preserve ambiguity.

E12 is a research layer below E11 concept induction:
- E12 proposes and validates reusable predicates / measurement operators.
- E11 composes those predicates into concepts and concept hierarchies.
- E10 maps role-sensitive structures between domains.
- E09 revises structures as new evidence arrives.
- E02 represents and evaluates higher-order relations.

## 1. Correct terminology: three different things

Do not conflate these levels:

1. **Observed channel**: a value delivered by the environment, e.g. pixel intensity, sensor reading, token span, timestamp, or a supplied categorical field.
2. **Derived predicate**: a testable function over observations, e.g. `is_rising(x, window)`, `moves_together(a,b)`, or `boundary_between(region_i, region_j)`.
3. **Latent factor / explanatory primitive**: a hypothesized reusable source of variation that helps explain several observed channels or predict responses under interventions.

A new name is not a new primitive. A predicate becomes a candidate primitive only if it has:
- an executable definition or model;
- a declared input domain and output type;
- provenance to the observations from which it was induced;
- a measurable predictive or compression contribution;
- counterexamples and an explicit validity scope;
- a versioned identity and a lifecycle state.

The system may induce a useful abstraction without recovering the "true" hidden ontology. Evaluation must therefore separate predictive utility, structural recovery (when ground truth is identifiable), and calibration/abstention.

## 2. Formal setup

Let an episode expose observations (x) through one or more channels (m), with optional actions (a), context (c), and later outcomes (y):

```text
x ~ P(X | world, context)
o_m = g_m(x) + noise_m
y = h(world, action, context) + noise_y
```

A primitive candidate is a typed operator:

```text
p = (id, input_types, output_type, f_theta,
     scope, provenance, cost, uncertainty, version)
```

It can be:
- a unary predicate over one observation;
- a binary or n-ary relation over observations;
- a temporal operator over an observation sequence;
- a measurement operator that maps raw data to a lower-dimensional value;
- a latent factor model that predicts multiple observed channels.

A primitive set (P) induces a representation:

```text
z_P(x) = [p_1(x), ..., p_k(x)]
```

The induction problem is to select both the operators and their composition:

```text
P* = argmin_P [
    L(P) + L(D_train | P)
       + lambda_g L(D_gate | P)
       + lambda_c Cost(P)
]
```

This is a candidate objective, not a theorem. A concrete coding scheme, normalization, and all coefficients must be fixed on development data. Gate evidence selects candidates; locked Test is used only after selection.

## 3. Four constraints on a credible primitive

### 3.1 Grounding

Every output must trace to a measurable input or an explicit action/outcome. The learner cannot claim a hidden property that no channel can distinguish.

### 3.2 Invariance

A useful primitive should remain stable under transformations declared irrelevant to the task. The benchmark must specify nuisance transformations independently of the learner. Do not reward invariance to a variable that actually changes the target.

### 3.3 Predictive or compressive utility

A candidate must improve held-out prediction, explanation length, or downstream task performance over simpler alternatives. In-sample fit alone is insufficient.

### 3.4 Discriminability

If two candidate primitives make identical predictions on all available evidence, they are observationally equivalent for that episode. The learner should return AMBIGUOUS, not select one based on arbitrary naming or tie-breaking.

## 4. Candidate generation: parallel but typed and budgeted

E12 should generate candidates from several independent proposal families:

| Proposal family | Candidate operation | Example |
|---|---|---|
| Statistical | threshold, rank, quantile, correlation, change point | value exceeds context-specific baseline |
| Geometric / topological | distance, boundary, connectedness, symmetry | two regions share a boundary |
| Temporal | order, duration, recurrence, lag, trend | A consistently precedes B |
| Relational | role, interaction, dependency, higher-order motif | one participant enables another |
| Contrastive | minimal distinguishing feature | predicate separating positive and hard negative cases |
| Predictive | residual / latent-factor proposal | shared factor explains multiple channels |
| Yijing-inspired | complement, partition, state transition, structured transform | test a two-state complement code against a learned code |

Each candidate includes a generator ID, source observation IDs, compute cost, and grammar version. Candidate generation must not inspect hidden truth labels or locked Test.

Avoid exhaustive arbitrary expression enumeration. Use a staged search:
1. cheap proposal generation;
2. type checking and canonicalization;
3. duplicate / semantic-equivalence screening on permitted evidence;
4. independent Gate evaluation;
5. retain a small Pareto set across quality, complexity, novelty, and cost.

Do not collapse candidates solely because they have similar names or member sets. Conversely, syntactically different operators that are observationally equivalent on the declared domain should be grouped as an equivalence class until a discriminating test exists.

## 5. Primitive lifecycle

Use explicit operations and immutable lineage:

- PROPOSE: candidate emitted with provenance.
- TEST: candidate evaluated on a permitted Gate.
- ACCEPT: independent evidence supports a declared use scope.
- REFINE: change parameters while preserving identity only if semantics remain compatible.
- SPLIT: one operator has stable, reproducible sub-regimes that need separate scopes.
- COMPOSE: build a higher-order operator from accepted primitives.
- SUSPEND: current evidence is insufficient or a contradiction is unresolved.
- RETIRE: evidence shows the operator is invalid or dominated in its declared scope.
- REACTIVATE: requires fresh independent evidence.

Every lifecycle event records parent versions, support IDs, contradiction IDs, Gate protocol, code version, and reason. No destructive overwrite. A renamed operator is not a new discovery.

## 6. Identifiability protocol

Each episode returns one of four statuses:

- IDENTIFIABLE: the benchmark's equivalence class contains one acceptable primitive structure at the declared resolution.
- AMBIGUOUS: at least two materially different structures remain equivalent under observed evidence.
- INCONSISTENT: no candidate in the declared grammar meets the pre-registered fit criterion.
- BUDGET_EXHAUSTED: the search stopped before a defensible decision.

Construct paired worlds:
- same Support observations, different hidden mechanisms;
- a specified intervention or new context distinguishes them;
- a no-intervention arm confirms that the mechanism cannot be identified from passive observations alone.

If the task provides no intervention, the learner must not claim causal direction merely from correlation. It may report predictive association or an unresolved relation.

## 7. Benchmark suite

### E12-A: unknown predicate recovery

Generate worlds from a finite, declared primitive grammar containing thresholds, parity, conjunction, temporal order, and simple geometric predicates. Hide which primitives are active. Include nuisance channels, missing values, measurement noise, and redundant channels.

Compare:
- supplied primitive vocabulary (upper-bound control);
- fixed handcrafted features;
- frequent itemset / correlation baseline;
- E12 statistical proposal only;
- E12 multi-family proposal;
- random proposal with equal compute;
- exact search on tiny instances.

Report predicate recovery only when the hidden primitive is identifiable; otherwise score equivalence-class recovery and abstention.

### E12-B: primitive reuse and compositional transfer

Train on primitive instances and a set of compositions; test on held-out combinations of known primitives, then on held-out nuisance transformations. Keep primitive OOD separate from composition OOD.

Measure:
- predicate precision/recall;
- operator equivalence-class recovery;
- downstream exact match / F1;
- sample efficiency;
- false discovery rate;
- abstention precision and coverage;
- description length and compute.

### E12-C: intervention discrimination

Create paired environments where observational correlations match but intervention responses differ. Allow actions only in the intervention arm. Evaluate whether the learner:
- remains ambiguous before intervention;
- chooses a discriminating intervention under a fixed budget;
- updates its primitive hypothesis after observing the result;
- does not overstate causality when intervention is unavailable.

### E12-D: primitive drift and revision

Change the measurement process or world mechanism over time. Include:
- temporary sensor corruption;
- persistent calibration shift;
- true mechanism change;
- previously unseen nuisance;
- return to an earlier regime.

Compare frozen primitives, batch refit, unconstrained online updates, and evidence-gated lifecycle updates.

## 8. Yijing-inspired hypotheses, not fixed truths

Translate the relevant ideas into candidate computational biases, then compare them against capacity-matched generic alternatives.

| Idea | E12 hypothesis | Required null / control |
|---|---|---|
| Yin–Yang | complementary predicate pairs may compress certain binary distinctions | independent binary features; learned two-state code |
| Four Images | two-stage coarse partition may help hierarchical state induction | generic 4-cluster / 2-bit code |
| Eight Trigrams | factorized 3-bit state may help compositional feature discovery | learned 8-state code and random permutation |
| Six-line / 64-state | structured product code may improve higher-order state reuse | equal-size unconstrained 64-codebook |
| Gua change | sparse bit-change operators may help transition discovery | generic sparse transition model |
| Mutual / reversed / opposite views | structured transformations may expose invariant features | random and learned transformations |
| Five-phase relations | signed directed relation prior may help relational predicate proposals | unconstrained learned matrix and random signed matrix |

For each, run no-prior, fixed-prior, learnable-prior, and parameter/compute-matched generic-prior arms. Include deliberately incorrect correspondences. A good learner should reject a harmful prior rather than rationalize it.

Traditional symbolic correspondence is not evidence of a latent mechanism. Any claimed gain must replicate outside data generated to favor that same correspondence.

## 9. Interface to E11 / E10 / E09 / E02

### E11 concept induction
E12 emits accepted predicates and typed relations with validity scopes. E11 composes them into recurring structures, concepts, and hierarchies. E11 must retain primitive provenance and cannot treat every accepted predicate as universally true.

### E10 analogy
E10 maps primitive and relation structures across domains using role alignment. Transfer must preserve declared invariants and record failed alignments. Surface similarity is a proposal signal, not an acceptance rule.

### E09 evidence update
Every prediction is made before feedback is revealed. The resulting evidence record is appended immutably. Primitive revisions produce explicit version diffs; batch refit remains a baseline.

### E02 dynamic hypergraph
Accepted predicates become typed nodes or operators; higher-order relations are sparse hyperedges. Candidate hyperedges cite primitive and observation IDs. E02's lifecycle must not silently promote an unverified E12 proposal.

## 10. Evaluation integrity

The evaluator's hidden primitive identities, generator seeds, and intervention outcomes must live outside the learner process. Do not pass a complete episode object containing Query or Test objects into the learner as a convenience.

Required tests:
- mutate hidden truth while keeping learner payload byte-identical; learner outputs must be identical;
- mutate locked Test; candidate proposals and Gate decisions must remain unchanged;
- reorder candidate input; canonical results must remain deterministic;
- duplicate evidence from one source; support must not be double-counted as independent evidence;
- remove a measurement channel; the learner must become less certain or report ambiguity where appropriate;
- inject a false prior; the learner must be able to reject it;
- exhaust compute budget; status must be BUDGET_EXHAUSTED, not a fabricated best answer.

Use world-seed or episode-level confidence intervals. Report every failure, abstention, and unresolved case.

## 11. Acceptance criteria and falsification

E12 is useful only if it improves at least one pre-registered capability without unacceptable cost or false discovery.

Minimum acceptance:
1. beats fixed-feature and random-proposal baselines on identifiable primitive recovery at equal compute;
2. does not force a unique answer on observationally equivalent worlds;
3. transfers accepted primitives to held-out compositions better than non-compositional baselines;
4. detects when a prior is harmful;
5. produces auditable provenance and version lineage;
6. maintains calibrated uncertainty / abstention under missingness and drift.

Falsification:
- no stable gain over fixed features at equal compute;
- gains disappear under held-out world families;
- false discovery rises sharply with vocabulary size;
- model selects a mechanism in indistinguishable worlds;
- apparent gains depend on evaluator leakage;
- Yijing-inspired priors do not outperform matched generic priors.

A negative result is informative: the project should then narrow E12 to the proposal families that demonstrably help.

## 12. Implementation sequence

P0 — data and evaluator boundary:
1. define a versioned Observation schema with source ID, channel, timestamp, type, value, missingness, and provenance;
2. separate learner payload from evaluator truth at process/API boundary;
3. create deterministic synthetic world generators and locked seed manifests.

P1 — transparent baseline:
1. implement a small typed predicate DSL;
2. add canonicalization and semantic duplicate checks;
3. add exact enumeration for tiny worlds;
4. add frequency, fixed-feature, and random proposal baselines.

P2 — grounded proposal engine:
1. add statistical, temporal, relational, and contrastive proposal arms;
2. score on Train only;
3. select with independent Gate;
4. preserve Pareto candidates and explicit ambiguity.

P3 — lifecycle and transfer:
1. add immutable evidence ledger integration;
2. add PROPOSE/TEST/ACCEPT/REFINE/SPLIT/SUSPEND/RETIRE events;
3. connect accepted primitives to E11 and E10 through versioned contracts;
4. compare batch refit with prequential updates.

P4 — Yijing ablation:
1. add complementary, hierarchical, factorized, and sparse-transition priors as optional arms;
2. run matched generic controls;
3. test incorrect-prior rejection;
4. retain only priors with replicated independent gains.

## 13. Immediate next experiment

Start with **E12-A0: Identifiability and Leakage Baseline**, before implementing a sophisticated learner.

The generator should produce paired episodes with:
- one family where a primitive is identifiable from Support;
- one family where two candidate primitives are observationally equivalent;
- one family where a discriminating intervention exists but has not yet been observed;
- one family with no available measurement that can distinguish the latent alternatives.

The learner receives only the permitted observations and declared action affordances. The evaluator privately knows the generating primitive class.

Acceptance is not high raw accuracy alone. It must correctly separate IDENTIFIABLE from AMBIGUOUS, avoid truth leakage, and report BUDGET_EXHAUSTED when applicable. This establishes whether E12 can reason about the limits of its own evidence before it is allowed to invent new primitives.
