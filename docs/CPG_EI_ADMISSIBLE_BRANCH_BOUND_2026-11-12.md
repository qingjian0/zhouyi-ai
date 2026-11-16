# CPG-EI admissible branch-and-bound search — 2026-11-12

## Motivation

The current bounded Beam strategy ranks partial prefixes with their partial score. That score is not an admissible upper bound: a prefix with a weak unary/pairwise score can still become the global optimum after a positive third-order interaction is completed. Beam pruning can therefore discard the true optimum and must fail closed.

The `branch_bound` strategy instead prunes only when a mathematically valid upper bound proves that a branch cannot enter the requested top-k.

## Score decomposition

For role assignment \(x=(x_0,\ldots,x_{R-1})\) and feature dimension \(d\), the current SROK score is a finite sum of unary, pairwise, and third-order terms:

\[
S(x)=
\sum_{r,k} w_{r,k}x_{r,k}
+\sum_{r<s,k}w_{rs,k}x_{r,k}x_{s,k}
+\sum_{r<s<t,k}w_{rst,k}x_{r,k}x_{s,k}x_{t,k}.
\]

Every term is a scalar weight multiplied by a product of one feature coordinate from each role participating in that term.

## Prefix upper bound

Let \(p\) be a prefix assigning the first \(m\) roles. For a score term involving role set \(I\) and feature coordinate \(k\), assigned roles contribute fixed feature values; each unassigned role contributes any value from its corresponding candidate pool.

Let \(P_{I,k}(p)\) be the finite set of all possible products for that term over those choices. Define:

\[
U_{I,k}(p)=
\begin{cases}
w_{I,k}\max P_{I,k}(p), & w_{I,k}\ge 0,\\
w_{I,k}\min P_{I,k}(p), & w_{I,k}<0.
\end{cases}
\]

Then the total prefix bound is:

\[
U(p)=\sum_{I,k}U_{I,k}(p).
\]

For every valid completion \(x\supseteq p\), each individual term in \(S(x)\) is no greater than its corresponding \(U_{I,k}(p)\). Summing these inequalities gives:

\[
S(x)\le U(p).
\]

The implementation obtains each product interval by recursively combining the minimum and maximum feature values for the remaining roles. It maximizes each term independently. This ignores coupling between terms and cross-role distinct-member constraints, so it may be loose, but it cannot make the bound smaller than the best valid completion.

## Exact top-k stopping rule

The search is best-first over prefixes ordered by descending \(U(p)\). Once at least \(k\) complete assignments have been found, let \(s_k\) be the current kth-best complete score and \(U_{\max}\) the largest remaining frontier bound.

Search may stop when the largest frontier score bound is below the kth score:

\[
U_{\max}<s_k.
\]

Equal-score branches require a second, lexicographic bound. For a prefix \(p\), define \(L(p)\) as its assigned node IDs followed by the smallest node ID available in each remaining role pool. Every completion's node-ID tuple is lexicographically greater than or equal to \(L(p)\). The frontier is ordered first by descending \(U(p)\), then by ascending \(L(p)\).

Therefore, when \(U_{\max}=s_k\), search may also stop if the smallest \(L(p)\) among frontier branches with that score bound is greater than or equal to the kth complete assignment's node-ID tuple. Such a branch cannot contain a higher-scoring completion, and any tied completion cannot outrank the current kth result. The implementation uses this tie-aware condition to avoid enumerating large equivalence classes of equal-score assignments while preserving exact deterministic top-k ordering.

For the public prediction API, the internal search retains at least two complete candidates even when `result_limit=1`, because the top-two score margin is required for the existing abstention rule.

If the expansion budget is exhausted before the stopping condition is proved, the result is marked `SEARCH_BUDGET_EXHAUSTED` and abstains. If the stopping condition is proved, the returned top-k ranking is exact relative to the finite candidate pools and current model weights, even when some lower-scoring branches were safely pruned.

## Strategy boundaries

| Strategy | Pruning rule | Completeness guarantee |
|---|---|---|
| `product` | None; enumerate the Cartesian product | Exact if the budget completes |
| `beam` | Heuristic partial-score ranking | Approximate; any pruning causes abstention |
| `branch_bound` | Admissible score upper bound plus lexicographic tie lower bound | Exact top-k if the proof stopping rule completes |

## Initial validation

The first deterministic comparison covered 5 seeds × 3 candidate-pool sizes (3, 5, 8), for 15 comparisons. Branch-bound matched Exact Product's top-5 rankings and abstention outcomes in all cases. A separate exhaustive prefix test verified the upper bound against every completion in a three-role fixture. Pure third-order synergy, equal-score tie handling, and fail-closed budget exhaustion also passed.

The observed ratio of branch-bound prefix extensions to Exact Product complete assignments averaged 0.8196 (range 0.25–1.3333). These counters have different granularities and exclude upper-bound evaluation cost; they are not a wall-clock speedup claim.

## Limitations and next measurements

- The bound is intentionally conservative; independent term maxima can be mutually incompatible and reduce pruning.
- Bound-evaluation CPU time and allocations are not included in `expanded_search_states`.
- Role-pair and role-triple term counts grow combinatorially with role count.
- The result is exact only for the supplied finite candidate pools and current scoring function; it does not validate candidate recall, learned-weight quality, or natural-language grounding.
- A dedicated benchmark must compare wall-clock time, upper-bound evaluations, memory, and exact-ranking agreement under identical candidate pools and a locked seed set.


## Tie-aware pruning follow-up

The first timing sweep exposed a pathological case: pure third-order synergy can create thousands of equal-scoring decoy assignments. Preserving deterministic Top-K tie order by enumerating every tie is correct but unnecessarily expensive.

The tie-aware refinement stores a lexicographic lower bound for every partial prefix. When the best remaining score upper bound equals the current kth score, the search can stop if the smallest possible completion tuple is not earlier than the kth tuple. A dedicated all-zero-score test compares the exact Top-5 and abstention reason while requiring fewer than all 512 product assignments to be expanded.

This does not relax the score upper-bound proof or tie ordering. It only proves that remaining tied completions cannot outrank the already selected kth result.
