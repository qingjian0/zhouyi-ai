# CPG-EI Counterfactual Context Coverage Audit v1

## Motivation

Pairwise influence requires matched states that differ in exactly one variable. Merely counting matched pairs is insufficient for conditional relations: all matched pairs may occur in contexts where the relation is inactive.

Example: let the target be `x0 XOR x1` only when `x2 == 1`, and zero otherwise. A training sample containing the complete `x0,x1` subcube at `x2 == 0` has matched pairs for both operands, but no observed operand influence. This does not identify the operands as irrelevant; it only shows that the sampled contexts did not activate the relation.

## Implemented diagnostic

For each input variable, the audit now reports:

- matched pair count;
- target-flip count;
- number of distinct contexts in which a matched pair was observed;
- number of contexts with a target flip;
- total possible context count, equal to `2 ** (input_dim - 1)`;
- observed context coverage ratio.

A context is the tuple of all input values except the variable being toggled. This allows us to distinguish pair count from diversity of counterfactual contexts.

## Interpretation

- Positive flips are direct evidence of influence in the corresponding observed contexts.
- Zero flips with partial context coverage is inconclusive; unobserved contexts may contain conditional influence.
- Full context coverage with zero flips is stronger evidence for irrelevance under deterministic complete binary observations, but must still be interpreted relative to label integrity and the assumed state representation.
- This diagnostic does not itself infer conditional operators or repair support proposals.

## Regression fixtures

Tests include:
1. all operand combinations observed only in an inactive context;
2. matched pairs observed in the active context;
3. full context coverage across the complete three-bit state space.

## Next gate

Use controlled sampling to measure how context coverage affects support precision/recall for conditional XOR and other context-gated rules. Compare the pairwise proposer with conditional-dependence tests, sparse Boolean polynomial recovery, decision trees, and a trainable support proposer. Keep family-held-out and state-held-out evaluation separate.

## Claim boundary

This is a diagnostic enhancement to a synthetic Boolean benchmark. It is not a learned neural relation-discovery model and does not establish causal, natural-language, Yi-Xue, or real-world reasoning.
