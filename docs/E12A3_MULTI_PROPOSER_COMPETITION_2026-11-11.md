# E12-A3 — Multi-Proposer Primitive Discovery and Budget Competition

Date: 2026-11-11  
Status: research protocol and architecture proposal; no performance result is claimed  
Base: E12-A2-M finite-hypothesis active measurement baseline  
Branch: research/e12a3-proposer-competition-2026-11-11

## 1. Research question

Can multiple heterogeneous proposal mechanisms discover useful, executable predicates more efficiently and robustly than a single proposer, random proposals, or exhaustive enumeration when all methods receive the same evidence and total compute budget?

The target is not merely to produce many expressions. The system must propose candidates grounded in observed data, with explicit types, domains, provenance, and execution semantics; validate them independently; establish incremental predictive or compressive value; and support rejection, revision, splitting, suspension, and retirement.

E12-A3 is a candidate-discovery and resource-allocation experiment. It is not a claim of open-ended concept creation or general intelligence.

## 2. Architecture

A3 separates proposal generation from evaluation and acceptance.

1. Observation normalizer: typed, immutable evidence records with source IDs, time, missingness, and measurement conditions.
2. Proposal portfolio: independent proposer families emit candidate expressions and declared costs.
3. Canonicalizer: validates types, normalizes syntax, and detects observational equivalence on a declared evidence set.
4. Evidence evaluator: evaluates candidates on Support and Gate; Locked Test remains unavailable until all choices are frozen.
5. Portfolio allocator: allocates a fixed global budget across proposer families.
6. Primitive registry: stores accepted candidates, scope, provenance, counterexamples, and lifecycle state.

No proposer receives evaluator truth, world seeds, hidden rule IDs, or Locked Test examples.

## 3. Proposal families

Start with small transparent generators, each with a stable family ID and version:

- STAT: thresholds, intervals, ranks, parity, distribution changes, residual patterns.
- TEMPORAL: monotonicity, ordering, persistence, periodicity, window deltas.
- RELATIONAL: equality, difference bounds, co-change, role constraints.
- CONTRASTIVE: predicates separating positive examples from hard negatives.
- COMPOSITIONAL: typed AND/OR/NOT compositions of already proposed primitives.
- RANDOM: grammar-valid random proposals as an exploration baseline.
- EXHAUSTIVE: bounded DSL enumeration as a search baseline, not a presumed winner.

Do not give one family a richer schema or more evidence than another. Every proposal records proposer family/version, canonical expression and grammar version, input/output types and domain, source observation IDs, proposal and execution costs, parent candidate IDs, and parameter uncertainty.

## 4. Candidate canonicalization and equivalence

Syntactic identity is not semantic identity. For a declared evidence set D, define the observed behavior signature as the vector of candidate outputs on D.

Candidates with identical signatures on D belong to the same observed equivalence class for D. This does not prove global equivalence.

Maintain two separate relations:
- syntactic canonical equality;
- empirical equivalence under a named dataset/version.

Do not collapse candidates solely because they agree on Support. Preserve provenance and allow Gate or later measurements to split an empirical equivalence class.

Candidate complexity should be explicit and versioned. A minimal description length score may be used as a tie-break or Pareto dimension, not as a substitute for held-out evidence.

## 5. Budget allocation

Let B be the total proposal/evaluation budget. Each family i receives an allocation b_i, with sum of allocations no greater than B.

Compare these policies:

A. Equal fixed allocation  
B. Round-robin allocation  
C. UCB-style adaptive allocation from prior Gate utility  
D. Successive halving / racing  
E. Pareto portfolio allocation using quality, novelty, complexity, and cost  
F. Single best proposer  
G. Random proposal allocation  
H. Exhaustive DSL allocation

To avoid early lock-in, adaptive policies reserve a preregistered exploration floor for every active family. Allocation updates may use Support and Gate only; Locked Test is never used for allocation.

A proposal family's reward must be computed from a declared score, for example incremental Gate log-loss improvement or compression gain minus a complexity penalty. Do not reward raw candidate count.

All methods receive the same total proposal budget, execution budget, Gate access count, and wall-clock/operation budget where measurable.

## 6. Evaluation without selection leakage

Use three distinct data roles:

- Support: candidate generation and fitting.
- Gate: portfolio selection, hyperparameter choice, and candidate filtering.
- Locked Test: one-time final evaluation after all candidates, policies, and thresholds are frozen.

For repeated adaptive Gate queries, record every query and apply a fixed query budget. If Gate is repeatedly reused, report that adaptive reuse explicitly; do not describe it as an untouched validation set.

Prefer nested world-level evaluation: inner worlds for proposer and allocator selection; outer held-out world families for final generalization.

No candidate can be declared generally accepted from a single Gate episode.

## 7. Acceptance and lifecycle

Use explicit states:

PROPOSED -> TYPE_CHECKED -> SUPPORT_SCREENED -> GATE_VALIDATED -> ACCEPTED

Alternative transitions:
- REJECTED: invalid or no incremental value;
- AMBIGUOUS: observational equivalence remains;
- REFINE: counterexample suggests a narrower or revised expression;
- SPLIT: one candidate conflates multiple contexts;
- SUSPENDED: evidence is insufficient or contradictory;
- RETIRED: repeatedly fails in its declared scope.

