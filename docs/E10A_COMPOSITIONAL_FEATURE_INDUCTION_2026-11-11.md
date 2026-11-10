# E10-A Compositional Feature Induction (2026-11-11)

## Question

Can a learner construct a discriminative object feature by composing multiple supplied categorical attributes, when no individual attribute separates the roles?

## Representation

An object feature is a conjunction of key/value pairs, for example:

\`(color=red, texture=rough)\`

A relation hypothesis contains an unordered set of role signatures, each role signature being a conjunction over selected object attributes. The learner searches subsets of observed attribute keys up to \`max_feature_terms\`.

## Sequential evidence discipline

The learner receives Support labels and the released Query object table. For each Query row it predicts first, then receives a reveal and revises using only accumulated revealed evidence. Duplicate observation IDs are rejected. Positive-only hypotheses remain provisional until at least one negative example has been revealed for that relation family.

## Adversarial test

The fixture uses three role classes:
- red + rough
- red + smooth
- blue + rough

Color alone aliases the first two roles; texture alone aliases the first and third. The pair distinguishes all three. Additional Query counterexamples independently violate a context conjunct and role composition.

## Limits

- This is symbolic conjunction search over generator-supplied categorical attributes.
- It does not learn raw sensory encoders, continuous feature transforms, latent dimensions, or feature semantics.
- Attribute names and categorical values are visible.
- The proposal grammar is finite and bounded; proposal-budget exhaustion abstains.
- Learner and evaluator still run in one trusted process in the current prototype.
- A successful unit test establishes only this controlled capability, not open-world feature discovery or general intelligence.

## Required comparisons

Compare under identical episode streams and compute budgets:
1. single-attribute primitive expansion;
2. pairwise/three-way compositional feature induction;
3. random attribute-subset proposals;
4. frozen representation / no feature expansion.

Vary latent role signatures, nuisance attributes, missing attributes, context changes, observation noise, and held-out object instances across seeds. Report prequential accuracy, coverage, abstention, candidate complexity, proposal count, budget exhaustion, and wall-clock cost. Zhouyi-derived structural biases must be a separate ablation arm, not embedded in the base learner.


## Multi-seed capability regression

The focused suite now evaluates eight Support seeds and independently permutes the three role-code assignments over the four possible color/texture pairs. Across 48 prequential decisions, the regression requires at least 24 covered predictions, zero errors among covered predictions, and at least 16 abstentions while evidence is insufficient or candidate proposals remain ambiguous. This is a deterministic controlled capability regression, not a broad statistical claim: the relation rule and feature grammar remain fixed, and the Query pattern family is intentionally narrow.
