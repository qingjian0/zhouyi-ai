# CPG-EI pre-encoded feature cache

## Motivation

The exact-head compute-accounted hybrid run exposed long Python training times. The existing reference learner calls `encode_relations` from `RelationalTransitionModel.train` on every epoch even though each fit's states and support basis are immutable. The optimization here encodes training features once and reuses the same tuples across epochs.

## Correctness contract

- Preserve the reference SGD update order, scalar operations, L2 handling, and loss calculation.
- A one-epoch cached update must produce exactly identical weights and training loss to `RelationalTransitionModel.train(..., epochs=1)`.
- Development checkpoint selection and locked-label isolation remain unchanged.
- The cache is per fit and is discarded after fitting; no cross-split feature statistics are learned.

## Benchmark

The exact-head workflow compares the reference repeated-encoding loop with the cached-feature update on the same generated corpus, seed, family, rows, model initialization, optimizer and epoch count. It reports corpus SHA-256, feature encoding counts, wall time, traced allocation peaks, runtime, and exact weight equality.

This microbenchmark isolates feature construction. It does not claim that gradient computation is faster, nor does it replace the end-to-end CPG-EI benchmark. The full #422 hybrid benchmark remains the authoritative model-quality comparison.

## Claim boundary

This is an implementation-level optimization for the existing finite synthetic Boolean learner. No claim is made about generalization, cross-family transfer, Yi-Xue understanding, causal discovery, language reasoning, or Transformer comparisons.
