# E11-A0.1 Robust Generator Arms

Date: 2026-11-11  
Status: generator implementation and focused tests added; execution/CI pending.

## Purpose

Translate three independent audit findings into controlled counterexample data
arms without changing the E11-A0 learner or the parallel one-to-one evaluation
work:

1. Missing defining attributes and false-positive attributes.
2. Shared attributes across concepts.
3. A nuisance cue whose correlation reverses across environments.

## Data contract

`RobustObjectView` exposes only an opaque object ID, an environment label,
and an observed attribute set. It does not expose concept membership or schema.
`RobustEpisode.truth` and `hidden_schemas` are evaluator-side data.
As in E11-A0, they coexist in the same Python process and are not a security
boundary.

## Generator arms

- `missing-noisy`: randomly drops defining attributes and injects false
  positives from the known attribute vocabulary.
- `shared-attribute`: all three planted concepts share `shared-00`;
  each also has two private attributes. This tests whether the common feature
  is incorrectly treated as a sufficient concept identifier.
- `nuisance-confounded`: learner observations come from `env-0`,
  where `nuisance-77` is positively associated with concept-a. Query
  observations come from `env-1`, where the association is reversed.

All modes permit overlapping memberships and use disjoint learner/query object
identities. The nuisance arm deliberately changes environment between splits;
it is not interchangeable with an ordinary random object split.

## Focused tests authored

- Determinism and object identity disjointness.
- Missing and false-positive attribute presence.
- Shared attribute commonality.
- Nuisance correlation reversal between environments.
- Invalid configuration rejection.

These are test definitions, not reported test results. No CI run or benchmark
score is claimed.

## Interpretation limits

This increment supplies harder data, not a concept learner. It does not solve
one-to-one candidate assignment, estimate unknown concept count, select
concepts by MDL, or prove open-world concept discovery. Those are separate
tracks. The one-to-one evaluation work is intentionally left to the parallel
E11-A evaluation branch.

## Reproduction

```bash
python -m unittest discover -s tests -p 'test_e11a0_robust_generators.py' -v
```
