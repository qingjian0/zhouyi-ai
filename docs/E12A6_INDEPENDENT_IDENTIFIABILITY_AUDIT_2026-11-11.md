# E12-A6 Independent Design Audit: Identifiability, Lifecycle Validity, and Evaluator Isolation

Date: 2026-11-11  
Branch: research/e12a6-identifiability-audit-2026-11-11  
Status: independent protocol audit and engineering acceptance criteria; no implementation or benchmark result is claimed.

## 1. Audit conclusion

E12-A6 is the correct integration target: it tests whether discovery, discrimination, composition, reuse, and revision form one evidence-governed lifecycle. Before implementation, three distinctions must be explicit or the benchmark can reward false knowledge:

1. Expression equivalence is not mechanism equivalence. Two expressions may agree on a finite dataset while differing outside it.
2. Predictive success is not primitive validity. A candidate may predict a task through a shortcut, confound, or narrow scope.
3. Lifecycle state is not truth. GATE_VALIDATED and REUSED are evidence states under declared distributions, not permanent semantic facts.

The benchmark should measure calibrated, scoped knowledge acquisition—not the number of candidates promoted.

## 2. Four equivalence relations

Do not use one generic equivalence flag.

### E0 — Syntactic canonical equivalence
Two ASTs reduce to the same canonical expression under declared rewrite rules (for example, commutativity of AND). This is grammar-relative and can be decided by the canonicalizer.

### E1 — Observed-sample behavioral equivalence
Two candidates produce the same outputs on a specific evidence set. Store the evidence-set digest and the compared candidate versions. This relation can disappear when new evidence arrives.

### E2 — Measurement-regime observational equivalence
Two hypotheses make the same predictions for every measurement in the currently permitted measurement set. If so, the system must preserve an ambiguity class and abstain from claiming identification. A new measurement regime may split the class.

### E3 — Interventional/causal equivalence
Requires an explicit intervention model and assumptions. E12-A6 passive-observation stages must not infer this relation. Keep causal claims out of the current acceptance state machine.

Every equivalence record must specify its level, scope, evidence digest, measurement regime, and validity status.

## 3. Candidate validity must be scoped

A candidate should not be promoted as a context-free law. Require:
- input types and units;
- expression AST and grammar version;
- scope: environment, entity class, time range, and declared conditions;
- support evidence IDs;
- counterexample evidence IDs;
- known competitors;
- measurement regime ID;
- predictive calibration;
- complexity and measured evaluation cost;
- candidate version and parent versions.

A narrow-scope candidate can be useful. Prefer a scoped primitive over an over-generalized primitive when evidence supports only the former.

## 4. Lifecycle state machine amendments

Keep the proposed lifecycle states, but make these transitions explicit:

- PROPOSED -> DISCRIMINATION_PENDING only when at least two live hypotheses disagree on a permitted measurement.
- DISCRIMINATION_PENDING -> AMBIGUOUS when no permitted measurement separates live hypotheses within budget.
- TRAIN_SUPPORTED -> GATE_VALIDATED only after a frozen candidate definition passes an independent Gate and beats a declared simple baseline on incremental utility.
- GATE_VALIDATED -> REUSED only after a held-out composition task invokes the candidate and records a measurable contribution.
- Any semantic edit creates a new candidate version and moves it to REVALIDATION_PENDING.
- CHALLENGED -> SPECIALIZED only if a predeclared partition yields stable sub-scopes; otherwise REVISED or RETIRED.
- RETIRED candidates remain in the immutable ledger and may be re-proposed only as a new version with explicit lineage.

Do not permit direct transitions from PROPOSED to GATE_VALIDATED or from CHALLENGED to REUSED.

## 5. The evaluator firewall

The strongest benchmark guarantee is not a prompt instruction; it is an API and process boundary.

Learner-visible:
- current episode observations;
- declared measurement descriptions and costs;
- learner's own candidate history;
- outcomes of measurements it explicitly purchased;
- public schema and remaining budget.

Evaluator-only:
- generator identity and parameters;
- hidden mechanism labels;
- Gate-Final labels;
- Locked-Test labels;
- episode seed and hidden split metadata;
- oracle candidate IDs and oracle action choices.

The learner process must not import evaluator modules, access hidden files, inspect environment variables containing labels, or infer split role from filenames/order. The evaluator should invoke the learner through a serialized request/response boundary and retain secret material outside the learner working directory.

Mutation tests must establish noninterference:
- change Locked-Test labels: learner proposals, actions, and Gate decisions remain byte-identical;
- change hidden generator labels while keeping learner-visible observations identical: learner trace remains byte-identical;
- permute row order, candidate order, and feature declaration order: canonical result remains invariant where task definition is permutation-invariant;
- add irrelevant metadata: decisions remain unchanged;
- replace a measurement outcome: only downstream decisions depending on that evidence may change.