Acceptance is scoped, not universal. Store the domain, evidence version, known counterexamples, and confidence calibration. A candidate may be accepted for one environment and remain unknown elsewhere.

Every transition is append-only and records the evidence that caused it. Do not overwrite the prior candidate definition.

## 8. Metrics

Primary:
- accepted useful primitives per 1,000 proposal/evaluation units;
- Gate-to-Locked-Test generalization gap;
- incremental predictive or compression gain over fixed features;
- proposal diversity after empirical-equivalence grouping;
- total compute and measurement cost;
- false acceptance and false discovery rates;
- counterexample recovery rate;
- held-out world-family transfer.

Secondary:
- time/operations to first useful primitive;
- proposer-family contribution and redundancy;
- Pareto frontier size;
- complexity distribution;
- candidate survival and retirement curves;
- coverage versus selective risk.

Report metrics per independent world seed and family. Do not treat correlated rows from one world as independent replicates.

## 9. Required adversarial conditions

Include correlated features that create spurious shortcuts; duplicated and near-duplicated observations; missing channels and measurement noise; shifted thresholds and unseen category values; label noise and contradictory examples; proposer families that emit many low-quality candidates; a deliberately strong but brittle proposer; a world where all available evidence is insufficient; and a held-out world whose useful primitive is outside the current DSL.

The final condition is a boundary test: the system should report DSL coverage failure or uncertainty, not pretend that exhaustive search found an open-world primitive.

## 10. Yijing-inspired proposal priors

Only after generic portfolio baselines are stable, add prior variants:

- no symbolic prior;
- generic binary complementary partition;
- generic four-way hierarchical partition;
- trigram-like factorized partition;
- transition/change prior inspired by gua transformation;
- capacity-matched random permutation;
- learnable prior.

Each prior must declare exactly where it acts: proposal distribution, grammar expansion, regularizer, candidate ranking, or budget allocation. Do not change multiple mechanisms at once.

Falsification conditions:
- gains vanish against capacity-matched generic priors;
- gains depend on a single generator family;
- calibration worsens;
- held-out world-family transfer does not improve;
- deliberately permuted priors perform equally well;
- the prior increases proposal count without increasing accepted utility.

Yijing-inspired structure is an inductive-bias hypothesis, not evaluator truth.

## 11. Security, reproducibility, and data contracts

Separate evaluator/environment and learner processes. Communicate through versioned JSONL messages.

Learner-visible payload may include observation schema and allowed observations, Support evidence, permitted measurement descriptions and costs, current candidate registry entries, and remaining budget.

It must exclude evaluator truth and hidden generator state, random seeds and world IDs if they encode generator identity, Locked Test samples and labels, oracle candidate IDs, and hidden scoring metadata.

For each episode, preserve immutable config and schema versions, learner input/output JSONL, proposal and allocation trace, candidate lifecycle event log, Gate decisions, Locked Test result stored separately, source commit, and environment version.

Run truth-mutation invariance and payload canary tests before benchmark claims.

## 12. Staged acceptance gates

Gate A — Protocol correctness:
- schema validation;
- canonicalization determinism;
- budget conservation;
- provenance completeness;
- no evaluator leakage;
- lifecycle transition validity.

Gate B — Tiny synthetic correctness:
- hand-computable worlds;
- exhaustive oracle comparison on tiny DSLs;
- duplicate and equivalent candidate handling;
- adversarial proposer tests.

Gate C — Controlled benchmark:
- at least 5 independent seeds to debug;
- at least 20 seeds for preliminary comparisons;
- equal-budget baselines;
- confidence intervals at world level.

Gate D — Generalization:
- held-out world families;
- unseen combinations and relations;
- noise and missingness shifts;
- a DSL-misspecification condition.

Gate E — Symbolic-prior ablation:
- capacity-matched generic priors;
- permuted controls;
- preregistered hypotheses and metrics.

No stage may be skipped by reporting a high training or Gate score.

## 13. Immediate implementation sequence

1. Define Proposal, ProposerFamily, CandidateSignature, BudgetAllocation, and LifecycleEvent schemas.
2. Implement canonical expression serialization and type checking.
3. Implement empirical equivalence grouping without claiming global equivalence.
4. Add STAT, RELATIONAL, RANDOM, and bounded EXHAUSTIVE proposers.
5. Add fixed equal allocation and round-robin before adaptive allocation.
6. Add immutable per-proposal traces and budget accounting.
7. Add tiny-world oracle tests and adversarial proposer tests.
8. Compare proposer portfolios under equal budgets.
9. Only then add UCB/racing/Pareto allocation.
10. Only after generic A3 passes, test Yijing-inspired priors.

## 14. Research conclusion

The key A3 hypothesis is that heterogeneous proposal mechanisms, when coordinated under a strict shared budget and evidence firewall, may discover a more diverse and useful set of reusable primitives than any single proposal mechanism.

The key null hypothesis is equally important: the apparent gain may disappear when proposal count, compute, validation access, and DSL capacity are controlled.

A3 succeeds scientifically even if the null hypothesis wins, provided it identifies which proposer mechanisms add value, where they fail, and what remains unidentifiable.
