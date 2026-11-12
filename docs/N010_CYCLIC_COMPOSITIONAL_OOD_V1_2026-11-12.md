# N0.10 Cyclic Compositional OOD Dataset v1

## Purpose

This generator adds a second controlled rule family that is structurally different from parity. It is intended to test whether relation learners can infer a compositional operator and transfer it across a held-out relation-family transformation.

## Rule

Each candidate has observable features `[x, y, evidence_quality, missing_indicator]`. For a three-role assignment, the forward family scores:

`score = x0*y1 + x1*y2 + x2*y0`

The locked-test family reverses the cycle:

`score = x0*y2 + x2*y1 + x1*y0`

The target is the assignment with the maximum latent score. Noise perturbs observed x/y values; missing evidence zeroes observed x/y while retaining the latent value only inside the generator's target oracle. Latent values, family labels and target IDs are not model inputs.

## Split policy and provenance

- train: `cycle-forward`
- dev: `cycle-forward`
- locked_test: `cycle-reverse`

The generator writes JSONL plus a sidecar manifest using the existing N0.10 synthetic provenance schema. The dataset SHA-256, split-family declarations and actual record families are checked by `load_dataset`; locked-test family overlap with train/dev is rejected.

Example:

```python
from prototype.n010_synthetic import generate_compositional_dataset

generate_compositional_dataset(
    "artifacts/n010-cycle.jsonl",
    seed=17,
    train_count=256,
    dev_count=64,
    locked_test_count=64,
    candidates_per_role=4,
    noise_rate=0.02,
    missing_rate=0.02,
)
```

## Interpretation limits

This is a synthetic cyclic bilinear retrieval benchmark, not natural-language reasoning. Because the target oracle uses latent values when evidence is missing, missingness creates irreducible uncertainty; coverage and abstention must be reported alongside exact-match accuracy. The reverse-cycle locked test is a deliberately stronger structural transfer test and is not expected to be solved by every model.

Do not tune on locked-test labels. Evaluate multiple seeds and compare raw SROK, fixed-random Xiang basis, learnable Xiang basis, parameter-matched MLP and low-rank tensor controls under identical candidate pools and expansion budgets.
