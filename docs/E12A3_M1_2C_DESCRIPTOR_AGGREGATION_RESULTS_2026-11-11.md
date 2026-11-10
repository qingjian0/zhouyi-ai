# E12-A3-M1.2c Context Descriptor Aggregation Results

Date: 2026-11-11  
GitHub Actions run: `42876314295`  
Artifact: `e12a3-m1-2-context-router` (artifact ID `13791094470`)  
Protocol: 20 seeds × 3 task families = 60 episodes; 31 proposal slots per method.

## 1. Compared descriptor aggregation

All variants used the same grammar-stratified four-proposal batch per family, the same 16-row Context-Support partition, and the same 12 context evaluations:
- TOP3_MEAN: average of the best three probe accuracies.
- TOP2_MEAN: average of the best two.
- MAX: best single probe accuracy.

Only the aggregation rule changed.

## 2. Aggregate Locked-Test results

| Method | Mean Locked-Test accuracy |
|---|---:|
| BOUNDED_ENUM | **82.08%** |
| STAT | 81.51% |
| SUPPORT_CONTEXT_ROUTER_STRATIFIED_MAX | 78.49% |
| SUPPORT_CONTEXT_ROUTER_STRATIFIED_TOP2 | 78.18% |
| EQUAL / ROUND_ROBIN | 77.60% |
| SUPPORT_CONTEXT_ROUTER_STRATIFIED_TOP3 | 77.45% |
| SUPPORT_CONTEXT_ROUTER_RANDOM | 77.19% |
| UCB1_MEAN | 76.20% |

The MAX descriptor is the best context-router point estimate so far, but it does not establish a reliable improvement over EQUAL.

## 3. Paired seed-clustered comparisons against EQUAL

| Descriptor | Mean difference | 95% t interval | Seed clusters (win / tie / loss) |
|---|---:|---:|---:|
| TOP3_MEAN | -0.16 pp | [-3.74, +3.43] pp | 8 / 2 / 10 |
| TOP2_MEAN | +0.57 pp | [-3.33, +4.47] pp | 8 / 2 / 10 |
| MAX | +0.89 pp | [-2.87, +4.64] pp | 7 / 4 / 9 |

All intervals include zero. The point estimates favor TOP2/MAX over EQUAL, but the uncertainty is too large to claim an advantage.

## 4. Task-family breakdown

| Method | Threshold | Pairwise Difference | PARITY |
|---|---:|---:|---:|
| EQUAL / ROUND_ROBIN | 87.97% | 89.69% | 55.16% |
| Stratified TOP3_MEAN | 91.88% | 81.25% | 59.22% |
| Stratified TOP2_MEAN | 91.09% | 82.03% | 61.41% |
| Stratified MAX | 89.53% | 83.75% | 62.19% |
| BOUNDED_ENUM | 90.63% | 92.34% | 63.28% |

MAX improves PARITY and Pairwise Difference relative to TOP3_MEAN, but all three context routers remain below EQUAL on Pairwise Difference. The static task router still fails to allocate enough budget to RELATIONAL when that family is the specialist.

## 5. Interpretation

Descriptor aggregation matters: MAX is the strongest context-router variant in this ablation, and TOP2 is close. This is consistent with the actual selection objective, where one strong candidate can be more valuable than several moderately accurate candidates.

However:
- The confidence intervals remain wide and include zero.
- The router remains below BOUNDED_ENUM and STAT overall.
- The router's pairwise performance remains weak relative to the RELATIONAL specialist.
- A maximum score from four probes can be noisy and optimistic.

The next experiment should not merely increase the probe count. It should test whether a richer Support-derived task descriptor—operator coverage, feature-role coverage, and the score gap between top candidates—can identify task structure more reliably while preserving the same total budget.

## 6. Limitations

- Three synthetic tasks and finite hand-specified grammar.
- Only 16 Context-Support rows and four probes per family.
- Accuracy is a coarse, uncalibrated score.
- Proposal slots are matched; CPU and wall-clock cost are not.
- API-level separation only; not process-isolated.
- No Yijing-inspired prior is included.
