# CPG-EI proposal-split SGD versus Adam candidate fitting

## Research question

The oracle-known-support benchmark showed a strong finite-domain optimization advantage for Adam at learning rate 0.1. This experiment asks whether that advantage transfers to the harder bounded candidate-discovery path, where the true support is not supplied to selection.

## Protocol

- Five deterministic seeds: 11, 23, 47, 89, 131.
- Three finite six-bit parity rule families.
- Train/proposal/locked split sizes: 40/12/12.
- Candidate weights are fit only on train examples.
- Candidate groups are ranked only by proposal BCE.
- Locked and alternate-family metrics are report-only.
- Candidate fit optimizers: SGD at 4.2 and Adam at 0.1.
- Candidate-fit epochs: 50, 100, 200.
- Three bounded motif-selection rounds; same candidate universe and acceptance threshold.
- Both optimizers use the same regularization coefficients and corrected mean-head gradient/regularizer normalization.

## Metrics

- Exact support recovery, support precision/recall and selected motif count.
- Proposal BCE and per-round best-candidate proposal improvement, including rejected candidates.
- Locked bit accuracy and alternate-family accuracy after selection.
- Candidate fit count and training passes.

## Leakage controls

The exact support is used only to score recovery after selection. It is not passed to the selector. Locked and alternate-family results never rank candidates or choose the optimizer. The optimizer comparison is a finite synthetic diagnostic, not a generalization claim.

## Interpretation

Adam is expected to improve candidate fitting if its oracle-known-support advantage transfers, but proposal-split ranking may still reject candidates. If Adam improves proposal BCE without improving support recovery, the bottleneck is more likely proposal evidence or score calibration than candidate optimization.

## Claim boundary

This experiment does not establish open-world relation induction, natural-language grounding or production-ready reasoning. A successful result must be confirmed on new rule families and feature dimensions before any default optimizer or selection policy is changed.