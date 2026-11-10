# Shared Evidence Ledger and Prequential Learning Contract (2026-11-11)

Status: design / implementation contract. This document does not claim an implementation, test pass, benchmark result, or integrated learner. It extends the cross-track synthesis on an isolated research branch.

## 0. Decision

E02, E09, E10, and E11 should share a **minimal evidence protocol**, not a shared monolithic learner.

The common substrate is an append-only, provenance-bearing event ledger. Each track remains free to propose its own candidate structures, but every proposal must be evaluated against the same temporal rule:

`predict -> commit_prediction -> reveal -> append_evidence -> revise`

The learner must make and persist its prediction before the target label or evaluator outcome is revealed. A later revision may change the current model, but must not rewrite the historical prediction or evidence record.

## 1. Why this is the highest-leverage integration point

Current audits identify four incompatible or incomplete semantics:

- E02 has evidence accumulation and adjudication states, but its adaptive score is not a calibrated classical sequential test.
- E09-B is batch induction with counterexample constraints and full-data refitting, not demonstrated online revision.
- E10-A has generator/split provenance concerns and learner/evaluator payload-boundary concerns.
- E11-A0 has a bounded concept proposal baseline, but hidden truth is still co-resident with learner-side episode structures.

A common ledger makes temporal ordering, provenance, update lineage, and compute cost inspectable without prematurely forcing the tracks into one hypothesis language.

## 2. Minimal typed record model

The following is a logical schema, not a mandated serialization library. Use canonical JSON or another deterministic encoding only after the field semantics are frozen.

### 2.1 Observation

- `observation_id`: globally unique opaque ID; never encodes label, class, split, or source semantics.
- `episode_id`: opaque episode/world identifier.
- `timestamp_or_step`: monotonic episode-local observation order.
- `payload_ref`: learner-visible observation payload or immutable content hash.
- `source_ref`: evaluator-only provenance pointer; never included in learner serialization.
- `environment_ref`: visible only when the task contract explicitly permits it.
- `feature_schema_version`: schema identifier, not a hidden target cue.

An observation may be a raw event, an object-attribute view, or a relation instance. It must not silently mix evaluator annotations into the learner payload.

### 2.2 PredictionCommit

Persisted before reveal:

- `prediction_id`
- `observation_id`
- `model_version`
- `candidate_set_hash`
- `selected_hypothesis_id` or explicit abstention
- `prediction` and calibrated confidence, if available
- `decision_status`: `PREDICT`, `ABSTAIN_AMBIGUOUS`, `ABSTAIN_INCONSISTENT`, `ABSTAIN_BUDGET`
- `compute_budget` and actual measured cost
- `created_at_step`

The prediction commit must be immutable. A post-reveal correction is a new record linked to the original prediction, never an overwrite.

### 2.3 EvidenceReveal

Created only after PredictionCommit is committed:

- `reveal_id`
- `prediction_id`
- `target_or_feedback`
- `reveal_source`
- `reveal_step`
- `reliability_metadata`
- `evaluator_signature` (optional, held outside learner process)

The reveal API must not permit a reveal without a matching prior prediction when the task is marked prequential.

### 2.4 StructureVersion

Every rule, relation, concept, analogy, or operator is a versioned structure:

- `structure_id`: stable lineage ID
- `version_id`: immutable version ID
- `kind`: predicate / relation / concept / analogy / operator / policy
- `definition_ast`: typed, executable or inspectable definition
- `scope` and `preconditions`
- `support_evidence_ids`
- `counterexample_evidence_ids`
- `parent_version_ids`
- `creation_method` and `learner_track`
- `complexity_cost`
- `status`: proposed / active / weakened / split / merged / suspended / retired
- `valid_from_step` and `valid_until_step`

A split creates child lineages with explicit parent references. A merge creates a new lineage referencing all parents. Historical versions remain queryable.

### 2.5 RevisionEvent

- `revision_id`
- `trigger_evidence_ids`
- `before_version_ids`
- `after_version_ids`
- `operation`: create / keep / modify / split / merge / suspend / retire / abstain
- `rationale_code`
- `search_budget`, `actual_compute`, `memory_delta`
- `revision_step`

No revision may cite evidence that was not revealed by its revision step.

## 3. State machine and information-flow contract

A task episode follows:

1. **Observe**: learner receives only the permitted observation payload.
2. **Propose**: learner generates sparse candidate structures under a declared budget.
3. **Check**: identifiability layer returns identifiable / ambiguous / inconsistent / budget-exhausted.
4. **Predict**: learner emits prediction or abstention.
5. **Commit**: runner durably records prediction, candidate hash, model version, and cost.
6. **Reveal**: evaluator reveals target/feedback only after commit.
7. **Append**: learner receives the reveal as a new immutable evidence item.
8. **Revise**: learner emits a new StructureVersion and RevisionEvent, or explicitly keeps/abstains.
9. **Audit**: evaluator scores the committed pre-reveal prediction and validates lineage.

### Process boundary

The evaluator must own hidden labels, latent structures, source-group provenance, and locked-test truth. The learner process receives serialized learner payloads only.

Do not return a single in-memory object containing both learner inputs and evaluator truth. Do not rely on private field names or Python conventions as a security boundary.

Required canaries:
- Mutating evaluator labels does not change learner payload bytes or hashes.
- Mutating evaluator-only source IDs does not change learner payload bytes or candidate generation.
- A recursive scan of learner payloads finds no evaluator-only keys or values.
- Locked-test labels are unavailable to the learner process and candidate-selection process.

## 4. Prequential metrics

Report at least:

