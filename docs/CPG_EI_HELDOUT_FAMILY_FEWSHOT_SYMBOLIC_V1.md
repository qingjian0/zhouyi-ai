# CPG-EI Held-Out-Family Few-Shot Symbolic Baseline v1

## Purpose

Evaluate whether the declared finite Boolean operator grammar can infer rules
from a small labeled support set on teacher families that were never used in
meta-training. This is a generic symbolic adaptation baseline, not a learned
meta-model.

## Selection protocol

For every output rule, enumerate the declared finite hypothesis grammar and
select the candidate with minimum error on support states only. Ties are resolved
by deterministic candidate order. Query labels are accessed only after selection
through the separate evaluator view.

The baseline is compared with a per-output majority predictor using exactly the
same support examples.

## Evaluation

- Teacher-family train/validation/test groups are disjoint.
- Validation/test support is drawn from within-family train states.
- Validation queries use development states; final test queries use locked states.
- Support-size conditions 16, 32, and 64 are nested for each fixed seed.
- Report query bit accuracy, exact-state accuracy, median and worst-family
  performance, candidate ambiguity, and selection digests.
- Three seeds on the 1,600-family corpus are used by the CI workflow.

## Interpretation

A successful result would establish only finite-grammar few-shot family transfer
under the generated teacher distribution. It would not establish a neural
meta-learning capability, zero-shot transfer, arbitrary relation induction,
Yi-Xue understanding, natural-language reasoning, or Transformer superiority.
