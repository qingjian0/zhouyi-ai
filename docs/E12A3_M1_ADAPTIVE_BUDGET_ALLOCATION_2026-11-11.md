# E12-A3-M1 Adaptive Budget Allocation

Date: 2026-11-11  
Status: UCB1 core, four-way adaptive benchmark, five reward variants, and Support-context router ablations implemented; context-conditioned routing has not yet established a reliable advantage over fixed allocation.

## 1. Research question

Can a coordinator allocate a fixed proposal budget across heterogeneous proposer families based on early evidence, improving held-out utility over:
- equal fixed allocation;
- round-robin;
- any single proposer;
- bounded DSL enumeration?

The target is not to reward the family that emits the most candidates. The coordinator must identify which proposal mechanism is useful for the current task while preserving exploration and preventing validation leakage.

## 2. Evidence split and data flow

The outer experiment uses four disjoint partitions:
1. Support: proposal generation and task-context derivation.
2. Gate-Dev: adaptive allocator feedback only.
3. Gate-Final: one-time selection after the allocation policy is frozen.
4. Locked Test: one-time final scoring after selection is frozen.

For the Support-context router, Support is internally divided into:
- Proposal-Support: 48 observations, passed to proposer generators.
- Context-Support: 16 observations, used only to compute task descriptors.

Proposal generation must not receive Context-Support rows or labels. Gate-Final and Locked Test are not arguments to allocation functions. This is API-level data-flow separation, not process-isolated security.

## 3. Budget and duplicate accounting

All main M1 benchmarks use a fixed proposal-slot budget of 31 per method and episode.

- Every emitted proposal consumes a slot, including a duplicate expression, because proposer computation was spent.
- Identical canonical expressions are stored once with all proposer-family provenance.
- A duplicate expression is evaluated once per evidence partition.
- Gate-Dev and Gate-Final unique-evaluation counts are logged separately.
- Proposal slots are matched; CPU operations and wall-clock cost are not yet matched.

## 4. UCB1 allocator core

The stateful UCB1 core is implemented in `prototype/e12a3_adaptive_allocator.py`.

It provides:
- fixed global proposal-slot budget;
- batch-based allocation;
- per-family exploration floor;
- mean reward plus confidence bonus;
- deterministic family-ID tie-breaking;
- normalized finite rewards in [0, 1];
- pending-batch acknowledgement;
- immutable allocation-event snapshots.

Because proposer queues are finite and sampled without replacement, reward distributions are non-stationary. UCB1 is treated as a finite-budget heuristic, not a setting with classical stationary-bandit regret guarantees.

## 5. Four-way adaptive benchmark (M1)

The first 20-seed × 2-task experiment completed 40 episodes. At 31 proposal slots per method:

| Method | Mean Locked-Test accuracy |
|---|---:|
| EQUAL | 91.72% |
| ROUND_ROBIN | 91.72% |
| UCB1_ADAPTIVE | 90.47% |
| BOUNDED_ENUM | 90.08% |

UCB1 minus EQUAL was -1.25 percentage points; the paired seed-clustered 95% t interval was [-2.94, +0.44] pp. This does not establish a statistically reliable difference, but the point estimate favors fixed allocation.

Full results: `E12A3_M1_FOUR_WAY_RESULTS_2026-11-11.md`.

## 6. Reward-function ablation (M1.1)

Five Gate-Dev reward definitions were compared over another 40-episode run:

| Adaptive reward | Mean Locked-Test accuracy |
|---|---:|
| MEAN | 90.47% |
| MAX | 90.39% |
| TOP2_MEAN | 90.47% |
| DELTA_BEST | 89.45% |
| MEAN_NOVELTY | 90.55% |
| EQUAL / ROUND_ROBIN | 91.72% |

No adaptive reward variant exceeded the fixed baselines. Every paired seed-clustered 95% interval versus EQUAL included zero.

Full results: `E12A3_M1_1_REWARD_ABLATION_RESULTS_2026-11-11.md`.

## 7. Support-context task router (M1.2)

The task matrix was expanded to Threshold, Pairwise Difference, and a new PARITY task. Support was split into Proposal-Support 48 / Context-Support 16. A router used four context probes per proposer family (12 total) and allocated the remaining 19 slots to the family with the highest context descriptor.

The initial random-probe router reached 77.19% mean Locked-Test accuracy versus 77.60% for EQUAL. It improved on Threshold and PARITY but underperformed on Pairwise Difference.

Full results: `E12A3_M1_2_CONTEXT_ROUTER_RESULTS_2026-11-11.md`.

## 8. Probe and descriptor ablations (M1.2b / M1.2c)

Grammar-stratified probes improved PARITY by 2.19 pp over random probes, but aggregate accuracy improved only 0.26 pp and remained below EQUAL. The paired interval versus random probes included zero.

Full results: `E12A3_M1_2B_STRATIFIED_PROBE_RESULTS_2026-11-11.md`.

With the same stratified probes, descriptor aggregation produced:

| Descriptor | Mean Locked-Test accuracy |
|---|---:|
| TOP3_MEAN | 77.45% |
| TOP2_MEAN | 78.18% |
| MAX | 78.49% |
| EQUAL / ROUND_ROBIN | 77.60% |
| BOUNDED_ENUM | 82.08% |

MAX is the strongest context-router point estimate, but its paired 95% interval versus EQUAL was [-2.87, +4.64] pp. It does not establish a reliable advantage.

Full results: `E12A3_M1_2C_DESCRIPTOR_AGGREGATION_RESULTS_2026-11-11.md`.

## 9. Interpretation

The evidence so far rejects the simple hypothesis that context-free UCB1 or a small static Support-context router automatically improves budget allocation.

Three findings matter:
1. Proposer specialization is task-dependent: STAT/RANDOM are strong on Threshold, RELATIONAL on Pairwise Difference, and STAT is the strongest single proposer on PARITY.
2. Global UCB1 reward tuning did not beat equal allocation.
3. Support-context routing is sensitive to probe coverage and descriptor aggregation, but current variants remain statistically inconclusive and below bounded enumeration.

The strongest overall control remains BOUNDED_ENUM in the three-task context-router experiment (82.08%). This is a finite grammar control, not evidence of general open-world discovery.

## 10. Next implementation sequence

1. Expand Support-derived descriptors beyond accuracy: operator coverage, feature/relation-role coverage, candidate score gaps, and uncertainty.
2. Test a transparent task-structure router against a contextual bandit, with identical proposal and evaluation budgets.
3. Add held-out relation/operator families, noisy labels, correlated distractors, and sparse composition tasks.
4. Match measured evaluation operations and wall-clock compute, not only proposal slots.
5. Add process-isolated evaluator/learner execution for stronger leakage guarantees.
6. Only after generic task-conditioned routing is validated, introduce Yijing-inspired structural priors as separately ablated, capacity-matched proposal-distribution variants.

## 11. Conclusion

Proposer diversity alone is insufficient. Context-free reward tuning also failed to improve over fixed allocation. The next meaningful research problem is to infer task structure from Support evidence and use that context to route computation, while retaining strict Gate-Final and Locked-Test isolation.
