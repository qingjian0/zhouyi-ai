# CPG-EI discovery optimizer comparison

This experiment tests whether optimizer improvements observed with oracle-known
support transfer to actual bounded motif selection.

## Protocol

- Five fixed seeds and three six-bit parity rule families.
- Train/proposal/locked partitions: 40/12/12, disjoint per seed.
- No oracle support is supplied to the discovery model.
- Paired SGD/Adam configurations: SGD 1.0 and 2.0; Adam 0.03 and 0.1.
- 50 epochs per candidate, at most three selected motifs.
- Both independent proposal-split ranking and legacy train-ranked selection.
- Locked and alternate-family metrics are report-only.

## Interpretation boundary

This is a finite synthetic diagnostic. It measures whether optimizer choice
changes support recovery in this specific bounded search space; it does not
establish open-ended relation induction, natural-language reasoning, or
production readiness. The known-support optimizer results are calibration
evidence only, not a substitute for this non-oracle experiment.