## 6. Active measurement decision contract

For candidate hypotheses H and permitted measurement q, define:

EIG(q) = H(H | D) - E_y[H(H | D, q=y)]

Use cost-normalized utility only when measurement costs are meaningful and nonzero:

U(q) = EIG(q) / cost(q)

The selector must return one of:
- SELECT(q, expected_gain, cost) when a legal measurement has positive expected gain and fits budget;
- NO_DISCRIMINATING_MEASUREMENT when all legal measurements have zero gain;
- BUDGET_EXHAUSTED when useful measurements exist but exceed remaining budget;
- INVALID_INPUT for malformed hypothesis/probe definitions.

Do not conflate no-information with budget exhaustion. Do not silently use hidden labels to estimate outcome distributions. On tiny finite hypothesis spaces, compare the implementation against exact enumeration.

## 7. Composition must preserve provenance and avoid shortcut credit

When a composed expression is formed:
- retain all parent candidate IDs and exact versions;
- retain the expression AST before and after simplification;
- record which parent predicates contributed to each prediction;
- evaluate the composition on held-out entity/world groups;
- compare against each parent alone and a simple non-compositional baseline.

A+C+E discovery is not enough if B and D encode a correlated shortcut. Include independently randomized distractors and group splits to test shortcut resistance.

A composition receives incremental-utility credit only if it improves held-out performance or reduces measurement cost over its best parent/simple baseline under matched compute.

## 8. Counterexample handling: distinguish drift from falsification

A failed prediction can arise from stochastic noise, measurement error, covariate shift, scope violation, a true counterexample, or an upstream schema bug.

The update policy must first classify the failure source, or explicitly mark it unresolved. Do not immediately revise a primitive after one noisy event, and do not ignore repeated systematic failures.

Use a sequential challenge policy with:
- predeclared error model;
- minimum evidence and false-alarm threshold;
- group-aware accumulation;
- change-point detection for drift;
- explicit challenge budget;
- immutable decision trace.

Report detection delay and false-revision rate separately.

## 9. Minimum adversarial benchmark matrix

| Stress case | Correct behavior | Failure signal |
|---|---|---|
| Null world | abstain / no promotion | false primitive acceptance |
| Observational equivalence | preserve ambiguity class | unjustified unique identification |
| Distractor correlation | reject shortcut or narrow scope | composition collapses under group shift |
| Delayed counterexample | challenge, scope, revise or retire | stale candidate remains trusted |
| Noisy isolated outlier | retain uncertainty or request evidence | immediate destructive revision |
| True scope change | detect drift and specialize/revalidate | overgeneralized transfer |
| DSL misspecification | report coverage failure / abstain | false confidence from nearest wrong expression |
| Candidate-order mutation | same result under deterministic policy | order-dependent selection |
| Test-label mutation | identical learner trace | evaluator leakage |
| Measurement-cost mutation | revise legal action under declared utility | cost ignored |

## 10. Acceptance gates before E12-A6 is called complete

A — Contract: typed schemas, versioning, scoped candidates, explicit equivalence levels, immutable events.

B — Isolation: serialized learner/evaluator boundary and mutation tests proving locked-label noninterference.

C — Exactness: tiny-domain EIG and bounded grammar checks against exact oracle implementations.

D — Lifecycle: all legal transitions tested; illegal transitions rejected; semantic edits create new versions.

E — Benchmark: sparse composition, nested composition, null, equivalence, DSL misspecification, noise, and delayed-counterexample worlds.

F — Evidence: matched proposal/evaluation/measurement/compute budgets; independent world-level uncertainty; all abstentions and failures included.

A passing unit-test suite validates implementation behavior, not architectural superiority. Superiority requires preregistered held-out comparisons against the best simple baseline.

## 11. Recommended implementation sequence

1. Add equivalence-level types and scoped candidate envelope.
2. Add append-only lifecycle event schema and transition validator.
3. Implement evaluator firewall before integrating proposers.
4. Implement exact finite-domain measurement selector and oracle tests.
5. Build one sparse-composition episode end to end.
6. Add null and observational-equivalence episodes before any broad benchmark.
7. Add delayed counterexample and scope specialization.
8. Integrate A1/A2/A3/A4/A5/M2 behind adapters only after contract tests pass.
9. Run the full adversarial matrix with frozen configuration.
10. Compare symbolic-prior variants only after the no-prior lifecycle baseline is reliable.

## 12. Decision

Proceed with E12-A6, but make equivalence-level separation, scope-aware primitive validity, and evaluator noninterference hard prerequisites. Without them, the benchmark can mistake finite-sample agreement, leakage, or shortcut exploitation for autonomous concept discovery.

This document is an audit and implementation gate proposal. It contains no new experimental result and does not certify any existing branch as passing these gates.
