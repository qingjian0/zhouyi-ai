# E12-A3-M1.2 Support-Context Router Results

Date: 2026-11-11  
GitHub Actions run: `42875417511`  
Artifact: `e12a3-m1-2-context-router` (artifact ID `13790932518`)  
Protocol: 20 seeds × 3 task families = 60 episodes; 31 proposal slots per method.

## 1. Protocol

The 64-row Support partition was stratified into 48 Proposal-Support rows and 16 Context-Support rows. Proposal generators received Proposal-Support only. A Support-context descriptor was computed from four sampled candidates per family; the first four proposals from each family formed the mandatory exploration batch. The remaining 19 slots were assigned to the family with the highest top-three Context-Support accuracy.

All methods used the same proposal-slot budget and the same shared context-probe evaluation cost (12 candidate evaluations per episode). Gate-Final selected once; Locked Test scored only the frozen selection.

The task matrix contained Threshold, Pairwise Difference, and a new PARITY task.

## 2. Aggregate Locked-Test results

| Method | Mean Locked-Test accuracy |
|---|---:|
| STAT | **81.51%** |
| RELATIONAL | 75.16% |
| RANDOM | 74.53% |
| BOUNDED_ENUM | **82.08%** |
| EQUAL | 77.60% |
| ROUND_ROBIN | 77.60% |
| UCB1_MEAN | 76.20% |
| SUPPORT_CONTEXT_ROUTER | 77.19% |

The Support-context router did not beat equal allocation. Its paired difference versus EQUAL was -0.42 percentage points, with a 95% seed-clustered t interval of [-3.89, +3.05] pp (7 wins, 4 ties, 9 losses across 20 seed clusters).

UCB1_MEAN was -1.41 pp versus EQUAL, with a 95% interval of [-3.20, +0.39] pp.

## 3. Task-family breakdown

| Method | Threshold | Pairwise Difference | PARITY |
|---|---:|---:|---:|
| STAT | 94.69% | 73.75% | 76.09% |
| RELATIONAL | 74.38% | **98.13%** | 52.97% |
| RANDOM | **95.94%** | 73.75% | 53.91% |
| BOUNDED_ENUM | 90.63% | 92.34% | 63.28% |
| EQUAL / ROUND_ROBIN | 87.97% | 89.69% | 55.16% |
| UCB1_MEAN | 89.84% | 83.91% | 54.84% |
| SUPPORT_CONTEXT_ROUTER | 91.72% | 82.81% | 57.03% |

The context router improved over equal allocation on Threshold (+3.75 pp) and PARITY (+1.48 pp), but lost substantially on Pairwise Difference (-6.88 pp). This instability explains why its aggregate result did not improve.

## 4. Context descriptor diagnosis

Mean Support-context descriptors by task:

| Task | STAT | RELATIONAL | RANDOM |
|---|---:|---:|---:|
| Threshold | 0.641 | 0.525 | 0.653 |
| Pairwise Difference | 0.645 | 0.568 | 0.631 |
| PARITY | 0.518 | 0.528 | 0.507 |

On PARITY, the descriptor failed to identify STAT as the specialist. The likely cause is probe sampling: the first four proposals were selected from shuffled pools, so the four-row probe can miss a rare but structurally important operator such as PARITY. The top-three mean then dilutes the signal further.

The context router's average family allocations were:
- STAT: 10.97 slots
- RELATIONAL: 8.12 slots
- RANDOM: 11.92 slots

The global allocation remained close to equal, rather than adapting strongly to the task specialist.

## 5. Interpretation

This experiment does not establish that Support-context routing is better than equal allocation. It does, however, expose a concrete design failure: a small random context probe is not guaranteed to cover the operator families that matter.

The next correction is not to increase the context budget. Instead, make the existing four-proposal probe per family grammar-stratified:
- select one candidate from each distinct operator family first;
- then fill remaining probe slots with distinct feature/relationship roles;
- preserve the same four-proposal exploration batch and 12 total context evaluations.

This is a testable correction for probe coverage, not evidence that the router will succeed.

## 6. Limitations

- Three synthetic tasks and a finite hand-specified predicate grammar.
- Context-Support has only 16 rows.
- Four-proposal probes remain noisy even when grammar-stratified.
- Proposal slots are matched; CPU operations and wall-clock cost are not.
- API-level separation only; not process-isolated.
- No Yijing-inspired prior is included.

## 7. Next experiment

M1.2b will compare random four-candidate probes against grammar-stratified four-candidate probes under identical task splits, candidate pools, and 31-slot budgets. It must retain EQUAL, ROUND_ROBIN, UCB1_MEAN, specialists, and BOUNDED_ENUM as controls.
