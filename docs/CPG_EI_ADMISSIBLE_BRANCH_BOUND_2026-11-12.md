# CPG-EI admissible branch-and-bound search — 2026-11-12

## Motivation

The current bounded Beam strategy ranks partial prefixes with their partial score. That score is not an admissible upper bound: a prefix with a weak unary/pairwise score can still become the global optimum after a positive third-order interaction is completed. Beam pruning can therefore discard the true optimum and must fail closed.

The `branch_bound` strategy instead prunes only when a mathematically valid upper bound proves that a branch cannot enter the requested top-k.

## Score decomposition

For role assignment (x=(x_0,\ldots,x_{R-1})) and feature dimension \\(d\\), the current SROK score is a finite sum of unary, pairwise, and third-order terms:

\[
S(x)=
\sum_{r,k} w_{r,k}x_{r,k}
+\sum_{r<s,k}w_{rs,k}x_{r,k}x_{s,k}
+\sum_{r<s<t,k}w_{rst,k}x_{r,k}x_{s,k}x_{t,k}.
\]

Every term is a scalar weight multiplied by a product of one feature coordinate from each role participating in that term.

## Prefix upper bound

Let \\(p\\) be a prefix assigning the first \\(m\\) roles. For a score term involving role set \\(I\\) and feature coordinate \\(k\\), assigned roles contribute fixed feature values; each unassigned role contributes any value from its corresponding candidate pool.

Let (P_{I,k}\\(p\\)) be the finite set of all possible products for that term over those choices. Define:

\[
U_{I,k}\\(p\\)=
\begin{cases}
w_{I,k}\max P_{I,k}\\(p\\), & w_{I,k}\ge 0,\\
w_{I,k}\min P_{I,k}\\(p\\), & w_{I,k}<0.
\end{cases}
\]

Then the total prefix bound is:

\[
U\\(p\\)=\sum_{I,k}U_{I,k}\\(p\\).
\]

For every valid completion (x\supseteq p), each individual term in \\(S(x)\\) is no greater than its corresponding (U_{I,k}\\(p\\)). Summing these inequalities gives:

\[
S(x)\le U\\(p\\).
\]

The implementation obtains each product interval by recursively combining the minimum and maximum feature values for the remaining roles. It maximizes each term independently. This ignores coupling between terms and cross-role distinct-member constraints, so it may be loose, but it cannot make the bound smaller than the best valid completion.

## Exact top-k stopping rule

The search is best-first over prefixes ordered by descending (U\\(p\\)). Once at least \\(k\\) complete assignments have been found, let \\(s_k\\) be the current kth-best complete score and \\(U_{max}\\) the largest remaining frontier bound.

Search may stop only when:

\[
U_{max}<s_k.
\]

The comparison is deliberately strict. If a remaining branch has a bound equal to \\(s_k\\), it may contain a tied candidate with a lexicographically earlier role binding, so it must still be explored to preserve deterministic ordering.

For the public prediction API, the internal search retains at least two complete candidates even when `result_limit=1`, because the top-two score margin is required for the existing abstention rule.

If the expansion budget is exhausted before the stopping condition is proved, the result is marked `SEARCH_BUDGET_EXHAUSTED` and abstains. If the stopping condition is proved, the returned top-k ranking is exact relative to the finite candidate pools and current model weights, even when some lower-scoring branches were safely pruned.

## Strategy boundaries

| Strategy | Pruning rule | Completeness guarantee |
|---|---|---|
| `product` | None; enumerate the Cartesian product | Exact if the budget completes |
| `beam` | Heuristic partial-score ranking | Approximate; any pruning causes abstention |
| `branch_bound` | Admissible score upper bound | Exact top-k if the proof stopping rule completes |

## Initial validation

The first deterministic comparison covered 5 seeds × 3 candidate-pool sizes (3, 5, 8), for 15 comparisons. Branch-bound matched Exact Product's top-5 rankings and abstention outcomes in all cases. A separate exhaustive prefix test verified the upper bound against every completion in a three-role fixture. Pure third-order synergy, equal-score tie handling, and fail-closed budget exhaustion also passed.

The observed ratio of branch-bound prefix extensions to Exact Product complete assignments averaged 0.8196 (range 0.25–1.3333). These counters have different granularities and exclude upper-bound evaluation cost; they are not a wall-clock speedup claim.

## Limitations and next measurements

- The bound is intentionally conservative; independent term maxima can be mutually incompatible and reduce pruning.
- Bound-evaluation CPU time and allocations are not included in `expanded_search_states`.
- Role-pair and role-triple term counts grow combinatorially with role count.
- The result is exact only for the supplied finite candidate pools and current scoring function; it does not validate candidate recall, learned-weight quality, or natural-language grounding.
- A dedicated benchmark must compare wall-clock time, upper-bound evaluations, memory, and exact-ranking agreement under identical candidate pools and a locked seed set.
