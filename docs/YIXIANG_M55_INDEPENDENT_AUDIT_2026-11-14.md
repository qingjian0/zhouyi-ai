# M55 independent audit: leakage, sample accounting, and artifact integrity

Date: 2026-11-14  
Audited commit: `5e870bc58d512e8a5c7740d3720940f94eedba37`  
Audited PR: #481  
Study workflow run: `43585634551` (completed successfully)  
Unit/integration workflow run: `43585634550` (completed successfully)  
Artifact: `m55-statistical-study-4163ead76b6bbbd5318de3ac2486583fe4bad9fb` (artifact ID `14110121695`)

## Executive finding

The M55 implementation and its 50-seed study execute successfully, but the current study is **not yet a valid fair comparison**. A successful CI run establishes execution and test consistency; it does not establish that the compared adapters were denied evaluator information. The independent audit found a direct oracle-cardinality leak and several reporting/generator defects. Therefore, the current M55 effect estimates and significance counts must be treated as diagnostic only and must not support a method-superiority claim.

## Reproduced study scope

The downloaded workflow artifact contains 5,400 method records:

- 12 synthetic scenarios;
- 3 generated sample sizes (120, 240, 480);
- 50 seeds (1000–1049);
- 3 adapters (random, marginal correlation, target-local PC-style).

This is a complete execution of the declared matrix at the audited commit. It is materially more than the earlier smoke test, but the following validity defects affect interpretation.

## Findings

### A1 — Evaluator-truth cardinality leaks into two candidate methods (critical)

In `prototype/yixiang_experiments_m55.py`, the runner computes:

```python
parent_count = max(1, len(parents))
```

Here, `parents` is the generator's evaluator-truth direct-parent set. The runner then passes this value into both:

- `random_baseline(..., parent_count=parent_count)`;
- `correlation_screen_baseline(..., parent_count=parent_count)`.

The M54 adapter contract says evaluator truth is withheld from adapters. However, these two adapters are explicitly told the true parent-set cardinality (except the empty-set special case, which is forced to one). This is an oracle leak. The PC-style adapter does not receive the same cardinality parameter, so the comparison is not budget/sparsity matched.

**Consequence:** current correlation and random F1 scores are conditional on information unavailable to a real learner. Paired p-values, confidence intervals, and multiplicity corrections cannot repair this design leak.

**Required correction:**

1. Remove all use of `len(parents)` from candidate-side adapter construction.
2. Select thresholds/hyperparameters using only training data and a predeclared rule, or a separate validation split with a frozen selection protocol.
3. If a fixed-cardinality baseline is retained, set its cardinality as a declared protocol constant or select it without evaluator truth; report its restricted scope explicitly.
4. Add a regression test that changes evaluator truth while keeping agent-facing observations fixed and verifies that each adapter invocation/context is unchanged.
5. Keep evaluator truth available only to the post-proposal scoring path.

### A2 — Reported sample size is total generated N, not training N (high)

The runner generates `n` rows, then assigns:

- train: `int(n * 0.70)`;
- validation: next 15%;
- test: remainder.

However, each record stores `"sample_size": n`. Thus the declared sizes 120, 240, 480 correspond to only 84, 168, and 336 training observations. The report currently labels total generated rows as sample size without exposing the effective training count.

**Required correction:** record both `total_sample_size` and `train_sample_size` in every raw record and summary. Prefer making the CLI parameter explicitly denote the training sample size, then generate additional disjoint validation/test observations, or rename the existing parameter and all report labels to `total_sample_size`. Do not silently reinterpret the historical run.

### A3 — Raw “JSONL” artifact is not newline-delimited JSON (high)

The writer in `prototype/yixiang_m55_study.py` appends the literal two-character sequence `\\n` rather than a physical newline between JSON records. The downloaded `m55_raw_records.jsonl` is consequently one physical line containing backslash-n separators. Standard JSONL readers cannot consume it as JSONL.

**Required correction:** write an actual newline character after each serialized record; add a test that reads the output line-by-line with `json.loads`, verifies exactly one record per physical line, and checks the expected record count.

### A4 — Hidden regime in mechanism-heterogeneity scenario is encoded by row order (high)

The `mechanism_heterogeneity` generator alternates the sign of the mechanism using `len(rows) % 2`. The resulting regime is not independently randomized. Since rows also expose sequential `unit_id`, the regime is perfectly recoverable from row order/identifier by any adapter that inspects the full row object, even though the regime is described as hidden.

**Required correction:** sample regime assignment independently from unit IDs using a separate deterministic RNG stream; do not expose the regime in agent-facing rows for the hidden-regime condition. Preserve it only in evaluator-side metadata. Add a test that checks regime assignment is not deterministically recoverable from row index/unit ID and that the evaluator-only regime field is absent from agent-facing observations.

### A5 — Sign-flip inference assumptions need an explicit gate (medium)

The paired sign-flip test is exact only under an appropriate exchangeability/symmetry or sharp-null randomization justification. The method labels were not randomized in the study. A sign-flip p-value should therefore not be presented as assumption-free evidence about a mean difference.

**Required correction:** document the precise null and exchangeability assumptions; add a robust paired effect interval and a sensitivity analysis (for example, paired sign test for a zero-median null, alongside the paired bootstrap mean interval). Keep Holm as the confirmatory family-wise correction. Treat BH as exploratory unless its dependence assumptions are justified.

### A6 — CI scope and scientific scope must remain distinct (medium)

Both exact-head workflows passed. The dedicated study produced the full declared synthetic matrix and uploaded an artifact. These facts establish execution, not external validity, causal identification, or superiority over Transformers/SCM learners/Zhouyi agents. No Transformer, SCM learner, or actual Zhouyi agent was included among the three executable adapters.

## Re-analysis status

The artifact was independently downloaded and inspected. It contains 5,400 records and 108 scenario × sample-size × method summary cells. The observed estimates are not promoted as scientific conclusions because A1 directly invalidates the fairness premise, while A2–A5 affect interpretation, reproducibility, or scenario validity.

Do not quote the existing Holm/BH significance counts as evidence that PC-style, correlation, or any Zhouyi method is superior. Re-run the corrected protocol with a new version identifier and preserve the old artifact as a superseded historical run.

## Required M55.1 repair sequence

1. Fix oracle-cardinality leakage.
2. Correct training/total sample accounting.
3. Fix JSONL serialization and artifact reader test.
4. Randomize hidden regime independently of row order and isolate evaluator metadata.
5. Clarify sign-flip assumptions and add a median-based sensitivity test.
6. Re-run the complete 12-scenario × 3-size × 50-seed matrix.
7. Recompute paired intervals and multiplicity-adjusted tests from the corrected raw records.
8. Have an independent reviewer inspect the generator semantics and adapter information boundary.

## Research boundary

This audit does not establish that the PC-style method is poor or that correlation screening is better. It establishes that the current comparison gives two methods evaluator-derived sparsity information and that several artifacts/scenario details need correction before inference is trustworthy.

The next core yixiang research phase (autonomous observation → feature selection → class formation → relation-preserving transfer → counterexample-driven revision) should be built on the repaired benchmark, not on the current contaminated M55 comparison.
