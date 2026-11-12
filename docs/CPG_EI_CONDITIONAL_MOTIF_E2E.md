# CPG-EI conditional motif: end-to-end validation

Status: research-only Draft; no default topology change.

## Question

The conditional proposer can rank the three correct four-feature motifs on the
finite GF(2) parity teacher. That result alone does not show that the selected
topology can be consumed by the trainable CPG-EI model and generalize to unseen
states. This experiment closes that gap.

## Protocol

- Generate five deterministic seeds of a six-bit, three-motif GF(2) parity teacher.
- Split independently sampled training and held-out states.
- Rank the 20 possible three-line motifs using training rows only.
- Activate the 12 relation features belonging to the three selected motifs.
- Train the existing six-head CPG-EI transition learner using only training rows.
- Report held-out bit accuracy, exact-state accuracy, support precision/recall,
  exact support recovery, and finite-loss status.
- Do not use held-out targets for proposal ranking, topology selection, or
  parameter fitting.

## Interpretation

This is an end-to-end integration check for one bounded motif family. It is
not evidence of arbitrary-arity structure discovery, open-world induction,
natural-language reasoning, or superiority to Transformer models. The greedy
residual-growth default remains unchanged. A default change would require
matched-compute comparisons, negative controls, broader teacher families, and
a passing full test suite.

## Acceptance

The focused test requires exact recovery of the three known motifs, finite
training losses, held-out bit accuracy of at least 0.90, and exact-state accuracy
of at least 0.70 for its fixed seed. The multi-seed report is diagnostic and
must be interpreted as a distribution, not as a single aggregate claim.
