# E12-A3-M0.1 Cross-Family Deduplication Results

Date: 2026-11-11  
Commit: `1b22906652faf4c3279c5744a3617b6732b12997`  
GitHub Actions run: `42871279195` — full repository workflow passed  
Protocol: same 20-seed × 2-task benchmark, 40 episodes, exactly 31 proposal slots per method.

## 1. Change under test

Compared with M0, the portfolio now canonicalizes candidates across STAT, RELATIONAL, and RANDOM before allocation.

- Syntactically identical expressions are evaluated once.
- The representative proposal retains all contributing proposer-family IDs in `supporting_families`.
- BOUNDED_ENUM remains a separate control and is not included in the portfolio.
- The benchmark enforces exact slot consumption and fails if a method cannot fill its declared budget.

The mean raw portfolio pool contained 155.0 proposals, of which 52.95 were duplicate expressions on average. The mean unique pool contained 102.05 expressions.

## 2. Results

| Method | Selection coverage | Mean Locked Test accuracy, conditional on selection |
|---|---:|---:|
| STAT | 15.0% | 100.00% |
| RELATIONAL | 42.5% | 99.20% |
| RANDOM | 25.0% | 100.00% |
| BOUNDED_ENUM | 35.0% | 99.03% |
| PORTFOLIO + dedup | 17.5% | 100.00% |

All methods consumed exactly 31 candidate slots in every episode.

Portfolio selection provenance among the seven selected episodes:
- STAT primary: 2
- RELATIONAL primary: 5
- RANDOM primary: 0

## 3. Interpretation

Deduplication reduces repeated evaluation, but it does not automatically improve a fixed round-robin portfolio.

The portfolio's selection coverage fell from 27.5% in the M0 pre-dedup baseline to 17.5% after deduplication. This does **not** prove deduplication is intrinsically harmful. It shows that the existing allocator is sensitive to how shared candidates are assigned to proposer queues and how the remaining budget is split.

The current deterministic representative-owner policy assigns a shared expression to one family queue while retaining provenance from all sources. This is auditable but not necessarily the best allocation policy.

The key conclusion remains:
- RELATIONAL is the strongest specialist on these two task families.
- BOUNDED_ENUM is a strong finite-grammar control.
- Neither equal-share nor current deduplicated round-robin portfolio demonstrates a benefit.

## 4. Next correction

Do not revert deduplication. Instead:
1. Treat a shared expression as one candidate with multi-family provenance.
2. Avoid charging or crediting the same expression multiple times.
3. Allocate the evaluation slot based on expected marginal utility, not lexical owner.
4. Use a shared candidate queue or cost-sharing attribution for multi-source proposals.
5. Add an exploration floor and adaptive reward updates.
6. Protect Gate-Final and Locked Test from allocator feedback.

This motivates E12-A3-M1 adaptive budget allocation.
