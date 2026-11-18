# E12-A3-M1 UCB Allocator Benchmark Preregistration

Date: 2026-11-11  
Status: protocol; no benchmark execution or performance result claimed.

## Question

Under one global proposal budget, does an adaptive allocator improve useful held-out primitive discovery over fixed allocation, round-robin, and the best specialist selected without access to final evaluation data?

## Arms

- FIXED_EQUAL: deterministic equal proposal-batch allocation.
- ROUND_ROBIN: deterministic cyclic allocation.
- UCB1_HEURISTIC: exploration-floor UCB allocation implemented in `prototype/e12a3_adaptive_allocator.py`.
- SUCCESSIVE_RACING: preregistered elimination/racing baseline (future implementation).
- SINGLE_SPECIALIST: family chosen on training worlds only, then frozen.
- ORACLE_ALLOCATOR: diagnostic upper bound using hidden per-family reward curves; never a deployable result.

The UCB1 label describes its index rule, not a classical regret guarantee. Rewards are portfolio-incremental, non-stationary, and dependent across proposer families; therefore textbook stationary-bandit regret bounds do not apply.

## Four-way evidence contract

1. **Support**: proposer input and candidate consistency screening.
2. **Gate-Dev**: bounded repeated feedback used only for allocation rewards. Every query, candidate score, and allocator update is logged and charged.
3. **Gate-Final**: independent one-time candidate selection after the allocator and all hyperparameters are frozen.
4. **Locked Test**: evaluator-only final scoring, one-time after selection. It never enters the learner or allocator.

If there is insufficient data for four disjoint partitions, use independently generated worlds for the Gate-Dev reward stream and Gate-Final/Locked-Test evaluation. Do not repeatedly query one tiny Gate and describe it as independent.

## Reward definition

After each fixed-size proposal batch, canonicalize and deduplicate candidates. Let B_t be the best Gate-Dev utility among all candidates proposed so far, and B_(t-1) the prior best. Define:

`r_t = max(0, B_t - B_(t-1))`

with B_t in [0,1] under a preregistered bounded metric (initially accuracy, later proper scoring utility). This reward is an incremental portfolio gain, not the candidate's absolute score. The allocator must never receive Gate-Final or Locked-Test outcomes.

Because rewards depend on the evolving portfolio, they are non-stationary. Report this limitation and compare against fixed/racing controls; do not claim formal UCB1 optimality.

## Budget and cost accounting

One allocation unit is one fixed-size batch. Every arm receives the same total proposal slots. Separately count:
- candidate generation operations;
- predicate/AST evaluations;
- canonicalization and deduplication operations;
- Gate-Dev queries;
- peak memory;
- wall-clock time.

Equal proposal slots alone do not establish equal compute. Run both slot-matched and measured-compute-matched comparisons.

## Task families

At minimum:
- unary threshold;
- pairwise relation;
- sparse A+C+E composition with B,D distractors;
- nested (A AND C) OR (B AND E);
- correlated distractors;
- noisy/missing observations;
- held-out relation/operator family;
- DSL-misspecification;
- observationally equivalent alternatives.

The direct composition engine and the COMPOSITIONAL proposer must be included as separate arms. Primitive discovery and composition costs are charged to the same global budget.

## Metrics

Primary:
- unconditional Locked-Test utility with a preregistered abstention penalty;
- selection coverage;
- false acceptance rate.

Secondary:
- conditional accuracy (always reported beside coverage);
- log loss/Brier score and calibration when probabilistic outputs exist;
- unique syntax candidates and empirical-equivalence classes;
- proposal/evaluation compute;
- family allocation shares;
- Gate-Dev queries and reward trajectory;
- world-seed clustered confidence intervals;
- regret versus exact small-world allocation oracle.

## Controls and falsification

- Candidate order, family order, opaque IDs, and serialization are randomized independently.
- Truth mutation with fixed learner-visible observations must not change proposals or allocation.
- Gate-Final mutation must not change the frozen allocation trace.
- Duplicating a proposer or its candidates must not create extra reward or free budget.
- A family with no incremental utility must not be rewarded for raw candidate count.
- Shuffled Yi-Xiang mappings are separate controls, never blended into the primary allocator reward.
- If UCB1 only routes budget to RELATIONAL on the two original tasks, it is a narrow task selector, not a general allocator.
- If gains disappear after measured-compute matching, there is no compute-efficiency advantage.
- If unconditional utility does not improve over the best specialist, increased coverage alone is insufficient.

## Release gate

No Yijing-specific prior experiment is started until the generic allocator has:
1. exact budget and evidence accounting;
2. truth/Gate-Final mutation tests;
3. all task families and independent world seeds;
4. matched-compute comparisons;
5. confidence intervals and a locked report.
