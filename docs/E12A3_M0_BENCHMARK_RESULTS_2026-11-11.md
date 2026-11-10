# E12-A3-M0 Equal-Budget Benchmark Results

Date: 2026-11-11  
Benchmark commit: `55cd2ca7fc4d72e729df83fc3003398c09295be1`  
GitHub Actions run: `42870394169` — full repository workflow passed  
Protocol: 20 seeds per task × 2 tasks = 40 episodes; exactly 31 proposal slots per method per episode.

## 1. Protocol

Tasks:
- THRESHOLD: infer a unary numeric threshold rule.
- PAIRWISE_DIFFERENCE: infer a two-feature difference threshold.

For each episode:
1. The evaluator creates disjoint Support, Gate, and Locked Test partitions.
2. Proposal families receive Support only. Current proposal generators are label-invariant.
3. Exact Support consistency screens candidates.
4. Gate accuracy selects one candidate, with deterministic canonical-expression tie-breaking.
5. Locked Test is evaluated once after selection; it is never passed to the learner or selector.

Compared methods:
- STAT
- RELATIONAL
- RANDOM
- BOUNDED_ENUM (finite grammar enumeration control)
- PORTFOLIO (round-robin over STAT, RELATIONAL, RANDOM; BOUNDED_ENUM is excluded because it overlaps the other proposal grammars)

Every method consumed exactly 31 proposal slots in all 40 episodes. Candidate order is seeded and reproducible to avoid lexical-prefix bias.

## 2. Results

| Method | Selection coverage | Mean Locked Test accuracy, conditional on selection | Mean Gate accuracy, conditional on selection |
|---|---:|---:|---:|
| STAT | 15.0% | 100.00% | 100.00% |
| RELATIONAL | 42.5% | 99.20% | 99.74% |
| RANDOM | 25.0% | 100.00% | 100.00% |
| BOUNDED_ENUM | 35.0% | 99.03% | 99.69% |
| PORTFOLIO | 27.5% | 98.76% | 99.60% |

Selection coverage means the proportion of episodes in which at least one candidate survived exact Support screening and a candidate was selected using Gate. It is not unconditional accuracy. The conditional accuracy figures exclude abstention episodes and must not be interpreted without coverage.

## 3. Interpretation

The current equal-share round-robin portfolio does **not** demonstrate an advantage.

- RELATIONAL has the highest selection coverage at 42.5%.
- BOUNDED_ENUM reaches 35.0%.
- PORTFOLIO reaches 27.5%, below both RELATIONAL and BOUNDED_ENUM.
- Conditional test accuracy is high for all methods, but coverage is low and the benchmark contains only two clean synthetic task families.

This is a useful negative result: adding proposer diversity and splitting the budget equally can reduce the chance that a specialist receives enough candidate slots to find the relevant rule.

The result rejects the simplistic hypothesis that a fixed equal-share portfolio is automatically better than its best specialist.

## 4. What this experiment does not establish

- It does not match CPU operations or wall-clock cost; only proposal slots are matched.
- It does not test noisy labels, missing features, distribution shift, or unseen DSL operators.
- It does not test sparse Boolean composition such as A+C+E; that is a separate composition-engine track.
- It does not compare against a decision tree or a learned allocator.
- It does not establish any advantage for CPG-EI or Yijing-inspired priors.
- No confidence intervals are reported yet; 20 seeds per task are preliminary.

## 5. Next experiments

1. Deduplicate identical canonical expressions across proposer families while retaining all source-family provenance.
2. Replace equal-share round-robin with a budgeted adaptive allocator, with a fixed exploration floor.
3. Use a development Gate for allocation and a separate final Gate/Locked Test for unbiased evaluation.
4. Add task-family shifts, noisy observations, correlated distractors, and DSL-misspecification worlds.
5. Add the sparse composition engine as a separate proposer family only after its dependencies and evaluation costs are charged to the same global budget.
6. Compare fixed allocation, UCB/racing, novelty-aware allocation, and an exact small-instance oracle.

## 6. Conclusion

The current prototype proves that the proposer interfaces, exact slot accounting, reproducible benchmark, Support/Gate/Test split, and CI execution work on the declared synthetic tasks. It does not prove that a multi-proposer portfolio is more effective.

The next research target is **adaptive resource allocation under candidate redundancy and task uncertainty**, not simply adding more proposer families.
