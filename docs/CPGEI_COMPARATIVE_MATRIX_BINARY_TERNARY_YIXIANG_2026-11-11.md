# CPG-EI Comparative Experiment Matrix: Binary, Ternary and Yixiang Priors

Date: 2026-11-11  
Status: preregistration candidate; no result claimed  
Branch: feature/experiment-matrix-p1-2026-11-11

## 1. Research question

Do structured state representations and 易象-inspired priors improve compositional generalization or sample efficiency beyond matched non-symbolic and shuffled-prior controls?

This is not a test of whether the Yijing or Taixuanjing is metaphysically true. It tests specific operational encodings on explicitly defined synthetic tasks.

## 2. Factorial design

### Representation factor
- **B2:** binary state representation.
- **T3:** ternary state representation.
- **L-K:** learned K-ary categorical representation, with K and parameter budget matched where possible.

### Prior factor
- **P0:** no symbolic prior.
- **PY:** operationalized Yijing-inspired prior, with mapping version frozen before evaluation.
- **PT:** operationalized Taixuanjing-inspired ternary prior, with mapping version frozen before evaluation.
- **PS:** shuffled prior preserving marginal frequencies and parameter count.
- **PR:** random prior sampled from the same declared family and budget.

### Composition factor
- **C-fixed:** fixed sparse composition baseline.
- **C-learned:** learned composition/ranker.
- **C-relational:** explicit relation/hyperedge learner, only where the task exposes relational structure.

Not every cell is meaningful. Predeclare valid combinations and do not silently drop failed runs.

## 3. Task families

1. **E01 sparse composition:** select non-contiguous elements from a sequence; evaluate exact composition and held-out position patterns.
2. **E02 relational rule induction:** infer finite-domain relations from support examples; test unseen combinations and rule families.
3. **E12 primitive induction:** propose reusable relation primitives from observations; evaluate on held-out generative mechanisms.

For each family, publish:
- generator source and version;
- train/validation/test generator seeds;
- exact train/test split rule;
- task difficulty and support-size schedule;
- leakage checks and generator collision audit.

## 4. Controls and fairness

- Match train examples, evaluation examples, optimizer steps and inference budget.
- Match parameter count within a declared tolerance; also report actual parameter count.
- Match total compute or report compute-normalized and wall-clock results separately.
- Keep the same architecture outside the factor under test.
- Include shuffled and random priors; a symbolic prior beating only P0 is insufficient evidence.
- Freeze prior mappings and hyperparameters before test evaluation.
- Tune on validation only. Do not use test feedback to revise mappings.
- Run at least 10 seeds for the primary comparison where compute permits; if fewer, label results exploratory and report all seeds.
- Publish per-seed outputs and confidence intervals, not only aggregate means.

## 5. Primary outcomes

Predeclare one primary outcome per task family. Recommended:
- exact-match accuracy on compositional OOD;
- exact-match accuracy on held-out rule families;
- sample efficiency: examples required to reach a fixed validation threshold.

Secondary outcomes:
- IID accuracy;
- calibration / Brier score;
- robustness to distractors and missing observations;
- inference FLOPs or measured runtime;
- memory footprint;
- primitive reuse precision and coverage;
- contradiction rate and abstention quality.

Do not collapse these into one opaque "intelligence score".

## 6. Statistical analysis

- Report mean, standard deviation, median and 95% confidence intervals across seeds.
- Use paired seed comparisons when runs share the same data-generation seeds.
- Report effect sizes, not only p-values.
- Correct for multiple comparisons across the predeclared primary contrasts.
- Include all failed, timed-out and invalid runs with reasons.
- Separate exploratory analyses from confirmatory analyses.

## 7. Falsification criteria

A symbolic prior is not supported if:
- it does not outperform its shuffled/random control;
- gains disappear under matched compute or parameter budgets;
- gains occur only IID but not on the target OOD split;
- results are unstable across seeds;
- performance depends on manually encoding test-generating rules;
- the prior increases accuracy but causes unacceptable calibration or contradiction regressions.

A ternary representation is not inherently superior because the source theory uses three-valued symbolism. It must beat binary and learned categorical controls on a task where the representational distinction is relevant.

## 8. Matrix expansion example

A first smoke-test matrix can use:
- tracks: E01, E02, E12;
- conditions: B2-P0, T3-P0, T3-PT, B2-PY, T3-PS;
- seeds: 11, 23, 47.

This yields 45 independent trial tasks. This smoke matrix checks orchestration and schema flow only; it is not sufficiently powered for scientific conclusions.

The full confirmatory matrix should enumerate valid representation × prior × composition × task-family cells and pre-register the primary contrasts.

## 9. Required artifacts per trial

Each task must emit:
- manifest digest and task ID;
- source commit and environment fingerprint;
- dataset/generator version and seed;
- representation, prior and composition configuration;
- parameter count and compute budget;
- raw predictions, targets and per-example metrics;
- aggregate metrics and failure diagnostics.

Raw outputs are immutable. Aggregation must verify that every expected task has a terminal status and must not omit failures from denominators without an explicit, justified exclusion rule.

## 10. Decision rule

Advance an encoding into the CPG-EI core only when it:
1. passes leakage and reproducibility checks;
2. beats matched random/shuffled controls on a preregistered primary metric;
3. reproduces across independent seeds;
4. offers a measurable benefit under compute/parameter accounting;
5. does not produce unacceptable calibration or robustness regressions.

Otherwise retain it as an experimental prior or reject it.
