# CPG-EI SGD versus Adam optimizer comparison

## Research question

The known-support optimizer sweep indicates that the current SGD path is highly learning-rate-sensitive after correcting the shared relation-gate gradient. This experiment adds an optional Adam optimizer without changing the default SGD behavior and compares both optimizers with the true relation support supplied.

## Protocol

- Five fixed seeds: 11, 23, 47, 89, 131.
- Three finite six-bit parity families.
- 40 training states; 12 locked states; complete 64-state truth table as a separate finite-domain diagnostic.
- Oracle supplies the true pair/triple support; support discovery is intentionally excluded.
- 800 epochs per configuration.
- SGD learning rates: 2.1, 4.2, 6.0, 12.0. These are six times the earlier 0.35, 0.7, 1.0, 2.0 settings to compensate for the corrected mean-over-six-heads output-weight gradient.
- Adam learning rates: 0.003, 0.01, 0.03, 0.1.
- Both default and search-strength regularization are compared.
- Each model is freshly initialized for every seed/family/optimizer/regularizer/rate combination.

## Leakage control

The only configuration-ranking metric is mean post-update training BCE over the fixed seed/family set. Locked-set accuracy and full-domain accuracy are reported only as diagnostics and are not used to choose an optimizer, learning rate, or regularizer. The benchmark is not an independent confirmation study; any selected configuration must later be evaluated on new seeds and a separately locked split.

## Gradient-objective consistency correction

The exact-head audit found that the six output-head gradients were divided by the
number of training examples, while the shared relation-gate gradient was divided
by the number of examples times six heads. The benchmark objective is mean BCE
over all six heads, so both gradient paths must use the same mean-over-heads
normalization. The output-head gradient now uses `1 / (N * 6)`, with the
existing L2 term applied afterward. A finite-difference regression test checks
an output-head parameter against that exact objective, complementing the
existing shared-gate finite-difference test.

This changes the effective SGD step scale. Learning-rate conclusions from
known-support and candidate-selection sweeps run before this correction must
not be carried forward as directly comparable results. The exact-head
SGD-versus-Adam workflow must be rerun on this corrected implementation before
any optimizer recommendation is made.

## Implementation

- optimizer='sgd' remains the default and preserves the existing update path.
- optimizer='adam' enables bias-corrected first/second moments for both per-head weights and shared relation-gate logits.
- Existing L2, gate-L1, and proximal edge-group-L1 terms remain active under both optimizers.
- Both output-head and shared-gate gradients match the mean-over-six-heads BCE objective, as checked by finite-difference regression tests. The output-head correction reduces the raw SGD gradient by 6×, so the SGD rate grid is rescaled accordingly; prior rate results are not directly comparable.

## Claim boundary

This is a synthetic finite parity diagnostic with oracle-supplied support. It does not measure support discovery, open-world relation induction, natural-language grounding, or general reasoning. The optimizer comparison is CPU microbenchmark evidence for this finite setup only.