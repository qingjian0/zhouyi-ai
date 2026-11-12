# CPG-EI SGD versus Adam optimizer comparison

## Research question

The known-support optimizer sweep indicates that the current SGD path is highly learning-rate-sensitive after correcting the shared relation-gate gradient. This experiment adds an optional Adam optimizer without changing the default SGD behavior and compares both optimizers with the true relation support supplied.

## Protocol

- Five fixed seeds: 11, 23, 47, 89, 131.
- Three finite six-bit parity families.
- 40 training states; 12 locked states; complete 64-state truth table as a separate finite-domain diagnostic.
- Oracle supplies the true pair/triple support; support discovery is intentionally excluded.
- 800 epochs per configuration.
- SGD learning rates: 0.35, 0.7, 1.0.
- Adam learning rates: 0.003, 0.01, 0.03, 0.1.
- Both default and search-strength regularization are compared.
- Each model is freshly initialized for every seed/family/optimizer/regularizer/rate combination.

## Leakage control

The only configuration-ranking metric is mean post-update training BCE over the fixed seed/family set. Locked-set accuracy and full-domain accuracy are reported only as diagnostics and are not used to choose an optimizer, learning rate, or regularizer. The benchmark is not an independent confirmation study; any selected configuration must later be evaluated on new seeds and a separately locked split.

## Implementation

- optimizer='sgd' remains the default and preserves the existing update path.
- optimizer='adam' enables bias-corrected first/second moments for both per-head weights and shared relation-gate logits.
- Existing L2, gate-L1, and proximal edge-group-L1 terms remain active under both optimizers.
- The shared gate gradient continues to match the mean-over-six-heads BCE objective, as checked by the existing finite-difference regression test.

## Claim boundary

This is a synthetic finite parity diagnostic with oracle-supplied support. It does not measure support discovery, open-world relation induction, natural-language grounding, or general reasoning. The optimizer comparison is CPU microbenchmark evidence for this finite setup only.