# E12-A3-M1.2b Grammar-Stratified Probe Results

Date: 2026-11-11  
GitHub Actions run: `42875957898`  
Artifact: `e12a3-m1-2-context-router` (artifact ID `13791751890`)  
Protocol: 20 seeds × 3 task families = 60 episodes; 31 proposal slots per method.

## 1. Compared probe strategies

Both variants use the same proposal pools, Support split, four-proposal-per-family exploration batch, 12 context evaluations, and remaining-budget routing rule.

- RANDOM: first four candidates from each seeded shuffled proposer pool.
- GRAMMAR_STRATIFIED: first cover distinct operators, then distinct feature/relation roles, then fill remaining slots.

## 2. Aggregate results

| Method | Mean Locked-Test accuracy |
|---|---:|
| BOUNDED_ENUM | **82.08%** |
| STAT | **81.51%** |
| EQUAL / ROUND_ROBIN | 77.60% |
| SUPPORT_CONTEXT_ROUTER_STRATIFIED | 77.45% |
| SUPPORT_CONTEXT_ROUTER_RANDOM | 77.19% |
| UCB1_MEAN | 76.20% |

The stratified probe improved over the random probe by only 0.26 percentage points. Paired by 20 seed clusters, the 95% t interval was [-2.71, +3.23] pp (5 wins, 12 ties, 3 losses). It did not establish a reliable improvement.

Against EQUAL, the stratified router was -0.16 pp with a 95% interval of [-3.74, +3.43] pp. It did not beat the fixed baseline.

## 3. Task breakdown

| Method | Threshold | Pairwise Difference | PARITY |
|---|---:|---:|---:|
| RANDOM probe router | 91.72% | 82.81% | 57.03% |
| Stratified probe router | 91.88% | 81.25% | 59.22% |
| EQUAL / ROUND_ROBIN | 87.97% | 89.69% | 55.16% |
| STAT | 94.69% | 73.75% | 76.09% |
| RELATIONAL | 74.38% | 98.13% | 52.97% |
| RANDOM | 95.94% | 73.75% | 53.91% |
| BOUNDED_ENUM | 90.63% | 92.34% | 63.28% |

Stratification slightly improved Threshold and PARITY, but further reduced Pairwise Difference performance. It still failed to route enough budget to RELATIONAL for the pairwise specialist.

## 4. Interpretation

Operator-stratified probing produced a small PARITY gain but did not improve the aggregate result. The current top-three mean descriptor still fails to identify the right specialist reliably from only four proposals and 16 context rows.

This suggests two distinct problems:
1. Probe coverage: the four proposals may still miss the correct feature/value combination.
2. Descriptor objective: averaging the top three may dilute one highly informative candidate. The final task is to include at least one strong candidate, so a maximum or top-one descriptor may be more aligned with the actual selection objective.

## 5. Next experiment

M1.2c will keep the same grammar-stratified probes and compare descriptor aggregation:
- top-three mean (current);
- top-two mean;
- maximum candidate accuracy.

All variants must use the same four probes, 12 context evaluations, 31 proposal slots, and the same Gate-Final / Locked-Test separation. No extra search budget is permitted.
