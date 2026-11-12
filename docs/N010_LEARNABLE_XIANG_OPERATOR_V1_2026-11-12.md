# N0.10 Learnable Xiang Operator Prototype v1

Status: experimental implementation; it is not yet accepted as the default SROK representation.

## Implementation

`prototype/n010_xiang_operator.py` implements a shared latent basis:

`z(x) = tanh(Wx + b)`

and role-bound score composition:

- unary: (z(x_r))
- pairwise: (z(x_i) \odot z(x_j))
- third-order: (z(x_i) \odot z(x_j) \odot z(x_k))

A linear readout scores the concatenated blocks. The implementation uses pure Python and deterministic full-batch binary cross-entropy gradients. No external ML framework is required.

Two modes are provided:

- `learnable`: updates basis and readout.
- `fixed_random`: freezes the seeded random basis and trains only the readout.

The input is the observable `Node.features` and role schema. Rule-family labels, split names and target identifiers are not operator inputs.

## Example

```python
from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_xiang_operator import LearnableXiangOperator, XiangConfig

roles = tuple(RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
              for name in ("r0", "r1", "r2"))
model = LearnableXiangOperator(roles, feature_dim=4,
                               config=XiangConfig(latent_dim=8, seed=7))
```

Train using `RelationClassificationExample` rows with binary labels -1/+1. Checkpoints are deterministic JSON envelopes with SHA-256 integrity validation.

## Interpretation and limits

This is an explicit, testable engineering interpretation of 象/数/理:
- 象: latent basis (z(x))
- 数: observable numeric features and evidence attributes
- 理: role-conditioned unary/pair/third-order composition

It is a hypothesis, not a claim that classical 易学 concepts are already validated computational primitives. The implementation is not yet wired into the main experiment runner, and no performance gain is claimed.

## Evaluation gate

Compare against raw SROK, fixed-random basis, unary/pairwise ablations, MLP, low-rank tensor and graph baselines. Match parameter count and compute budget, use multiple seeds, and evaluate a second non-parity rule family. Keep locked-test labels out of model selection. Accept the operator only if it shows repeatable held-out-family gains over both raw and fixed-basis controls without unacceptable coverage/calibration regression.

This component does not solve autoregressive KV-cache growth. Long-context memory compression requires a separate information-retention and retrieval benchmark.
