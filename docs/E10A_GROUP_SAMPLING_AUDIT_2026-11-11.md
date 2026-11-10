# E10-A Group-level Sampling and Statistical Unit Audit

Date: 2026-11-11  
Audited base: PR #42 head `03f13b701009bac7d99efb6928e70bf298e46ad6`  
Status: implementation adds sampling diagnostics; no test or CI pass is claimed.

## Finding

The label-blind adapter samples participant groups uniformly within each relation symbol. Its sampling unit is:

`(relation_symbol, unordered_participant_set)`

A group may contain multiple observations (for example, the same participants under a positive and a context-negative condition). Therefore uniform group selection is not equivalent to uniform observation selection. Observation-level inclusion probability depends on the size of its group.

This matters for the estimand:
- group-macro evaluation estimates performance on a randomly selected structural participant group;
- observation-micro evaluation weights larger groups more heavily;
- reporting only the total number of query observations hides this distinction.

Neither estimand is inherently wrong, but the benchmark must declare which one is primary. Confidence intervals should resample independent generation seeds or episodes, not treat correlated rows inside one group as independent samples.

## Change in this branch

The task manifest now records:
- explicit sampling unit;
- explicit uniform-group weighting policy;
- Support and Query group-size histograms.

The histograms are structural and label-blind. Their weighted sums must equal the corresponding observation counts.

## Required evaluation protocol

1. Report group-macro metrics and observation-micro metrics separately.
2. Report per-group size distribution and per-relation coverage.
3. Aggregate uncertainty across independent seeds/episodes; do not bootstrap individual observations as if independent.
4. Preserve the label-blind assignment property: changing evaluator labels must not change selected Query group IDs.
5. Keep A-G claims limited to known-object recombination. This audit does not create object-disjoint or component-disjoint generalization.

## Limitations

- No learner is evaluated here.
- Group-level diagnostics do not remove shared-object dependence across groups.
- The generator may induce unequal and correlated group sizes.
- Object-disjoint and connected-component-disjoint tracks still require generator-level design, not post-hoc relabeling of this A-G split.
- Exact tests and CI have not been executed in this environment.
