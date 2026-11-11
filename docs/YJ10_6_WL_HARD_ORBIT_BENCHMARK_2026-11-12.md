# YJ-10.6: WL-hard orbit benchmark

## Purpose

Establish a small exact benchmark where bounded 1-WL color refinement merges vertices that are not in the same exact automorphism orbit.

## Benchmark pair

Both cases contain seven vertices, seven undirected edges, and degree two at every vertex:
- C7: one seven-cycle.
- C3 disjoint-union C4: a triangle plus a separate four-cycle.

The candidate bijection count is 7! = 5,040, within the explicit exact-oracle budget.

## Expected structural result

- 1-WL assigns one color class of size seven in both cases.
- C7 has automorphism group order 14 and one exact vertex orbit of size seven.
- C3 disjoint-union C4 has automorphism group order 48 and two exact vertex orbits of sizes three and four.
- On the disjoint-union case, the 1-WL partition creates 12 pairwise false merges, with pairwise precision 9/21 and recall 1.0.

## Interpretation

This demonstrates a specific limitation of the current 1-WL role-color baseline: equal local refinement colors do not imply membership in the same automorphism orbit. The exact oracle provides a finite-structure ground truth under the declared undirected-edge contract.

This is not evidence that WL-hard cases have been solved in general, and it does not establish semantic roles, causal structure, or real-world OOD generalization. The current benchmark is pairwise (arity two); higher-order CFI-style hypergraph families and matched k-WL baselines remain future work.

## Budget and reproducibility

- Exact candidate bijections: 5,040 per case.
- Relation policy: explicit UNORDERED.
- Stable synthetic node/edge construction.
- Exceeding the configured exact-search budget fails closed; no sampling is presented as exact.
