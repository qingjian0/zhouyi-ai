# E10-A Primitive Expansion Experiment v1 (2026-11-11)

## Research question

Can a learner add a mechanism hypothesis after the current candidate set has no explanation for a newly observed relation, using only Support evidence and Query labels revealed after prediction commits?

This is the first E10-A step beyond pure candidate elimination. It is deliberately a bounded primitive/feature proposal experiment, not a claim of open-ended concept invention.

## Proposal grammar

A proposed mechanism is a tuple:

- observed relation symbol;
- an attribute key present on every participant in the positive examples;
- an unordered tuple of distinct categorical role values;
- a conjunction of context key/value pairs common to the positive examples.

A proposal must explain every positive example and reject every negative example revealed so far. The learner is not given evaluator truth, mechanism hashes, or future Query labels.

The proposal search is bounded by proposal_budget and max_context_terms. Budget exhaustion fails closed: the learner abstains rather than silently truncating the search and presenting a partial candidate set as complete.

## Sequential protocol

1. The learner receives Support only.
2. It receives the unlabeled Query object table and one Query observation.
3. It predicts or abstains.
4. The runner commits the prediction.
5. The evaluator reveals that observation's label.
6. The learner proposes/revises candidates from Support plus revealed evidence only.
7. The next Query observation is released.

A new relation with no candidate initially produces ABSTAIN_INCONSISTENT. A candidate induced from only positive evidence remains PROVISIONAL; prediction for that relation remains abstained until at least one positive and one negative example provide contrastive evidence.

## Test task

The focused synthetic episode introduces a Query-only relation symbol (aligns) and a Query-only attribute key (texture_class). The Support learner has never seen that relation or feature. Revealed positive evidence can propose a new candidate; a context counterexample tests the conjunction, while role-composition and phase counterexamples test whether the proposal is overbroad.

The test is intentionally finite and hand-constructed. It does not establish discovery of arbitrary feature transformations, new raw sensory primitives, causal structure, or open-world ontologies.

## Baselines and next experiments

Compare under identical episode order, evidence, and proposal budget:

- frozen Support candidate set;
- online candidate elimination only;
- bounded primitive expansion;
- random feature/relation proposal under the same budget;
- later, an independently ablated structural prior (including but not privileged to receive Zhouyi-derived proposal biases).

Report prequential accuracy, coverage, abstention rate, candidate count/trajectory, false expansions, proposal count, compute cost, and budget-exhaustion rate across multiple seeds. The current prototype is a capability probe, not a comparative result.

## Limitations

- Attribute keys and categorical values are supplied by the generator; the learner selects among them rather than inventing raw feature extractors.
- Relation symbols are visible in Query rows; discovering a latent relation from unlabelled perceptual input is not tested.
- Candidate proposal uses accumulated revealed evidence (bounded batch proposal after each reveal), not gradient learning.
- Evaluator and learner still share a trusted Python process in the existing runner. This is not a sandbox or security boundary.
- Tests must be run by CI before any pass claim.
