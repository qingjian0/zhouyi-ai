# CPG-EI vectorized optimizer: parity and performance validation

## Motivation

The scalar early-stopping path repeatedly called `RelationalTransitionModel.train(..., epochs=1)`. That revalidated every row and rebuilt the same Boolean monomial feature vectors on every epoch, then performed nested Python loops over examples, output heads, and features.

The vectorized path encodes train and development features once per fit, converts them to float64 matrices, and uses matrix multiplication for logits and batch gradients. It preserves the scalar objective:
- binary cross-entropy;
- mean gradient over training rows;
- L2 penalty on non-bias coefficients only;
- same learning rate and update order;
- development-loss checkpoint selection and patience rule;
- locked rows remain report-only.

The scalar implementation remains available as `fit_with_early_stopping_scalar` and the runtime fallback when NumPy is not installed. The default path selects the NumPy implementation when available.

## Reproducibility

- CI pins NumPy 2.3.5 and sets BLAS/OpenMP thread counts to one.
- Both implementations consume the same generated corpus and per-family split.
- The parity benchmark reports exact best-epoch agreement, max absolute differences in train/development/locked bit and exact-state metrics, and best-development-loss delta.
- The full performance run uses seed 20261114, eight families, eight inputs, eight outputs, 128/64/64 per-family train/development/locked states, 600 max epochs, patience 30, learning rate 0.1, L2 0.0001, and zero initialization.
- Wall time excludes common corpus generation.

## Claim boundary

This is an implementation-level optimization of the same finite synthetic Boolean learner. It does not add a new learning algorithm or establish improved reasoning/generalization. Numerical parity and speed must be confirmed by the exact-head CI artifact before any performance claim is made.