- pre-reveal accuracy / macro-F1 / task-specific score;
- log loss or Brier score when probabilities are meaningful;
- calibration and coverage-risk curves;
- abstention rate by reason;
- first prediction score versus post-update score;
- per-update marginal compute and memory;
- cumulative compute versus batch-refit control;
- structural stability: unnecessary revisions, oscillation, and stale-structure retention;
- revision precision: fraction of revisions supported by later independent evidence;
- recovery after distribution shift;
- performance by episode/world seed, not treating correlated rows as independent.

The main incremental-learning comparison is not merely final accuracy. Compare the same learner budget under:
- immutable batch-refit baseline;
- append-only incremental revision;
- periodic replay/refit;
- no-revision frozen model.

A system only earns an online-learning claim if predictions are made before reveal, revisions are causally downstream of new evidence, and update cost is measured without silently replaying all history.

## 5. Cross-track adapters

The ledger is shared; candidate semantics are not.

| Track | Candidate object | Revision examples | Additional evaluation |
|---|---|---|---|
| E02 | event identity / relation / adjudication state | keep, modify, reactivate, suspend, abstain | evidence sufficiency, competing hypotheses, drift |
| E09 | predicate / rule AST | specialize, weaken, split, retire | prequential counterexample repair |
| E10 | role-sensitive relation / analogy / transition operator | remap roles, revise preconditions, compose or split operator | A-P/A-S/A-O/A-C and relation-family OOD |
| E11 | concept boundary / hierarchy edge | expand, contract, split, merge concept | unknown concept count, object/world-disjoint transfer |

A shared evidence ID may support multiple tracks, but each track must record its own hypothesis, score, and revision. Cross-track reuse must be explicit and ablatable; it must not create hidden information channels.

## 6. Candidate search and global coordination

Represent candidate paths as typed proposals over observation/evidence IDs. Do not enumerate every subset.

Each proposal declares:
- generator family;
- input evidence IDs;
- hypothesis AST and version;
- total compute allowance;
- measured compute;
- allowed data split;
- predictive and structural scores;
- counterexamples;
- redundancy/novelty relation to existing candidates.

The coordinator:
1. rejects candidates using forbidden evidence or split access;
2. deduplicates semantically equivalent candidates;
3. preserves materially different candidates when evidence is ambiguous;
4. allocates a fixed global compute budget;
5. compares serial, independent-parallel, and adaptive-shared-budget search;
6. abstains when no candidate is defensible within budget.

The primary parallelism metric is best defensible held-out structure at equal total compute, not candidate count or wall-clock time alone.

## 7. Identifiability and abstention

The learner must be allowed to say:

- `IDENTIFIABLE`: unique within the declared grammar and available evidence resolution;
- `AMBIGUOUS`: multiple materially different structures remain observationally equivalent;
- `INCONSISTENT`: no candidate in the declared grammar explains the evidence;
- `BUDGET_EXHAUSTED`: search ended before a defensible decision.

Paired-world tests should share identical Support observations but diverge under a held-out context or intervention. If the learner cannot distinguish them before that evidence arrives, it must not be credited for guessing the hidden world.

## 8. Minimum benchmark protocol

For each experiment:
- preregister generator families, split semantics, seeds, metrics, thresholds, and compute budget;
- separate development, Gate, and locked Test worlds;
- keep source provenance and evaluator truth out of learner payloads;
- include random, frequency-only, fixed-structure, batch-refit, and equal-budget search baselines as relevant;
- report failed, ambiguous, unsplittable, and budget-exhausted episodes;
- use seed/world-level confidence intervals;
- rerun exact repository tests and CI on the exact commit under evaluation;
- publish configuration, source commit, artifacts, and hashes.

For E10-A, report A-P, A-S, A-O, and A-C as separate tracks. Never silently fall back from a stricter split to an easier one. For E11, report query-observable and unobservable concepts separately and freeze matching thresholds before locked evaluation.

## 9. Implementation sequence

P0 — protocol tests:
1. canonical schema and immutable append-only ledger;
2. prediction-before-reveal enforcement;
3. evaluator/learner process separation;
4. payload hash and recursive canary tests;
5. lineage validation (no future evidence references).

P1 — one narrow end-to-end vertical slice:
1. choose E09-B as the first adapter because its batch-refit behavior is an explicit control;
2. add prequential prediction commits and evidence reveal;
3. implement incremental revision as a separate arm;
4. measure marginal update cost against batch refit;
5. preserve the old batch learner unchanged as baseline.

P2 — adapter expansion:
1. E10-A source-instance A-S split and task payload isolation;
2. E02 evidence controller adapter with empirically calibrated thresholds;
3. E11 concept proposals with observable-concept scoring and independent evaluator.

P3 — coordinator:
1. equal-budget serial/parallel comparisons;
2. candidate deduplication and diversity preservation;
3. optional Yijing-inspired candidate priors as isolated ablation arms.

## 10. Falsification criteria

The shared protocol or proposed learner direction should be reconsidered if:
- prediction commits can be generated after target reveal;
- evidence lineage cannot reconstruct exactly what was known at each step;
- incremental updates replay the full dataset without being counted as such;
- candidate search exceeds budget or hides unmeasured work;
- the learner's score collapses under source/object/world-disjoint splits;
- Yijing-inspired priors fail against parameter/compute-matched generic priors or become impossible to reject;
- parallel paths do not improve held-out quality at equal total compute;
- structure recovery is poor despite high prediction scores, or vice versa.

## 11. Claims this contract does not make

This design does not establish:
- a new neural architecture;
- a replacement for Transformers;
- general intelligence or open-world autonomy;
- causal discovery from observational data alone;
- successful online learning;
- a benefit from Yijing-inspired priors;
- any benchmark or CI pass.

Those remain separate empirical questions.
