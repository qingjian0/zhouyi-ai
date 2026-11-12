# CPG-EI multi-seed structure-discovery diagnostic

Status: diagnostic harness; no cross-seed performance claim until exact-head CI output is inspected.

## Scope

The existing sparse-teacher test exercises one train/validation seed pair. This diagnostic adds three independent data-seed pairs (7/107, 17/117, 29/129), each using 512 training and 128 validation examples, three growth rounds, up to three proposed edges per round, and 60 training epochs per round.

It reports, per seed:

- held-out validation bit accuracy;
- recall of the six teacher support edges;
- number of active edges;
- aggregate mean accuracy and support recall.

The candidate universe remains the same finite 35-edge pairwise/third-order feature set. This does not test arbitrary node creation, unseen relation arities, open-world graph induction, or natural-language transfer.

## Interpretation boundary

This diagnostic checks seed sensitivity and makes the evidence visible in CI logs. It deliberately does not set a pass threshold for mean accuracy or support recall: such a threshold must be justified by a preregistered power/variance study and matched baselines, not chosen after observing these runs.

The next stronger validation should add:
1. a second teacher family with a different generating mechanism;
2. label-shuffle and feature-permutation negative controls;
3. pairwise-only and matched-compute baselines;
4. false-discovery rate and exact-support recovery;
5. confidence intervals over at least 10 independent seeds.

A successful diagnostic is not evidence of open-ended relation discovery.


## Negative control: shuffled training labels

A deterministic negative control shuffles training targets across training states while leaving validation examples untouched. It reports validation bit accuracy, recovery of the known teacher support, false discoveries, active-edge count, and the finite candidate-universe size. This is a diagnostic measurement only; no post-hoc acceptance threshold is imposed. The control is intended to expose spurious structure recovery when the state/target relationship is destroyed.
