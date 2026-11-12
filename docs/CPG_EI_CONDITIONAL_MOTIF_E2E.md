# CPG-EI conditional motif: end-to-end validation

Status: research-only Draft; no default topology change.

## Question

The conditional proposer can rank the three correct four-feature motifs on the
finite GF(2) parity teacher. That result alone does not show that the selected
topology can be consumed by the trainable CPG-EI model and generalize to unseen
states. This experiment closes that gap.

## Protocol

- Generate deterministic six-bit, three-motif GF(2) parity teachers.
- Split independently sampled training and held-out states.
- Rank the 20 possible three-line motifs using training rows only.
- Activate the 12 relation features belonging to the three selected motifs.
- Train the existing six-head CPG-EI transition learner using only training rows.
- Sweep full-batch SGD learning rates 0.35, 1.05, 2.1, and 4.2 with 300 and
  600 epochs, across three seeds.
- Report held-out bit accuracy, exact-state accuracy, support precision/recall,
  exact support recovery, and finite-loss status.
- Do not use held-out targets for proposal ranking, topology selection, or
  parameter fitting.

## Initial result and interpretation

The first fixed configuration (seed 11, learning rate 0.35, 300 epochs) recovered
all 12 support features exactly, but reached only 80.21% held-out bit accuracy.
This is a real failure against the original 90% target, and shows that exact
topology recovery does not guarantee that the current optimizer has learned
the parity mapping. The test now records a diagnostic floor rather than
misrepresenting the initial run as converged; the optimizer sweep measures
whether learning rate and duration explain the gap.

This remains a bounded six-line benchmark. It is not evidence of arbitrary-arity
structure discovery, open-world induction, natural-language reasoning, or
superiority to Transformer models. The greedy residual-growth default remains
unchanged. A default change requires matched-compute comparisons, negative
controls, broader teacher families, and passing full project tests.
