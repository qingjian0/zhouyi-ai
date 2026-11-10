# E12-A3-M1 Adaptive Budget Allocation

Date: 2026-11-11  
Status: four-way adaptive benchmark and tests are implemented; E12-specific CI steps passed in run 42874202373; initial 40-episode results are recorded; full legacy workflow, CPU-cost matching, broader task matrix, and process isolation remain pending  
Motivation: E12-A3-M0 exact-budget result shows equal-share round-robin underperforms the best specialist on the current two-task synthetic benchmark.

## 1. Research question

Can a coordinator allocate a fixed proposal budget across heterogeneous proposer families based on early evidence, improving selection coverage and held-out utility over:
- equal fixed allocation;
- round-robin;
- any single proposer;
- bounded DSL enumeration?

The target is not to reward the family that emits the most candidates. The coordinator must identify which proposal mechanism is useful for the current task while preserving exploration and preventing validation leakage.

## 2. Hypothesis and null

Primary hypothesis H1:
An adaptive allocator with an exploration floor can improve selection coverage and/or held-out utility over fixed equal-share allocation under the same proposal and evaluation budget.

Null H0:
After accounting for exploration, candidate duplication, and evaluation cost, adaptive allocation does not improve over the best fixed allocation or best specialist.

A result supporting H0 is scientifically useful. It means task-specific specialist selection or a simpler fixed policy is preferable to a learned coordinator for the tested task family.

## 3. Evidence split

Use four roles:

1. Support: proposer input and exact/soft candidate screening.
2. Gate-Dev: repeated, logged feedback for allocator reward updates.
3. Gate-Final: one-time candidate selection after allocation and all policy choices are frozen.
4. Locked Test: one-time final evaluation, never passed to the learner or allocator.

Gate-Dev queries are an adaptive resource and must be counted. Gate-Final must not influence budget allocation, early stopping, or hyperparameter selection. If data volume is insufficient for four disjoint splits, use nested independent worlds rather than reusing one Gate partition and pretending it is untouched.

## 4. Global budget and candidate accounting

Let total proposal budget be B. Each candidate consumes a declared proposal slot and a separately measured evaluation cost.

Before a candidate consumes a new slot:
- canonicalize its expression;
- check syntactic identity;
- check observed equivalence under the named Support snapshot;
- if already present, attach proposer provenance to the existing candidate and do not charge a duplicate evaluation;
- if structurally distinct but behaviorally equivalent, retain both identities but group them in the empirical equivalence class.

Every proposer family receives an exploration floor m_i. Require sum(m_i) <= B. The remaining budget is allocated adaptively. No family may receive more than the remaining global budget.

## 5. Candidate reward

Do not reward raw candidate count or Support accuracy alone.

For a candidate c, define a Gate-Dev utility with preregistered terms:

U(c) = GateDevScore(c) - lambda * Complexity(c) - mu * EvalCost(c) + nu * Novelty(c)

GateDevScore may be accuracy for the initial noise-free baseline, but log-loss or Brier score is preferred once candidates produce calibrated probabilities.

Novelty is measured against the existing candidate registry, not by string distance alone. It may include:
- new behavior signature on Support;
- new feature/role coverage;
- new relation type;
- new held-out task-family transfer evidence.

Initial M1 prototype reward for family i is the mean Gate-Dev accuracy of newly evaluated unique candidates in its emitted batch; a duplicate-only batch receives zero. The reward is already in [0, 1]. Candidate count is not added to reward. This is a deliberately simple first reward, not the final utility function. Because proposer pools are finite and sampled without replacement, reward distributions are non-stationary; UCB1 is treated as a finite-budget heuristic here, not as a setting with classical stationary-bandit regret guarantees. Later experiments must compare discounted/sliding-window UCB, Thompson-style models, and fixed allocation under identical budgets.

## 6. Allocator candidates

Compare at least:

