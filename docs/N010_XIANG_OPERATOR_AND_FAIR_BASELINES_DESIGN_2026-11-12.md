# N0.10 fair baselines and learnable Xiang operator design

Status: experiment specification; no result is claimed until implementations, parameter counts and multi-seed runs are attached.

## 1. Operational definition

This project uses the traditional terms as an engineering decomposition, not as claims that a classical cosmology is already a validated neural mechanism:

- **象 (Xiang / representation basis):** a learned or fixed set of latent channels derived from observed node features.
- **数 (Shu / measurable state):** numeric attributes, discrete tags, evidence confidence, missingness and provenance.
- **理 (Li / relational law):** explicit unary, pairwise and higher-order operators over role-bound latent representations.

The operator must receive only observable inputs. The hidden rule family, target IDs, evaluator labels and split names are never operator inputs.

## 2. Candidate learnable operator

For a node feature vector (x\in\mathbb{R}^{d}), define a shared latent basis:

\[
z(x)=\tanh(Wx+b),\qquad W\in\mathbb{R}^{k\times d},\ b\in\mathbb{R}^{k}.
\]

For an ordered role assignment (a=(x_1,\ldots,x_R)), use:

\[
S(a)=\sum_r u_r^\top z(x_r)
+\sum_{r<s}v_{rs}^\top(z(x_r)\odot z(x_s))
+\sum_{r<s<t}w_{rst}^\top(z(x_r)\odot z(x_s)\odot z(x_t)).
\]

Here (z) is the learnable Xiang basis, observed numeric/evidence fields are Shu, and the role-conditioned composition terms are Li. The Hadamard products are a low-cost factorized interaction, not a full dense tensor. The existing raw-feature SROK remains the control and fallback.

### Required controls

1. Raw-feature SROK, same interaction order.
2. Fixed random projection (W), frozen after seeded initialization.
3. Fixed orthogonal projection, frozen.
4. Learnable shared (W,b).
5. Learnable role-specific (W_r,b_r).
6. Feature-shuffled and relation-label-shuffled negative controls.

The learned operator must beat fixed-basis controls on held-out rule families, not merely fit IID parity data. If it only improves train/dev loss, it has not established a useful Xiang basis.

## 3. Parameter and compute matching

The current raw SROK parameter count is:

\[
P_{\mathrm{SROK}}=d\left(R+\binom{R}{2}+\binom{R}{3}\right).
\]

For the shared-basis operator, count every learned parameter explicitly:

\[
P_{\mathrm{Xiang}}=kd+k
+k\left(R+\binom{R}{2}+\binom{R}{3}\right).
\]

For role-specific bases, replace the first (kd+k) term with (R(kd+k)). Report parameter count, multiply-add estimate, activation memory and wall-clock time. Compare baselines within ±5% parameter count where feasible; otherwise report the mismatch and add a width sweep rather than calling the comparison matched.

Baseline families:

- Unary and pairwise SROK ablations.
- Full third-order raw SROK.
- MLP over the same role-concatenated observable features.
- Low-rank CP tensor with rank selected by parameter budget.
- Small message-passing graph model with the same candidate/evidence graph and a fixed number of rounds.

All models receive identical rows, candidate pools, splits, labels, optimizer family, epoch/update budget, early-stopping rule and inference expansion budget. Report optimizer and hardware details. No baseline gets extra feature engineering.

## 4. Dataset matrix

Use the synthetic generator's provenance-bound JSONL as the initial controlled suite:

- IID even-parity train/dev.
- Locked odd-parity family shift.
- Noise and missing-evidence sweeps.
- Candidate-pool scaling (2, 3, 4, 6 candidates per role).
- Distractor scaling and irrelevant evidence.
- At least five independent data seeds for every reported aggregate.

Add a second family generator before making broad claims: a non-parity compositional rule with different causal structure. A model should not pass a single synthetic family and be described as generally learning 易象.

## 5. Evaluation contract

Primary:
- Exact-match accuracy on all examples.
- Coverage and abstention rate.
- Accuracy conditional on coverage.
- Budget-exhaustion and beam-pruning rates.

Secondary:
- Candidate Recall@K / MRR.
- Binary relation log loss and Brier score where binary labels exist.
- Expected calibration error with fixed binning and confidence intervals.
- Per-family and per-noise-level breakdowns.
- Parameter count, FLOPs/MACs, peak memory, latency.

Use paired seeds and bootstrap confidence intervals. Keep locked-test labels inaccessible during hyperparameter selection. Publish every seed, not only the best run.

## 6. Acceptance gates

A learnable Xiang operator is accepted only if all are true:

1. Unit tests verify finite outputs, shape validation, deterministic checkpoint roundtrip and gradient correctness.
2. It matches the raw-SROK parameter/compute budget or reports a transparent width sweep.
3. It improves held-out-family performance over both raw SROK and fixed-basis controls across multiple seeds, with uncertainty intervals.
4. The gain survives feature permutation controls and does not depend on hidden rule-family metadata.
5. It does not trade away coverage or calibration without an explicit measured trade-off.
6. An independent non-parity family reproduces the benefit.

Until these gates pass, Xiang is an experimental representation/operator hypothesis, not a proven replacement for Transformer or a demonstrated KV-cache solution.

## 7. Relationship to long-context and KV memory

This operator acts on structured candidate/evidence state. It does not, by itself, solve autoregressive token generation or KV-cache growth. A separate memory-compression benchmark must measure retained information, retrieval accuracy, update cost and memory bytes at fixed context lengths. Do not infer million-token capability from success on structured role-binding data.
