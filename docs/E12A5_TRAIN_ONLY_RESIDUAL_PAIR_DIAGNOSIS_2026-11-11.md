# E12-A5-1 — Train-Only Residual Pair Diagnosis

Status: finite symbolic diagnostic prototype. Source, tests, and this document are committed to a research branch. No test execution or CI success is claimed.

## Research question

Given A3 predictions made without training on the corresponding examples, can the learner identify numeric feature pairs whose relationship is associated with A3's errors, and pass those pairs to A4 as bounded operator-expansion triggers?

## Input contract

Each residual record contains:
- a unique evidence ID;
- a complete numeric feature vector;
- the true binary label;
- A3's binary prediction;
- a model version at prediction time.

Only `prequential` or `out_of_fold` prediction modes are accepted. In-sample residuals are rejected because they can understate generalization errors and distort the diagnosis. The input contains no Gate or Test object; the diagnostic cannot inspect those splits.

This is a necessary but not sufficient provenance contract: the caller must truthfully guarantee that prequential predictions were committed before labels were revealed, or that out-of-fold predictions came from a model that excluded the corresponding fold.

## Diagnosis method

For each numeric feature pair (x, y):
1. Compute `d = abs(x-y)` for each Train residual record.
2. Enumerate thresholds midway between adjacent distinct observed distances.
3. Consider both orientations: high distance predicts residual, or low distance predicts residual.
4. Require minimum support on both sides.
5. Score each split using balanced accuracy against the binary residual target (A3 prediction differs from label).
6. Keep pairs above the configured balanced-accuracy threshold, rank deterministically, and return at most top_k.

Balanced accuracy is used because residual/correct counts may be imbalanced. A score of 0.5 is chance-level for a balanced binary diagnostic; the default threshold is 0.65. This score is a feature-pair association, not a causal attribution.

## A4 handoff

The result includes `counterexample_pairs`, directly consumable as A4's trigger-pair input. The caller should preserve the complete diagnosis object alongside A4 provenance, including model version, prediction mode, selected pair scores, thresholds, and evidence IDs.

A4 currently checks only that trigger pairs are valid schema pairs. The combined pipeline must ensure these pairs came from this Train-only diagnostic and must not allow Gate/Test labels to affect diagnosis or candidate generation.

## Failure and abstention

- In-sample prediction mode: rejected.
- Missing either residual class: rejected; there is no contrast to diagnose.
- Insufficient support on either side: candidate split is skipped.
- No pair reaches the score threshold: `NO_SUPPORTED_PAIR`.
- Invalid numeric values, overflowing pairwise distances, duplicate evidence IDs, invalid thresholds or budgets: rejected.

## Complexity

For F numeric features and N records, pair enumeration is O(F²N). Each pair's distance values are sorted, giving O(F²N log N) worst-case time. The current implementation evaluates all thresholds and stores selected evidence IDs; top_k limits returned results, not candidate enumeration or memory. A production implementation needs explicit pair-generation and threshold-evaluation budgets.

## Tests authored

- recover a synthetic feature pair that perfectly separates A3 residuals;
- reject in-sample predictions;
- reject datasets without both residual classes;
- enforce minimum support;
- confirm Gate/Test are absent from the diagnostic interface;
- preserve evidence and model-version provenance;
- fail closed on bool/non-finite numeric inputs and invalid parameters.

Command: `python -m unittest tests.test_e12a5_residual_pair_diagnosis -v`

No local test execution or CI success is claimed.
