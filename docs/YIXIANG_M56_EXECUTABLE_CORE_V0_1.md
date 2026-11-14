# M56 executable core v0.1 — implementation note

Status: executable synthetic protocol slice; pending CI and artifact audit  
Protocol: M56 autonomous yixiang formation and relational transfer v0.1  
Scope: M56-A1 through A3, plus minimal executable contracts for B1, C1, D1

## 1. What is implemented

- A versioned case envelope with explicit task context, observations, relations, evidence spans, and source provenance.
- A validator that rejects evaluator-truth fields in agent-visible cases and rejects untraceable or incorrectly layered synthetic evidence.
- A deterministic synthetic generator with separate random streams for task assignment, feature generation, and nuisance generation.
- A separate evaluator-only truth object containing selected features, hidden class membership, target relation validity, split assignment, and nuisance state.
- Three task-conditioned feature families: support/load, flow/pressure, and containment/boundary.
- Task-shift views that hold observations fixed while changing the declared purpose.
- Explicit within-domain, near-domain, and far-domain transfer-distance labels, plus lexical/feature/relational/mechanism/long-context analogy-granularity labels.
- Independent-nuisance and train-only spurious-cue conditions. In the latter, the nuisance marker is correlated with the hidden class in training, independent in validation, and reversed in test.
- A minimal open-set category decision with member, non_member, and unknown states.
- A directed relation-preservation scorer that requires an explicit role mapping.
- A versioned counterexample revision function that narrows only the affected scope and otherwise retains the current scope or requests more evidence.

## 2. Leakage and validity controls

The public case object never contains evaluator truth. The generator returns truth through a separate object and the runner writes separate files:

- m56.agent.jsonl: agent-visible observations only;
- m56.evaluator.json: evaluator-only labels and split metadata;
- m56_audit.json: aggregate integrity and nuisance diagnostics.

The evaluator truth is not passed to the feature-selection control, category decision, relation scorer, or revision function.

The synthetic source provenance is explicitly labeled synthetic_observation. It must not be mistaken for a primary classical text. The current implementation contains no human annotation and makes no claim about the correctness of any historical interpretation.

## 3. Experiments and expected diagnostics

Run the module with python -m prototype.run_yixiang_m56_study.

The CI workflow executes:
1. independent nuisance generation;
2. a train-only spurious-cue stress condition;
3. unit tests for reproducibility, truth isolation, task shift, open-set rejection, directed relation mapping, counterexample scope, and JSONL separation.

The spurious-cue condition is a negative control. A system that relies on incidental_marker should fail when the correlation reverses at test time. This benchmark runner reports the cue/class agreement by split; it does not yet run a learned model or claim that any model has passed this challenge.

## 4. Interpretation limits

This is an executable contract and generator slice, not a completed M56 model comparison.

Not implemented yet:
- independent human annotation of pre-Qing source passages;
- adjudicated source-family and textual-dependency metadata;
- Transformer, structure-mapping, SCM, or Zhouyi-agent adapters;
- trained category induction or learned relation alignment;
- calibrated confidence and abstention evaluation;
- full counterexample taxonomy (split, weaken, reject, merge) with adjudicated expected actions;
- held-out source-family and relation-template benchmark results.

The task-rule feature selector is a transparent control derived from the declared task contract. It is not evidence that a system autonomously discovers the right features. The current transfer-distance and analogy-granularity fields are balanced stratification labels; the generator does not yet implement distinct symbolic encodings, increased long-context load, or graded mechanism complexity for each label. They must not be interpreted as measured near/far-transfer difficulty. Likewise, the category, transfer, and revision functions are reference contracts for testing invariants, not claimed cognitive capabilities.

## 5. Acceptance gates for the next stage

Before expanding the benchmark:
1. exact-head CI must pass;
2. raw agent and evaluator files must remain disjoint and parseable;
3. nuisance correlation must be measured per split;
4. task shifts must change the relevant feature set while preserving observations;
5. within/near/far transfer distances and analogy granularities must remain explicit in the public schema;
6. relation reversal and role permutation must be rejected correctly;
7. category abstention and local revision must preserve uncertainty and unaffected scope.

Only after these controls pass should the project add annotation pilots and real model adapters. Any model comparison must use identical permitted inputs, compute budgets, versioned prompts/configurations, and source-family-held-out test data.
