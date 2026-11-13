# CPG-EI NumPy hybrid acceleration

## Purpose

The Python reference hybrid in PR #422 performs full-batch gradient descent with repeated Python-level loops over examples, outputs, and features. This branch adds an optional NumPy float64 backend that caches train/development feature matrices once and uses matrix operations for logits and gradients.

## Numerical contract

- Same model, supports, train/development splits, zero initialization, full-batch gradient descent, learning rate, L2 penalty (excluding intercept), development BCE checkpoint selection, patience, and min-delta.
- NumPy is optional; the dependency-free Python backend remains the default.
- The accelerated backend must match a single reference Python gradient step to 1e-12 and match selected epoch/predictions on a deterministic early-stopping fixture.
- Feature matrices are encoded once per split; gradient matrix work remains proportional to epochs × examples × features.

## Fixed full benchmark

Uses the exact eight-family corpus from PR #422 (seed 20261114; expected corpus digest is checked). The report compares accuracy and feature counts directly against the parent PR's exact-head Python result. Historical wall time is disclosed as a separate-run measurement, not a paired benchmark; no hard speedup claim is made from that comparison.

## Scope boundary

This is an implementation-performance optimization for the existing synthetic finite Boolean benchmark. It does not improve the hypothesis grammar, cross-family transfer, open-world relation induction, Yi-Xue or natural-language reasoning. NumPy is not made a mandatory project dependency.


## Exact-head result

The fixed-corpus workflow completed successfully on the exact PR head. Corpus digest remained `f56948816847a587c194931588027f97d99a4541644932b81f2df26e7b381c15`.

| Metric | Python reference (#422) | NumPy backend |
|---|---:|---:|
| Locked bit accuracy | 90.0391% | 90.0391% |
| Locked exact-state accuracy | 41.2109% | 41.2109% |
| Mean features per output | 27.375 | 27.375 |
| Total optimizer epochs | 33,266 | 33,266 |
| Wall time | 711.25 s | 30.70 s |

The measured timing ratio is approximately 23.2×, but this is a comparison of separate CI runs, not a paired same-process timing; it is indicative rather than a controlled speedup claim.

The feature matrix encoding accounting changed from repeated per-epoch work to one train/development encoding per output head:
- Training feature encodings: 106,772,480 → 232,448.
- Development feature encodings: 53,502,464 → 116,224.
- Gradient feature contributions remain 106,772,480 because the same number of optimizer updates are performed.

The exact-head NumPy workflow passed numerical parity tests and produced the archived full benchmark artifact. The optional dependency is installed only in this workflow; the reference Python path remains the default.


## Parallel-branch reconciliation

The repository also has related Draft experiments that must be compared before any merge:
- PR #423 (`research/cpg-ei-preencoded-feature-cache-v1-2026-11-13`) caches scalar feature encodings and preserves the reference update order.
- PR #427 (`research/cpg-ei-vectorized-optimizer-v1-2026-11-13`) adds an integrated scalar/vectorized optimizer path and a full-basis paired benchmark.
- PR #429 is intentionally stacked on this branch and adds a same-process paired Python/NumPy benchmark specifically for the symbolic-support hybrid.

These branches overlap in optimizer implementation. Do not merge #423, #426, and #427 as independent implementations without reconciling the canonical backend API and numerical contract. #429's paired hybrid measurement is distinct in scope from #427's full-polynomial learner comparison. Preserve one scalar reference, one vectorized implementation, and one authoritative paired hybrid benchmark after review.
