# E12-A2-D — Noisy Measurements and Prior-Misspecification Stress

Status: first synthetic stress benchmark; no Yijing-specific prior or superiority claim.

## Research question

Do active measurement policies remain reliable when observations are noisy and the learner's prior differs from the environment's target distribution? In particular, can a structurally biased prior cause confident but wrong beliefs even when Bayesian updating is implemented correctly?

## Design

- Four hypotheses per world.
- Three noisy sensor families: complementary, rare-target, and redundant.
- Binary stochastic observations with action-specific likelihood (P(o=1\mid h,a)).
- Each action is usable once; each has a positive integer cost.
- Budget is fixed within a benchmark run.
- The environment samples targets from its private true prior and emits noisy outcomes.
- The learner sees only its chosen prior arm, the public likelihood table, action costs, and remaining budget.

Prior arms:
1. `matched`: learner prior equals the environment's true prior.
2. `uniform`: neutral prior.
3. `anti_aligned`: reversed true-prior weights as a deliberate stress condition.

Policies:
- `random`
- `fixed`
- `expected_ig`
- `cost_normalized_ig`
- `exact_optimal`: finite-horizon dynamic programming under the learner's own prior and supplied likelihood model.

The exact planner is not given the hidden target or the environment's private prior unless those happen to equal the selected learner prior. It is optimal only for the learner's declared model.

## Metrics

- MAP accuracy.
- Posterior confidence threshold rate (maximum posterior at least 0.95).
- Overconfident-wrong rate (maximum posterior at least 0.90 while MAP is wrong).
- Multiclass Brier score and log loss.
- Mean posterior entropy and MAP confidence.
- Mean acquisition cost.

The benchmark uses paired target draws and common action-specific sensor random streams across every prior and policy arm within each family/episode. If two arms select the same action at the same episode, they receive the same sampled sensor outcome. It reports paired metric deltas (matched-minus-uniform and anti-aligned-minus-uniform) with normal-approximation 95% confidence intervals. Bootstrap intervals and larger independent world families remain future work.

## CI result snapshot (Run #42873835303, 2026-11-11)

The full workflow passed on the branch head tested by Run #42873835303. The A2-D step used 100 episodes per family/prior/policy cell, budget 3, three noisy world families, three prior arms, and five policies (4,500 episodes total).

Expected-IG policy results:

| World family | Learner prior | Accuracy | Brier ↓ | Log loss ↓ | Overconfident-wrong rate ↓ |
|---|---|---:|---:|---:|---:|
| Complementary | Matched | 85% | 0.2453 | 0.5049 | 4% |
| Complementary | Uniform | 84% | 0.2841 | 0.5900 | 0% |
| Complementary | Anti-aligned | 85% | 0.3603 | 0.7723 | 11% |
| Rare | Matched | 85% | 0.2221 | 0.4379 | 2% |
| Rare | Uniform | 79% | 0.2643 | 0.5108 | 1% |
| Rare | Anti-aligned | 83% | 0.3519 | 0.7746 | 4% |
| Redundant | Matched | 84% | 0.2799 | 0.5752 | 0% |
| Redundant | Uniform | 78% | 0.3692 | 0.6941 | 0% |
| Redundant | Anti-aligned | 78% | 0.3861 | 0.7514 | 0% |

Paired anti-aligned-minus-uniform contrasts for Expected IG:
- Complementary: overconfident-wrong rate +11 percentage points; normal-approximation 95% CI [+4.8, +17.2] points.
- Rare: log loss +0.264; normal-approximation 95% CI [+0.024, +0.504].
- Redundant: the corresponding intervals include zero for the reported metrics.

Matched-minus-uniform contrasts did not establish a reliable accuracy or proper-score improvement at this sample size; the confidence intervals include zero. In the complementary family, the matched prior also increased the overconfident-wrong rate by 4 points (95% normal-approximation CI [+0.14, +7.86] points), despite lower average Brier/log loss. This is a reminder that a prior can improve aggregate scores while still creating more confident errors in a subset of episodes.

These are exploratory finite-synthetic results. The intervals are paired normal approximations, not bootstrap intervals; there is no multiple-comparison correction, and each family uses a fixed likelihood table rather than independently sampled world structures. Do not treat these results as evidence for any Yijing prior. Their current value is methodological: a future structured prior must beat the uniform and generic controls while passing confident-error and distribution-shift guardrails.

## Interpretation safeguards

1. A matched prior is not automatically better on finite samples; stochastic sensor outcomes can still produce errors.
2. A prior can improve accuracy while worsening calibration, or increase confidence without increasing correctness. Report proper scoring rules and overconfident-wrong rate.
3. An anti-aligned prior is a stress test, not a realistic estimate of any particular traditional prior.
4. No Yin/Yang, four-image, trigram, hexagram, or Five-Phase mapping is encoded here.
5. Likelihood tables are supplied to the learner; this tests inference and action choice under noise, not autonomous sensor-model learning.
6. These finite synthetic results do not establish natural cognition, causality, general intelligence, or any Yijing-specific advantage.

## Run

```bash
python -m unittest tests.test_e12a2d_noisy_prior_stress -v
python -m prototype.e12a2d_noisy_prior_stress --episodes 100 --budget 3 --start-seed 2026 --json
```

## Next steps

- Add world-seed block confidence intervals and paired comparisons.
- Add likelihood-model misspecification separately from prior misspecification.
- Add zero-information / observational-equivalence cases and ensure no prior arm manufactures certainty.
- Only after generic stress controls pass, compare preregistered Yijing prior arms with shuffled and anti-aligned controls.