A. Equal fixed allocation  
B. Round-robin  
C. UCB1 on incremental Gate-Dev utility  
D. Thompson sampling with a calibrated reward model  
E. Successive halving / racing  
F. Novelty-aware UCB  
G. Single best proposer, selected on training worlds only  
H. BOUNDED_ENUM control  
I. Exact small-instance oracle allocation (diagnostic upper bound only)

For UCB1:
- initialize every family with the preregistered exploration floor;
- update family mean reward and count only after a complete batch;
- choose the next family by mean_reward + c * sqrt(log(total_batches + 1) / family_batches);
- deterministic tie-break by family ID;
- enforce the global remaining budget;
- freeze c before Gate-Final.

For Thompson sampling, use a reward likelihood appropriate to the score; do not treat arbitrary accuracy values as Bernoulli success without calibration.

## 7. Anti-leakage and anti-collapse controls

- The allocator receives only Support and Gate-Dev-derived rewards.
- It never receives Locked Test, Gate-Final, evaluator truth, world seed, hidden rule IDs, or task-generator code.
- Every Gate-Dev query and reward update is logged.
- A fixed Gate-Dev query budget is enforced.
- Run truth-mutation invariance: changing evaluator truth while holding learner-visible observations fixed must not change proposals or allocations.
- Run Gate-Final mutation invariance: changing Gate-Final labels must not change the frozen allocation trace.
- Keep a nonzero exploration floor so early noisy reward cannot eliminate a family.
- Add a candidate-provenance ledger so multiple proposers agreeing on one expression do not count as multiple independent discoveries.

## 8. Benchmark matrix

At minimum:
- unary threshold task;
- pairwise difference task;
- sparse non-contiguous Boolean composition (A+C+E);
- correlated distractor task;
- noisy observation task;
- held-out relation/operator family;
- DSL-misspecification task.

Run at least 20 independent world seeds per task for preliminary results. Report:
- selection coverage;
- unconditional utility with abstention penalty;
- conditional Locked Test accuracy;
- Brier/log-loss and calibration;
- unique candidate count after syntax/equivalence grouping;
- proposer-family budget share;
- total proposal slots and measured evaluation operations;
- Gate-Dev query count;
- regret against exact small-instance oracle;
- confidence intervals clustered by world seed.

## 9. Acceptance criteria

The adaptive allocator is promising only if:
1. it improves over equal allocation on held-out world families, not just Gate-Dev;
2. gains survive exact proposal-slot and measured-compute matching;
3. it does not increase false acceptance or calibration error;
4. it remains stable under candidate ordering and proposer duplication;
5. it does not collapse to one family on a small or noisy early sample;
6. it improves an unconditional metric that penalizes abstention, not only conditional accuracy.

If it only reallocates budget toward RELATIONAL on the two current tasks, it has learned a narrow task-family preference, not a general allocation strategy.

## 10. Integration with sparse composition

The sparse composition engine is a separate proposal family with dependency costs.

A composition candidate must charge:
- the cost of proposing or retrieving each parent primitive;
- the composition-generation slot;
- the composition evaluation cost.

Do not allow the composition engine to receive an effectively free pool of A1 primitives while other proposers pay for discovery. Compare primitive-only, composition-only, and combined portfolios with the same global budget.

## 11. Initial allocator implementation

The stateful UCB1 core is implemented in `prototype/e12a3_adaptive_allocator.py`. A four-way adaptive benchmark is implemented in `prototype/e12a3_adaptive_benchmark.py`.

The benchmark uses disjoint Support / Gate-Dev / Gate-Final / Locked-Test partitions:
- proposal generators receive Support only;
- the adaptive allocator receives Support and Gate-Dev only;
- Gate-Final is used once to select among the frozen candidate registry;
- Locked Test is scored only after the Gate-Final selection is fixed.

Cross-family duplicate expressions retain all proposer provenance in one candidate registry. A repeated expression still consumes a proposal slot because the proposer spent computation emitting it, but it is evaluated on Gate-Dev only once and does not earn duplicate novelty reward.

