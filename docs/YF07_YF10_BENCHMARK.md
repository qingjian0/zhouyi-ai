# YF-07–YF-10 Unified Synthetic Capability Benchmark

Status: executable multi-seed synthetic benchmark. Results must be generated from a recorded exact commit and interpreted only within each task's declared scope.

## Purpose

The initial YF-07–10 prototypes were unit-tested but had no comparative experiment harness. This benchmark adds a common seeded evaluation runner with independent support/test samples where applicable, negative controls, and a finite-graph oracle comparison.

Run:

```bash
python -m prototype.yinfu_dynamic_cognition_benchmark --seeds 20 --start-seed 100 --json
python -m unittest tests.test_yinfu_dynamic_cognition_benchmark -v
```

## E-YF07 — Change-point detection

- Generate piecewise-constant mean-shift sequences with randomized transition locations, shift signs/magnitudes, and Gaussian noise.
- Evaluate the detector's detection rate and localization error.
- Compare localization error with a fixed midpoint baseline.
- Generate independent null sequences to estimate false-alarm rate.
- Limitation: this does not yet test gradual drift, periodicity, adversarial noise, or causal trigger identification.

## E-YF08 — Candidate relation generalization

- Generate support and test samples independently from the same two-feature distribution.
- Target is a thresholded product relation, while the candidate grammar contains unary, difference, and product operators.
- Select the top-ranked candidate on support only; freeze it before evaluating the independent test set.
- Compare with the top support-ranked unary candidate.
- Limitation: the target operator is inside the declared grammar. This tests recovery/generalization within a known grammar, not unrestricted discovery. It does not yet include multiple-comparison correction or a fully disjoint generator-family test.

## E-YF09 — Contextual reversal and negative controls

Three equally structured conditions:
1. Reversal: context A has positive mean effect, context B negative.
2. Same-sign negative control: both contexts have positive mean effect.
3. Zero-effect negative control: both contexts have zero mean effect.

Each context receives repeated noisy observations. Report reversal detection rate and false reversal rates in the two controls.
Limitation: contexts and effect observations are supplied. This tests sign-pattern detection, not causal inference or autonomous context discovery.

## E-YF10 — Multi-path planning

- Generate layered directed acyclic graphs with stochastic edge utility and positive cost.
- Compare one-step greedy path selection with exhaustive simple-path enumeration under the same depth and cost constraints.
- Report mean net utility and greedy regret relative to the finite-graph oracle.
- Limitation: transition graph and edge values are known and deterministic within each episode. This does not test learned world models, uncertainty propagation, or runtime-matched search.

## Reproducibility and interpretation

- Every task uses deterministic seeds.
- The suite reports per-seed outputs; summarize across seeds only after preserving raw JSON.
- Do not pool unlike metrics across tasks.
- A benchmark win on these generated distributions is not evidence of general cognition, natural-world prediction, causal discovery, or superiority of Yinfu/Yijing representations.
- Next validity upgrade: disjoint generator families, shuffled-feature controls, gradual/noisy change processes, intervention-based reversal tests, and equal-node-expansion planning comparisons.
