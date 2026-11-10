# YF-07–YF-10: Dynamic Transformation Cognition

Status: bounded symbolic research prototypes and preregistered-style evaluation contract. No neural learning gain, causal-discovery claim, or classical-theory advantage is established.

## Research objective

Extend YF-01–YF-06 from timing-aware observation and reciprocal interaction into four falsifiable capabilities:

- YF-07 **Autonomous 察机**: detect change points and candidate trigger conditions from observations, rather than receiving the transition time.
- YF-08 **Dynamic 类象 generation**: propose new feature relations from observed data using a declared bounded grammar.
- YF-09 **Relation reversal learning**: identify when the estimated sign of a relation differs across sufficiently supported contexts.
- YF-10 **Multi-path 机变推演**: enumerate and compare multiple budget-feasible future paths under an explicit transition model.

The Chinese classical terms name research inspirations only. The algorithms below are modern, bounded statistical/symbolic constructions.

## YF-07 — Autonomous 察机

Prototype: `detect_change_point` in `prototype/yinfu_dynamic_cognition.py`.

The first slice is retrospective change-point detection: scan admissible split points, compare pre/post means, and require a preregistered minimum effect and minimum segment length. This tests whether the system can locate an unannounced regime transition in a sequence.

Required next experiment:
1. Generate piecewise-stationary, gradual-drift, periodic, heavy-noise, and no-change series.
2. Compare fixed threshold, random split, CUSUM, and windowed mean baselines.
3. Evaluate detection delay, false-alarm rate, localization error, and calibration on held-out generators.
4. Shuffle timestamps and include placebo series.

Important limitation: a detected change point is not yet an explanation of its cause. Trigger-condition induction is a separate next slice and must be evaluated on held-out contexts.

## YF-08 — Dynamic 类象 generation

Prototype: `generate_relation_candidates`.

The current grammar proposes unary thresholds and pairwise difference/product thresholds. Candidate thresholds are generated from support rows only; candidates are ranked by support balanced accuracy. This is deliberately a small, auditable search space, not unrestricted concept invention.

Required validation:
- Separate Support, Gate, and Locked-Test by episode/generator seed.
- Use Gate only for candidate selection; reveal Locked-Test only after predictions are committed.
- Compare generic unary features, pairwise grammar, random/permuted feature mappings, lookup-table baselines, and an oracle grammar control.
- Add nonlinear out-of-grammar and nuisance-feature controls.
- Report coverage, balanced accuracy, candidate count, search cost, false-discovery rate, and abstention.
- Apply multiple-comparison correction or use an untouched Gate/Locked-Test hierarchy.

A relation that only fits Support is not a discovered primitive. Promotion requires independent Gate evidence and delayed counterexample monitoring.

## YF-09 — Relation reversal learning

Prototype: `learn_contextual_reversal`.

The current slice estimates mean effects within named contexts and reports reversal only when at least two contexts each meet a minimum sample count and their effects exceed a minimum magnitude with opposite signs.

This is descriptive conditional association, not causal effect identification. Future intervention experiments must randomize actions within context, report overlap/positivity, and use held-out contexts. Include:
- same-sign and zero-effect controls;
- context-label permutation;
- sample imbalance and measurement noise;
- continuous context and threshold sensitivity;
- reversal precision/recall and confidence intervals.

Do not infer a reversal from one positive and one negative singleton.

## YF-10 — Multi-path 机变推演

Prototype: `enumerate_paths`.

Enumerates simple paths up to a depth and cost budget, then ranks them by accumulated declared utility minus cost. The current prototype is deterministic exhaustive enumeration over a finite transition graph; it is not actual parallel hardware execution, learned world modeling, or globally optimal planning beyond that graph.

Required comparisons:
- greedy one-step, beam search, random feasible path, and exhaustive oracle on small graphs;
- equal node-expansion and compute budgets;
- branching-factor/depth stress tests;
- model misspecification and transition uncertainty;
- path regret, best-path recall, cost, diversity, and budget-exhaustion rate.

## Shared experiment protocol

