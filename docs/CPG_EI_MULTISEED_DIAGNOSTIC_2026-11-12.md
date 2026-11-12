# CPG-EI multi-seed structure-discovery diagnostic

Status: exact-head diagnostic completed; conclusions remain limited to the finite synthetic candidate universe.

## Scope

The existing sparse-teacher test exercises one train/validation seed pair. This diagnostic adds three independent data-seed pairs (7/107, 17/117, 29/129), each using 512 training and 128 validation examples, three growth rounds, up to three proposed edges per round, and 60 training epochs per round.

It reports, per seed:

- held-out validation bit accuracy;
- recall of the six teacher support edges;
- number of active edges;
- aggregate mean, population standard deviation, minimum and maximum validation accuracy;
- mean/minimum/maximum support recall, support precision, false-discovery count, active-edge count and exact-support recovery count.

The candidate universe remains the same finite 35-edge pairwise/third-order feature set. This does not test arbitrary node creation, unseen relation arities, open-world graph induction, or natural-language transfer.

## Interpretation boundary

This diagnostic checks seed sensitivity and makes the evidence visible in CI logs. It deliberately does not set a pass threshold for mean accuracy or support recall: such a threshold must be justified by a preregistered power/variance study and matched baselines, not chosen after observing these runs.

The next stronger validation should add:
1. a second teacher family with a different generating mechanism;
2. label-shuffle and feature-permutation negative controls;
3. pairwise-only and matched-compute baselines;
4. false-discovery rate and exact-support recovery;
5. preregistered confidence intervals and power analysis over a larger seed set.

A successful diagnostic is not evidence of open-ended relation discovery.


## Negative control: shuffled training labels

A deterministic negative control shuffles training targets across training states while leaving validation examples untouched. It reports validation bit accuracy, recovery of the known teacher support, false discoveries, active-edge count, and the finite candidate-universe size. This is a diagnostic measurement only; no post-hoc acceptance threshold is imposed. The control is intended to expose spurious structure recovery when the state/target relationship is destroyed.


A second negative control independently permutes each training feature column across examples while preserving each feature's marginal distribution and leaving labels untouched. It reports the same structure-recovery metrics as the shuffled-label control. This tests whether the learner depends on the original joint feature/target structure rather than marginal feature frequencies alone.


## Ten-seed reporting

The CI diagnostic now uses ten fixed independent seed pairs and emits per-seed precision/recall, false discoveries, active-edge count and exact-support recovery, plus descriptive mean/standard deviation/minimum/maximum summaries. These are descriptive synthetic-benchmark statistics; no pass threshold or generalization claim is inferred from them.


## Candidate-score normalization ablation (2026-11-12)

Exact-head CI run #43201228903 succeeded on commit `0dc9c0a664485aac8f4e432a927dce07b47b034b` (5 tests). The paired five-seed comparison produced:

| Metric | Raw score | Residual-norm normalized |
|---|---:|---:|
| Mean support recall | 0.5667 | 0.4667 |
| Exact six-edge recovery | 0/5 | 0/5 |
| Mean false discoveries | 0.8 | 0.8 |

Validation bit accuracy was identical between the two modes for each paired seed. Normalization reduced the number of active edges but also reduced support recall; it did not improve exact recovery or false discoveries. **Decision: retain raw scoring as the default; keep normalization only as an explicit ablation option.** This five-seed result is diagnostic, not a universal ranking claim.
