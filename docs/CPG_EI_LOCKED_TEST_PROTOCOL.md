# CPG-EI conditional motif: leakage-safe locked-test protocol

Status: research-only; follows PR #406 and does not change the default learner.

## Why this exists

PR #406's optimizer sweep compared eight configurations on the same held-out
partition. That partition was not used for gradient updates, but its metrics
were inspected to choose the optimizer configuration. Therefore the best
reported score is a model-selection result, not an untouched final test score.

## Protocol

- For each of five deterministic seeds, create disjoint train, development,
  and locked-test samples using separate RNG seeds.
- Generate candidate motifs from training rows only during the development
  sweep.
- Select learning rate and epoch count using aggregate development bit
  accuracy, then development exact-state accuracy.
- Resolve ties deterministically in favor of fewer epochs and then lower
  learning rate.
- Refit the selected configuration on train + development rows.
- Evaluate the refitted model on locked-test rows exactly once, after selection.
- Never pass locked-test rows to candidate proposal, topology selection,
  hyperparameter selection, or parameter fitting.

## Acceptance and claim boundary

The focused test verifies the split contract, exact relation support, finite
losses, and metric bounds. The five-seed benchmark reports locked bit accuracy,
exact-state accuracy, support recovery, and finite-loss status.

This is still a finite six-line GF(2) parity benchmark. It does not establish
open-world relation discovery, arbitrary-arity induction, natural-language
reasoning, or superiority to Transformer models.