1. Split by generator family and seed, not by random rows from the same episode.
2. Freeze grammar, thresholds, budgets, and stopping rules before Gate/Locked-Test.
3. Keep classical mappings as independent arms: Five Phases, 命物时功神, generic learned/statistical, capacity-matched random, and permuted-symbolic controls.
4. Report negative results and uncertainty intervals; do not select a classical mapping after seeing Locked-Test.
5. Record candidate provenance, support IDs, grammar version, Gate evidence, prediction commits, and later counterexamples.
6. Keep every module optional. No default CPG-EI path should depend on a YF prior until replicated held-out gains are demonstrated.

## Integration boundaries

- E12-A2 supplies the active-observation baseline; YF-07 must not silently replace its information-gain selector.
- E02 supplies finite symbolic rule-induction controls; YF-08 must demonstrate generalization beyond its declared grammar and compare against abstaining finite-rule baselines.
- E12-A6's Candidate/Evidence/Action lifecycle is the intended future evidence-governance adapter. This PR does not claim that adapter is implemented.
- YF-09 must not convert context-conditioned correlation into causal language.
- YF-10 consumes explicit transition candidates; it does not generate trusted world dynamics itself.

## Promotion gate

Do not merge this research slice into main or make it a default architecture component until: full repository CI passes on the exact head; independent review checks leakage and budget accounting; multi-seed held-out generator results beat capacity-matched controls; and the gains survive shuffled/permuted and out-of-grammar tests.


## Compact seeded capability benchmark

The prototype now exposes `run_synthetic_benchmark(seeds=5, start_seed=100)` in the same module. This keeps the benchmark implementation alongside the primitives and avoids a separate executable artifact.

The runner returns raw per-seed metrics for four narrowly scoped tests:

- YF-07: abrupt mean-shift detection rate, localization error, and null-series false-alarm rate.
- YF-08: select the top relation candidate using support rows only, then evaluate balanced accuracy on separately generated test rows. The generating product operator is part of the declared grammar, so this is grammar recovery, not open-ended discovery.
- YF-09: reversal detection on a positive condition, plus same-sign and zero-effect negative controls.
- YF-10: greedy path regret against exhaustive enumeration on the same finite graph and budget.

The runner is deterministic for a fixed seed. Unit tests check repeatability and verify that candidate-budget truncation retains feature, difference, and product operator families. It is a smoke benchmark, not a substitute for disjoint generator-family evaluation, statistical confidence intervals, intervention-based causal tests, or equal-compute planning comparisons.



## CI smoke result snapshot — Run #42893566018

Exact tested head: `2c8664ba01ec2106dddedc522761732ddbc35501`. GitHub Actions completed the full unit-test suite and the five-seed smoke benchmark.

| Measure | Five-seed result |
|---|---:|
| YF-07 change detection | 100% (60/60 episodes) |
| YF-07 mean localization error when detected | 0.067 samples |
| YF-07 null false-alarm rate | 0% (0/60) |
| YF-08 mean held-out balanced accuracy | 0.837 |
| YF-08 selected operator | Product in all 5 seeds |
| YF-09 reversal detection | 100% (150/150 cases) |
| YF-09 same-sign false reversal | 0% (0/150) |
| YF-09 zero-effect false reversal | 0% (0/150) |
| YF-10 mean greedy regret vs finite-graph oracle | 0.368 net-utility units |

Interpretation is intentionally narrow:

- YF-07's shift size is large relative to its Gaussian noise and the detector threshold; these results do not establish robust early warning or gradual-change detection.
- YF-08's product operator is part of the search grammar and the generator; the result is held-out sample generalization within that known grammar, not novel open-world relation invention.
- YF-09 uses strongly separated supplied contexts and effects; its perfect result does not demonstrate causal discovery or general context induction.
- YF-10 shows a positive regret gap for the local greedy baseline on the generated graphs, but exhaustive search is an oracle with full graph knowledge and is not compute-matched.

The benchmark used five seeds only. Treat these numbers as a smoke-test snapshot, not a confirmatory study or evidence of Yinfu/Yijing-specific benefit. Next validation must expand seeds, vary signal-to-noise and generator families, add permuted controls, and compare planning under equal node-expansion budgets.
