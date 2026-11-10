# E12-A2 × E02-D — Active Identification of Finite Relation Rules

Date: 2026-11-11  
Branch: `research/e12a2-e02-active-rule-identification-2026-11-11`  
Status: integrated benchmark prototype and protocol; execution must be verified on the exact commit.

## Research question

Can active measurement selection identify an unknown relation rule with fewer observations than random or fixed measurement order, while preserving uncertainty when the available observations are insufficient?

This connects two existing research lines:
- E02-D supplies a finite, explicitly bounded affine rule family over Z3 and reports how support size affects identifiability.
- E12-A2-M supplies an expected-information-gain selector over finite hypotheses and permitted measurements.

The integration is intentionally narrow: it tests active **passive measurement** selection, not intervention or causal discovery.

## Task

The hidden environment selects one rule from the 27-rule family:

`c = -(αa + βb + δ) \bmod 3`

with α,β,δ in {0,1,2}. A query is a pair (a,b) in Z3 x Z3; its measured outcome is c.

The learner receives one initial Support observation and the remaining permitted query IDs. It reconstructs the consistent hypothesis set from evidence. It does not receive the target rule ID, seed, or hidden generator state.

## Compared policies

1. **Information gain:** select the query maximizing expected entropy reduction under a uniform posterior over consistent rules, normalized by unit query cost.
2. **Random:** select a uniformly random remaining query.
3. **Fixed:** select the lexicographically first remaining query.
4. **Exact oracle:** dynamic-programming policy minimizing expected remaining unit-cost measurements on the finite hypothesis set. This is an upper-bound diagnostic, not a learner baseline.

All policies receive the same initial observation, query domain, and unit measurement costs. Run at least 100 seeds across all 27 target rules.

## Primary metrics

- identification rate;
- mean and maximum additional measurements after the initial Support observation;
- mean remaining consistent hypotheses;
- per-rule and per-seed outcomes.

Do not treat individual query outcomes as independent statistical samples; the independent unit is the target-rule/seed episode.

## Leakage and decision boundary

The policy functions accept only evidence and permitted query IDs. The hidden target is used by the episode runner solely to reveal the selected query's outcome. Mutating the target while holding learner evidence fixed must not change the selected query.

A singleton consistent set is IDENTIFIABLE only within this declared finite grammar and noiseless observation model. If no permitted query separates remaining candidates, the system must remain ambiguous; it must not infer an unobserved distinction.

## Interpretation limits

- The hypothesis class is known and finite; this does not demonstrate open-world rule invention.
- The observation model is deterministic and noiseless.
- The prior is uniform; prior misspecification and noisy likelihood calibration are not tested.
- Unit costs are equal; this is not a real-world compute or latency benchmark.
- The exact oracle knows the finite hypothesis class and is not a fair deployable learner.
- No Yijing prior is included. Any such prior requires a separate capacity-matched generic and shuffled ablation.

## Reproduction

`python -m unittest tests.test_e12a2_e02_active_rule_identification -v`

`python -m prototype.e12a2_e02_active_rule_identification --seeds 100 --start-seed 100 --json`

The workflow result on the exact branch commit is authoritative; do not infer success from the presence of tests or this protocol.
