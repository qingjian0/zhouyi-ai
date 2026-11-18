# CPG-EI Empirical-Bayes Held-Out-Family Meta-Learner v1

## Purpose

This experiment tests whether a prior estimated from meta-training teacher families improves finite-grammar few-shot adaptation on disjoint teacher families. It extends the deterministic symbolic selector; it is not a neural meta-learner.

## Protocol and information boundaries

- Teacher families are partitioned into disjoint meta-train, validation, and locked-test groups by `build_heldout_family_protocol`.
- Meta-training episodes expose support labels and development-query labels. These labels are used only to estimate the candidate-rule prior.
- Validation episodes expose support labels to the selector and query labels to the hyperparameter evaluator. Validation query labels select the prior-strength coefficient.
- Locked-test episodes expose only support labels and query states to the selector. Locked query labels remain in the evaluator view and are read only for final metrics.
- Family identities do not cross the three groups. No locked query labels enter prior estimation or alpha selection.

## Empirical-Bayes rule prior

Let the declared finite hypothesis set be \(\mathcal H\), and let \(c_h\) be the fractional count of candidate rule \(h\) among minimum-error candidates inferred independently for each meta-training family/output from its support plus development observations.

With positive smoothing \(\lambda\), estimate:

\[
p(h) = \frac{c_h + \lambda}{\sum_{g\in\mathcal H} c_g + \lambda |\mathcal H|}.
\]

When several candidates have the same minimum meta-training error, their contribution is divided equally. This avoids arbitrary tie-order bias in the prior.

For a held-out episode, let \(e_{support}(h)\) be the candidate's number of mismatches on that episode's support labels. Select:

\[
\hat h = \arg\min_{h\in\mathcal H}
\left[e_{support}(h) - \alpha \log p(h)\right].
\]

The coefficient \(\alpha\) is selected from a fixed grid using validation-family query metrics only. \(\alpha=0\) reproduces the deterministic support-only finite-grammar selector and is retained as a direct baseline.

## Comparisons and reporting

The benchmark reports:

1. Empirical-Bayes selector using the validation-selected \(\alpha\).
2. Deterministic support-only selector (`alpha=0`).
3. Per-output majority predictor from the same support examples.

It reports bit accuracy and exact-state accuracy, plus family-level results, selected alpha, corpus digest, prior digest, and evaluation time. Three independent seeds and support sizes 16/32/64 are used in the full workflow.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_cpg_ei_empirical_bayes_meta_learner.py' -v
python -m prototype.cpg_ei_empirical_bayes_meta_learner \
  --families 1600 \
  --seeds 20261114 20261115 20261116 \
  --support-sizes 16 32 64 \
  --json artifacts/empirical-bayes-meta-results.json
```

## Claim boundary and failure conditions

- The hypothesis set is fixed and finite; the method cannot discover rules outside it.
- The prior reflects the synthetic meta-training family distribution. It may hurt under family-distribution shift.
- A high score does not establish open-world relation discovery, real-world analogy, Yi-Xue understanding, causal discovery, natural-language reasoning, or superiority over neural models.
- If the validation-selected prior does not outperform \(\alpha=0\) on locked test, report the result as a failed or non-transferable prior rather than changing the test protocol.
- Any change to candidate enumeration, data generation, split construction, or alpha grid requires a new exact-head artifact and corpus digest.
