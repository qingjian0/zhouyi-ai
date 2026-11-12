# N0.10 synthetic rule-family generator v1

Status: deterministic benchmark-data generator. It complements the N0.10 runner; it does not claim semantic or real-world generalization.

## Generate

```bash
python -m prototype.n010_synthetic \
  --output data/n010-rule-families.jsonl \
  --seed 20261112 \
  --train-count 512 --dev-count 128 --locked-test-count 128 \
  --candidates-per-role 4 --noise-rate 0.05 --missing-rate 0.05
```

The generator writes the JSONL dataset and a sibling `.manifest.json` containing the dataset SHA-256, seed, feature layout, generation parameters, counts and rule-family split policy.

## Rule and feature contract

- Three roles: `r0`, `r1`, `r2`; each role pool contains at least two candidates and both latent signs.
- Four node features: observed sign, unary utility, evidence quality and missing-evidence indicator.
- Train/dev target assignments satisfy latent sign product `+1` (even parity).
- Locked-test target assignments satisfy latent sign product `-1` (odd parity).
- Within the feasible parity class, summed unary utility selects one unique target assignment.
- Noise flips observed signs; missing evidence masks the observed sign and removes its evidence reference. The latent rule is used only to construct labels and is never emitted as a feature.
- The locked-test rule family is disjoint from train/dev by construction. The generator manifest records this policy separately from the N0.10 runner manifest.

This is a deliberately controlled higher-order identification and distribution-shift benchmark. The even-to-odd family change is a hard transfer test, not an expected-success guarantee. Report IID dev and held-out family results separately; do not tune on locked-test outcomes.

## Runner configuration

```python
from prototype.n09_learnable_srok import RoleSpec
roles = tuple(
    RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
    for name in ("r0", "r1", "r2")
)
```

Then pass the generated JSONL, `feature_dim=4`, and these roles to `run_experiment`. Use the exact source Git SHA in the runner config. Preserve the generator manifest beside the run report so the data-generation provenance remains auditable.

## Limits and next comparisons

The generator provides controlled data with known latent rule families; it does not model natural-language semantics, calibrated uncertainty, or real-world evidence acquisition. The next evaluation gate is a parameter/feature-budget-matched comparison among unary-only, pairwise-only, third-order SROK, MLP and low-rank tensor/graph baselines, with identical data, splits, optimizer budget and inference budget. Locked-test results must remain unopened until model selection is frozen.
