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
