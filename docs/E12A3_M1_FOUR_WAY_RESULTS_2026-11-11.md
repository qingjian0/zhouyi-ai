# E12-A3-M1 Four-Way Adaptive Budget Benchmark Results

Date: 2026-11-11  
Commit under test: `882c34f458188df19718180599fde2505c17caaf`  
GitHub Actions run: `42874202373`  
Artifact: `e12a3-m1-four-way-benchmark` (artifact ID `13790074133`)  
Protocol: 20 seeds × 2 task families = 40 episodes; 31 proposal slots per method.

## 1. Data isolation and accounting

Each episode used disjoint partitions:
- Support: 64 observations
- Gate-Dev: 32 observations
- Gate-Final: 32 observations
- Locked Test: 32 observations

Proposal generators received Support only. The UCB1-inspired allocator received Support and Gate-Dev only. Gate-Final selected once among the frozen candidate registry. Locked Test scored only the selected candidate.

All seven methods consumed exactly 31 proposal slots in every episode. Duplicate expressions consumed proposal slots because proposal computation had occurred, but were deduplicated before Gate-Final evaluation. Adaptive Gate-Dev evaluation was cached by canonical expression.

The adaptive method used a mean of Gate-Dev accuracy across newly evaluated unique candidates as the batch reward. Duplicate-only batches received zero reward.

## 2. Aggregate Locked-Test results

| Method | Selection coverage | Mean Locked-Test accuracy |
|---|---:|---:|
| STAT | 100% | 83.83% |
| RELATIONAL | 100% | 86.48% |
| RANDOM | 100% | 84.84% |
| BOUNDED_ENUM | 100% | 90.08% |
| EQUAL | 100% | 91.72% |
| ROUND_ROBIN | 100% | 91.72% |
| UCB1_ADAPTIVE | 100% | 90.47% |

Coverage means that a candidate was available for selection. It is 100% for every method and is not a measure of correctness. Accuracy is therefore the informative outcome here.

## 3. Task-family breakdown

| Method | Threshold | Pairwise difference |
|---|---:|---:|
| STAT | 93.91% | 73.75% |
| RELATIONAL | 74.53% | 98.44% |
| RANDOM | 95.63% | 74.06% |
| BOUNDED_ENUM | 91.25% | 88.91% |
| EQUAL | 91.56% | 91.88% |
| ROUND_ROBIN | 91.56% | 91.88% |
| UCB1_ADAPTIVE | 91.25% | 89.69% |

The task families have different specialist strengths: STAT/RANDOM are strong on the threshold task, while RELATIONAL is strong on pairwise difference. This is exactly the type of heterogeneity a coordinator must exploit.

## 4. Paired comparison by seed

The 20 seed IDs were treated as clusters, averaging the two task-family differences within each seed. Differences below are UCB1_ADAPTIVE minus the comparator.

| Comparator | Mean difference | 95% t interval | Seed clusters (win / tie / loss) |
|---|---:|---:|---:|
| EQUAL | -1.25 pp | [-2.94, +0.44] pp | 0 / 16 / 4 |
| ROUND_ROBIN | -1.25 pp | [-2.94, +0.44] pp | 0 / 16 / 4 |
| BOUNDED_ENUM | +0.39 pp | [-4.66, +5.44] pp | 9 / 2 / 9 |
| RELATIONAL | +3.98 pp | [+0.33, +7.64] pp | 12 / 4 / 4 |

The confidence interval for UCB1 versus EQUAL includes zero. This preliminary result does not establish a statistically reliable disadvantage, but the point estimate favors the simpler fixed policies.

## 5. Allocation behavior

Mean proposal-slot allocation per episode:
- RANDOM: 12.15
- STAT: 11.20
- RELATIONAL: 7.65

Range across episodes:
- RANDOM: 8–16
- STAT: 4–19
- RELATIONAL: 4–12

The adaptive method evaluated a mean of 29 unique candidates on Gate-Dev and 29 on Gate-Final, within the 31-slot proposal budget. The remaining difference is due to cross-family duplicate expressions.

## 6. Interpretation

This first four-way experiment does **not** show that the current UCB1 reward and allocator improve over equal allocation or round-robin. EQUAL and ROUND_ROBIN tie at 91.72%; UCB1_ADAPTIVE reaches 90.47%.

The current reward is the mean Gate-Dev accuracy of newly unique candidates in a batch. That reward estimates average candidate quality, but the final objective is to ensure at least one high-quality candidate survives Gate-Final selection. These objectives are not identical. The allocator can prefer a family with many moderately accurate candidates over one that occasionally emits a very strong candidate.

The task-family breakdown also indicates that a global, context-free arm mean is insufficient when the best proposer changes with task structure. A task-conditioned or contextual allocator is a natural next hypothesis, but it must be tested against the same budget and held-out task families.

## 7. Limitations

- Only two clean synthetic task families and a finite hand-specified predicate grammar.
- Proposal slots are matched; CPU operations and wall-clock time are not.
- UCB1 reward distributions are non-stationary because each finite proposer queue is sampled without replacement.
- Gate-Dev is adaptively queried and may be overfit; Gate-Final is separate but only one 32-row sample per episode.
- This is API-level separation, not process-isolated execution.
- No Yijing-inspired prior is included.

## 8. Next experiments

1. Reward ablation: mean batch accuracy vs incremental best-utility improvement vs top-k utility vs novelty-adjusted utility.
2. Contextual allocation: use Support-derived task descriptors, never Gate-Final or Locked-Test features/labels.
3. Compare UCB1 heuristic, discounted/sliding-window UCB, Thompson-style allocation, equal, round-robin, and best specialist.
4. Add noisy, correlated-distractor, sparse-composition, and held-out relation/operator tasks.
5. Add paired confidence intervals over more independent worlds and match measured evaluation operations / wall-clock cost.
6. Only after generic allocation is validated, test Yijing-inspired structural priors as capacity-matched proposal-distribution variants.