The adaptive allocator logs family, requested/emitted slots, new unique candidates, bounded reward, and remaining budget. Its allocation function has no Gate-Final or Locked-Test parameter. Selection and Locked-Test scoring are separate functions.

This implementation establishes API-level data-flow separation and mutation-invariance tests; it is not process-isolated and must not be described as a hard security boundary.

The UCB1 core tests cover exploration-floor ordering, reward-sensitive choice, deterministic ties, budget conservation including a final partial batch, invalid reward handling, and event traces. Adaptive benchmark tests cover four-way split disjointness, API boundaries, deterministic allocation, exact proposal budget, and separate Gate-Final/Test stages.

## 12. Next implementation sequence

The first stateful UCB1 core is implemented in `prototype/e12a3_adaptive_allocator.py`.

It provides:
- a fixed global proposal-slot budget;
- batch-based allocation;
- a per-family exploration floor;
- UCB1 mean-reward plus confidence bonus;
- deterministic family-ID tie-breaking;
- finite normalized reward validation in [0, 1];
- explicit pending-batch acknowledgement;
- immutable allocation-event snapshots.

Tests cover exploration-floor ordering, reward-sensitive choice, deterministic ties, budget conservation including a final partial batch, invalid reward handling, and event traces.

This is an allocator primitive, not an end-to-end adaptive learning result. It does not itself inspect candidate pools, observations, Gate-Dev, Gate-Final, or Locked Test. The experiment harness must calculate a preregistered Gate-Dev reward and pass only that scalar to the allocator.

## 12. Next implementation sequence

1. Add cross-family canonical-expression deduplication with provenance retention.
2. Implement four-way data roles and query accounting.
3. Implement fixed equal and round-robin allocators under exact budgets.
4. Implement UCB1 with exploration floor and deterministic tie-break.
5. Add Gate-Final freeze and Locked Test isolation tests.
6. Add exact tiny-world oracle and truth-mutation tests.
7. Run the expanded task matrix over independent world seeds.
8. Only after the generic adaptive allocator is validated, introduce Yijing-inspired priors as proposal-distribution variants.

## 13. First four-way benchmark result

The first 20-seed × 2-task experiment is recorded in `E12A3_M1_FOUR_WAY_RESULTS_2026-11-11.md`.

At 31 proposal slots per method:
- EQUAL and ROUND_ROBIN both reached 91.72% mean Locked-Test accuracy.
- UCB1_ADAPTIVE reached 90.47%.
- BOUNDED_ENUM reached 90.08%.
- The UCB1 minus EQUAL paired seed-clustered difference was -1.25 percentage points, with a 95% t interval of [-2.94, +0.44] pp.

This is not evidence that UCB1 improves over fixed allocation. The confidence interval includes zero, and the point estimate favors the simpler fixed methods. The current mean-batch-accuracy reward and context-free allocator are not yet adequate.

## 14. Reward-function ablation follow-up

Five Gate-Dev reward definitions were compared in a 20-seed × 2-task run. None exceeded EQUAL or ROUND_ROBIN. Their aggregate Locked-Test accuracies ranged from 89.45% to 90.55%, against 91.72% for both fixed baselines. Paired seed-clustered confidence intervals included zero for every adaptive-vs-equal comparison.

Detailed results: `E12A3_M1_1_REWARD_ABLATION_RESULTS_2026-11-11.md`.

The current evidence points away from further context-free reward tuning and toward task-conditioned allocation. The next control should be a transparent Support-derived task-structure router, followed by a contextual bandit comparison on held-out task families.

## 15. Conclusion

The E12-A3-M0 result shows that proposer diversity alone is insufficient. The next meaningful research problem is resource allocation under task uncertainty, duplicate candidates, and unequal proposer specialization.

E12-A3-M1 will test whether the coordinator can learn where to spend computation without learning from its final evaluation set.
