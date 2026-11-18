# E10-B: Evidence-Driven Concept Split and Merge

## Research question

Can a learner revise its own concept partition when accumulated evidence indicates that a broad concept contains predictively distinct sub-concepts, and later merge those sub-concepts when new evidence removes the distinction?

## Minimal operational model

Each entity has a categorical feature map and one revealed binary target. The learner begins with one broad root concept. For each active leaf, it evaluates bounded categorical feature splits using Gini impurity reduction. A split is permitted only when:
- every child has at least \`min_members_per_child\` observations;
- all members have the candidate feature;
- child count is within \`max_children\`;
- impurity reduction exceeds \`min_split_gain\`.

Sibling leaves merge when their observed target-rate spread is at most \`merge_rate_tolerance\`. Both operations are appended as explicit revision events, including evidence IDs, split gain/rate spread, and complexity delta. Unknown feature values or missing split keys produce abstention rather than a guessed branch.

## Why split and merge both matter

A system that can split but never merge is a one-way complexity ratchet. A system that merges without evidence can erase useful distinctions. E10-B therefore treats split and merge as competing, evidence-gated operations over a reversible parent-child structure.

## Test cases

- Predictive feature separates a coarse concept into two supported sub-concepts.
- Unique nuisance values cannot force a split because each child lacks minimum support.
- New counterevidence makes sibling target rates converge and triggers merge.
- Duplicate observation/entity IDs are rejected without state mutation.
- Missing or unseen branch values abstain.

## Limits and threats to validity

- This is a bounded categorical partitioner, similar to a small incremental decision tree.
- The feature vocabulary is supplied; it does not invent raw features or semantics.
- The binary target is revealed supervision, not unsupervised concept discovery.
- Gini gain and empirical target rates can overfit; minimum support is not a statistical confidence guarantee.
- Merge uses a fixed rate-spread threshold, not a calibrated Bayesian or sequential hypothesis test.
- There is no representation transfer, causal model, continual non-stationarity benchmark, or evaluator process isolation yet.

## Required next experiments

1. Compare no-revision, split-only, merge-only, split+merge, and random-boundary controls under identical evidence streams and compute budgets.
2. Add delayed/noisy labels, class imbalance, missing attributes, nuisance correlations, and distribution shifts.
3. Hold out entity IDs and feature-value combinations; measure prequential accuracy, coverage, concept count, split/merge churn, false-split rate, false-merge rate, and cumulative complexity.
4. Replace fixed thresholds with sequential evidence tests and compare calibration.
5. Only after the neutral baseline is stable, test Zhouyi-inspired structural priors as an isolated ablation: Yin/Yang as binary partition proposal, Four Symbols as hierarchical two-stage partition, trigram/hexagram analogues as bounded multiway composition, and changing-line analogues as reversible state transitions. Compare against random proposals with matched proposal count and compute.

## Interpretation boundary

Passing these tests demonstrates only that the prototype can revise a finite categorical partition under a controlled evidence stream. It does not establish open-world autonomous concept formation or general intelligence.
