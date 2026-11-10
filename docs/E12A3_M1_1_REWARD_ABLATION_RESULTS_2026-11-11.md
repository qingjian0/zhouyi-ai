# E12-A3-M1.1 Reward-Function Ablation Results

Date: 2026-11-11  
GitHub Actions run: `42874682461`  
Artifact: `e12a3-m1-1-reward-ablation` (artifact ID `13791036633`)  
CI: workflow run `42874682461` — full repository workflow passed  
Protocol: 20 seeds × 2 task families = 40 episodes; 31 proposal slots per method.

## 1. Reward variants

All variants use the same Support / Gate-Dev / Gate-Final / Locked-Test protocol, the same proposal pools, and the same UCB1 allocator core. Only the bounded Gate-Dev batch reward changes.

- MEAN: mean accuracy of newly evaluated unique candidates.
- MAX: highest accuracy among newly evaluated unique candidates.
- TOP2_MEAN: mean of the best two new unique candidate accuracies.
- DELTA_BEST: increase in best-so-far Gate-Dev accuracy.
- MEAN_NOVELTY: mean accuracy multiplied by the fraction of emitted proposals that are new unique candidates.

Every reward is bounded in [0, 1]. Duplicate-only batches receive zero reward.

## 2. Aggregate Locked-Test results

| Method | Mean Locked-Test accuracy | Difference vs EQUAL |
|---|---:|---:|
| EQUAL | **91.72%** | — |
| ROUND_ROBIN | **91.72%** | 0.00 pp |
| UCB1_MEAN | 90.47% | -1.25 pp |
| UCB1_MAX | 90.39% | -1.33 pp |
| UCB1_TOP2_MEAN | 90.47% | -1.25 pp |
| UCB1_DELTA_BEST | 89.45% | -2.27 pp |
| UCB1_MEAN_NOVELTY | 90.55% | -1.17 pp |
| BOUNDED_ENUM | 90.08% | -1.64 pp |

No adaptive reward variant exceeded equal allocation or round-robin.

## 3. Paired seed-clustered comparisons against EQUAL

The 20 seed IDs are the clusters; the two task-family differences are averaged within each seed.

| Adaptive reward | Mean difference | 95% t interval | Seed clusters (win / tie / loss) |
|---|---:|---:|---:|
| MEAN | -1.25 pp | [-2.94, +0.44] pp | 0 / 16 / 4 |
| MAX | -1.33 pp | [-3.12, +0.47] pp | 0 / 17 / 3 |
| TOP2_MEAN | -1.25 pp | [-2.94, +0.44] pp | 0 / 16 / 4 |
| DELTA_BEST | -2.27 pp | [-4.71, +0.18] pp | 2 / 11 / 7 |
| MEAN_NOVELTY | -1.17 pp | [-2.86, +0.52] pp | 0 / 17 / 3 |

All intervals include zero. These preliminary results do not establish statistically reliable differences, but every adaptive point estimate is below the fixed baseline.

## 4. Task-family breakdown

| Method | Threshold | Pairwise difference |
|---|---:|---:|
| EQUAL / ROUND_ROBIN | 91.56% | 91.88% |
| UCB1_MEAN | 91.25% | 89.69% |
| UCB1_MAX | 90.47% | 90.31% |
| UCB1_TOP2_MEAN | 91.25% | 89.69% |
| UCB1_DELTA_BEST | 90.16% | 88.75% |
| UCB1_MEAN_NOVELTY | 91.25% | 89.84% |

The strongest specialist still changes by task: RANDOM is strongest on Threshold (95.63%), while RELATIONAL is strongest on Pairwise Difference (98.44%). All current context-free UCB variants fail to reach the equal-allocation result on either task-family aggregate.

## 5. Allocation behavior

Mean family slots per episode:

| Reward | RANDOM | RELATIONAL | STAT |
|---|---:|---:|---:|
| MEAN | 12.15 | 7.65 | 11.20 |
| MAX | 10.33 | 10.75 | 9.93 |
| TOP2_MEAN | 11.25 | 9.33 | 10.43 |
| DELTA_BEST | 17.25 | 7.90 | 5.85 |
| MEAN_NOVELTY | 12.08 | 8.53 | 10.40 |

MAX and TOP2_MEAN move allocations closer to equal, but do not improve held-out accuracy. DELTA_BEST tends to over-allocate to RANDOM after early high rewards, showing a potential early-reward lock-in failure.

## 6. Interpretation

The negative result is consistent across five reward definitions. Simply changing how a context-free UCB1 arm is rewarded does not solve the task-heterogeneity problem.

The likely missing information is task context. A global average reward combines worlds in which different proposer families are specialists. It can therefore make the allocator converge toward a family with strong average early rewards while under-allocating to a specialist that is highly valuable only in a subset of tasks.

The next experiment should test a Support-derived contextual prior or contextual bandit, and compare it with a simpler task-structure router. Any context must be computed from Support only; Gate-Dev may update the allocator, while Gate-Final and Locked Test remain isolated.

## 7. Limitations

- Two synthetic task families and finite hand-specified candidate pools.
- Proposal slots are matched; CPU operations and wall-clock cost are not.
- UCB1 reward distributions are non-stationary because finite pools are sampled without replacement.
- Gate-Dev is adaptively queried and may be overfit; Gate-Final and Locked Test are separate.
- This is API-level separation, not process isolation.
- No Yijing-inspired prior is included.

## 8. Next experiments

1. Support-derived task descriptors and contextual allocation.
2. A transparent task-structure router as a simpler control.
3. Compare contextual allocation, fixed equal, round-robin, best specialist, and bounded enumeration.
4. Add held-out task families to test whether context generalizes rather than memorizes two known tasks.
5. Match measured evaluation operations and wall-clock compute.
