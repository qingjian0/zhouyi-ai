# E12-A3 Preliminary 20-Seed Benchmark Audit

Date: 2026-11-11  
Source: GitHub Actions run #374, `research/e12a3-proposer-competition-2026-11-11`  
Status: preliminary synthetic result; not a general performance claim.

## 1. Protocol observed

- Tasks: THRESHOLD and PAIRWISE_DIFFERENCE.
- Seeds: 20 per task, 40 total episodes.
- Per-method budget: 64 proposal slots per episode.
- Support: 45 examples.
- Gate: 23 examples.
- Locked Test: 22 examples.
- Candidate selection: exact Support consistency, then Gate ranking.
- Locked Test: one-time evaluator-side scoring after selection.

The benchmark reports proposal-slot budgets. It does not yet equalize CPU operations, wall-clock time, or the cost of evaluating different expression families.

## 2. Aggregate results

Values below are copied from the CI JSON output.

| Method | Coverage | Mean Locked-Test accuracy when selected | Effective success rate* |
|---|---:|---:|---:|
| STAT | 0.50 | 1.0000 | 0.5000 |
| RELATIONAL | 0.50 | 0.9932 | 0.4966 |
| RANDOM | 0.45 | 1.0000 | 0.4500 |
| EXHAUSTIVE | 1.00 | 0.9966 | 0.9966 |
| PORTFOLIO | 0.85 | 0.9960 | 0.8466 |

*Effective success rate is coverage multiplied by conditional mean Locked-Test accuracy. It is a useful descriptive measure for this benchmark, not a universal metric.

Mean Support-consistent candidate counts:
- STAT: 0.50
- RELATIONAL: 0.50
- RANDOM: 0.45
- EXHAUSTIVE: 1.00
- PORTFOLIO: 1.35

## 3. Preliminary interpretation

1. EXHAUSTIVE is the clear winner on these two small synthetic tasks: it has full coverage and approximately 99.66% conditional Test accuracy.
2. PORTFOLIO improves coverage over individual STAT, RELATIONAL, and RANDOM proposers, but does not beat EXHAUSTIVE. Its effective success rate is approximately 0.8466 versus 0.9966 for EXHAUSTIVE.
3. The portfolio's higher mean number of Support-consistent candidates (1.35) does not translate into higher success. Candidate count is not utility.
4. The high conditional accuracies are partly a consequence of strict Support screening and Gate selection. They must not be reported without coverage.
5. This benchmark does not test the central sparse A+C+E composition task. It tests simple threshold and pairwise-difference predicates. It therefore does not validate the direct A3 composition engine.

## 4. Why this is not evidence against all portfolios

The current portfolio distributes 64 proposal slots across four families. On a small hand-specified DSL, exhaustive enumeration can cover the useful candidate more reliably. This is expected when the hypothesis space is small enough to search exhaustively.

Portfolio methods may become useful when:
- the DSL is larger or incomplete;
- proposers have heterogeneous discovery strengths;
- candidate evaluation costs differ;
- the useful expression is not near the beginning of the exhaustive ordering;
- held-out world families require broader proposal diversity.

These conditions must be explicitly tested rather than assumed.

## 5. Benchmark limitations and possible confounds

- Only two simple synthetic task families are included.
- All proposal families share a small hand-specified predicate grammar.
- Proposal slots are matched, but actual compute and runtime are not.
- The benchmark's exhaustive pool is assembled from the same statistical and relational proposal mechanisms; this is a bounded grammar baseline, not a universal oracle.
- The current portfolio scheduler is round-robin and does not adapt based on measured utility.
- The test set is small (22 rows per episode); confidence intervals should be reported at the independent world/seed level.
- No Yijing-inspired prior is involved.
- No direct sparse composition candidate is evaluated.

## 6. Required next benchmark

Add at least four families:
1. Sparse triple composition: target A AND C AND E, with B,D irrelevant.
2. Nested composition: (A AND C) OR (B AND E).
3. Unidentifiable task: two structures are equivalent under all permitted observations.
4. DSL-misspecification task: the target operator is unavailable to every proposer.

Compare:
- direct sparse composition engine;
- STAT only;
- RELATIONAL only;
- RANDOM only;
- EXHAUSTIVE tiny-DSL oracle;
- portfolio without COMPOSITIONAL;
- portfolio with COMPOSITIONAL;
- a matched decision-tree baseline.

Report:
- coverage;
- conditional Test accuracy;
- effective success rate;
- false acceptance;
- ambiguity/abstention calibration;
- candidate count;
- measured predicate evaluations;
- CPU time and wall-clock time;
- world-level confidence intervals.

## 7. Decision

Do not tune the portfolio to this 20-seed result and do not claim it is better. Preserve this as a negative/diagnostic baseline: under the current small DSL and slot budget, exhaustive search dominates the portfolio.

The next decisive experiment must include the sparse non-contiguous composition task that motivated E12-A3. Only then can the direct composition engine and multi-proposer portfolio be compared on the actual research objective.
