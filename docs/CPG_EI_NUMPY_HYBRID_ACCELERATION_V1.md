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
