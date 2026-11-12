# N0.10 Fair Baseline Protocol v1

## Goal

Compare the learnable Xiang basis against controls that isolate (a) learnable representation, (b) multiplicative interaction structure and (c) generic nonlinear capacity. A raw accuracy comparison with unconstrained parameter counts is not interpretable.

## Parameter accounting

Let:
- (R): number of ordered roles
- (F): observable feature dimension per node
- (L): Xiang latent dimension
- (D=R F): flattened assignment dimension
- (S=R+\binom{R}{2}+\binom{R}{3}): unary, pair and triple role blocks

Learnable Xiang parameter count:

`P_xiang = L F + L + L S = L(F + 1 + S)`

One-hidden-layer MLP with hidden width (H), tanh activation and scalar logit:

`P_mlp = H(D + 1) + (H + 1) = H(D + 2) + 1`

Rank-(K) multiplicative tensor baseline, with one (F)-dimensional projection per role and rank component plus scalar bias:

`P_tensor = K R F + 1`

For the current (R=3,F=4,L=8) configuration:
- Xiang: (8(4+1+7)=96) parameters
- MLP: (H=7) gives 99 parameters
- Low-rank tensor: (K=8) gives 97 parameters

This is within a 5% parameter budget. Recompute widths/ranks from the actual role and feature schema rather than hardcoding these example values.

## Required controls

1. Raw SROK / existing structured learner.
2. Fixed-random Xiang basis with trainable readout.
3. Learnable Xiang basis.
4. Parameter-matched MLP.
5. Parameter-matched low-rank multiplicative tensor.
6. Optional graph message-passing baseline only when its edge construction is observable and identical across models.

The fixed-random control is essential: if learnable Xiang does not beat it, gains may come from the multiplicative feature map rather than learning the basis.

## Fairness constraints

- Identical JSONL records, train/dev/locked-test split, candidate pools, evidence masks and labels.
- Same optimizer family (full-batch gradient descent for the first comparison), epochs, learning-rate search budget, L2 search budget and seed list.
- Same inference candidate enumeration and maximum expansion budget. Do not compare one model's exact product search with another model's beam-pruned search.
- Match trainable parameters within ±5%; report exact counts.
- Use at least 10 fixed seeds for screening and 30 for a final claim.
- Lock the test family before hyperparameter selection. Select hyperparameters using train/dev only.
- Report mean, standard deviation and 95% bootstrap confidence intervals across seeds.

## Metrics

Primary:
- exact-match accuracy over all locked examples
- coverage and abstention rate
- covered accuracy
- budget-exhaustion rate

Secondary:
- candidate Recall@1 / Recall@K and MRR where candidate-level scores are available
- binary cross-entropy / log loss
- Brier score and expected calibration error
- per-rule-family and per-missingness-stratum performance
- wall-clock training/inference time and peak memory

## Acceptance gate

Do not promote Xiang as the default representation unless it:
- beats both fixed-random Xiang and parameter-matched MLP/tensor controls on held-out compositional families across seeds;
- has a positive paired confidence interval for the primary metric, not merely a better single seed;
- does not gain accuracy by collapsing coverage or increasing abstention;
- remains within the declared parameter and compute budgets;
- reproduces from a content-addressed dataset, config and checkpoint.

A failure to transfer is still a useful result: retain the operator as an experimental representation and inspect which order/role interactions are identifiable. Do not tune on locked-test examples.
