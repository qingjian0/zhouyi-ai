# CPG-EI compute-accounted symbolic-support hybrid

## Research question

Can a finite symbolic hypothesis search reduce the feature space needed by a trainable polynomial learner, while retaining most of the trainable learner's predictive performance on exactly the same observations?

This experiment follows the matched symbolic/trainable comparison and the development-loss early-stopping baseline. It does not replace either baseline.

## Fixed benchmark

- Dataset: zhouyi-cpg-ei-mixed-operators-v1.
- Seed: 20261114.
- Eight independent teacher families, eight Boolean inputs, eight outputs.
- 256 states per family; each family has 128 train, 64 development, and 64 locked states.
- The corpus is generated once. All three methods receive the same in-memory corpus and its manifest digest.
- Optimizer: learning rate 0.1, L2 0.0001, maximum 600 epochs, patience 30, minimum development-loss improvement 0.00001.
- Initial weights are zero.

## Compared methods

1. Exhaustive symbolic baseline: enumerate the declared finite operator/support grammar; minimize training error; use development error only to break training ties; evaluate locked states after selection.
2. Full polynomial learner: one multi-output logistic model per family with every non-empty Boolean monomial over the eight inputs (255 monomials plus an intercept), selected by development-loss early stopping.
3. Symbolic-support-constrained hybrid: for each family/output, score the same finite candidates using training labels only. Take every minimum-training-error candidate, form each candidate scope (support plus context index for conditional XOR), and use the union of all non-empty monomial subsets of those scopes as that output's feature basis. Fit one logistic head per output. Development loss selects the checkpoint; locked labels are report-only.

The hybrid does not use teacher manifests or true rules to choose features. It uses only the declared candidate grammar and training observations. The development partition is deliberately excluded from feature selection so it remains available for checkpoint selection.

## Compute accounting

- Candidate hypotheses: number of distinct declared rule descriptions enumerated.
- Candidate truth-table state evaluations: candidate count multiplied by the full input-state count used to precompute each rule mask.
- Candidate-output train-score evaluations: one candidate/train-label score per family and output.
- Development tie-break evaluations: symbolic train-minimizer count evaluated on development states.
- Feature count: non-empty monomials, excluding the intercept; feature columns and coefficients are also reported with the intercept included.
- Gradient feature contributions: optimizer epochs × training rows × output heads × feature columns.
- Wall time: method execution only; common corpus generation is excluded. All methods run with tracemalloc enabled.
- Python allocation memory: peak tracemalloc increase above the method's pre-call Python-heap baseline.
- RSS: one process-wide high-water mark for the whole benchmark, not an isolated per-method RSS measurement. Do not interpret it as per-method memory.

The report binds every result to the corpus SHA-256, seed, dimensions, split sizes, optimizer configuration, Python runtime, and exact workflow commit.

## Leakage and reproducibility checks

- Mutating development and locked labels must not change the hybrid's training-selected feature supports.
- Mutating locked labels must not change the hybrid's selected epochs, development losses, or selected weights.
- Empty training support is rejected.
- The benchmark asserts and reports a single corpus digest for all methods.
- The CI artifact is the authoritative machine-readable measurement; no metric is claimed before the exact-head run completes.

## Interpretation boundary

This is per-family supervised adaptation on a synthetic finite Boolean task. The symbolic baseline searches a declared finite grammar; the hybrid inherits that grammar as an inductive bias. Family labels are reporting strata, not a cross-family transfer split.

The experiment does not establish open-world relation induction, generalization beyond the generator, causal discovery, Yi-Xue understanding, natural-language reasoning, or superiority to Transformer models. Symbolic operator identity and prediction accuracy remain separate metrics because distinct rule descriptions can share a truth function.
