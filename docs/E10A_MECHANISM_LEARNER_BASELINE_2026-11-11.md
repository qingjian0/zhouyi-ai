# E10-A Mechanism Learner Baseline (2026-11-11)

## Research question
Can a learner infer a compact relation predicate from labelled Support data and transfer it to unseen object identities, without receiving the latent mechanism specification or evaluator truth?

## Candidate language v0
A candidate is a conjunction of relation symbol, one categorical object feature, an unordered set of distinct required values (one per participant), and one context key/value gate. Participant order is ignored because observations are shuffled.

Candidates are generated from positive Support observations. Every candidate must explain all positives and reject all negative Support observations. The learner retains all compatible candidates rather than selecting one arbitrarily.

## Decisions and revision
- `PREDICT`: all compatible candidates agree on the current observation.
- `ABSTAIN_AMBIGUOUS`: compatible candidates disagree.
- `ABSTAIN_INCONSISTENT`: no candidate covers the relation.
- Every prediction includes candidate-set hash and model version.
- After reveal, only the current Query row and its target are appended, then the candidate set is re-induced.

## Boundaries
This is finite DSL identification on a synthetic generator. It is not open-world ontology formation, new relation-family invention, unrestricted compositional generalization, or evidence of general intelligence. Exact consistency filtering assumes noiseless labels.

## Controls to implement next
1. Frozen: never revise after Query reveals.
2. Incremental: revise after each reveal.
3. Batch refit: recompute from Support plus all revealed Query rows after each step.
4. Same seed, row order, candidate language, and compute budget; report accuracy, coverage, abstention, candidate count, revision count, and cost.
5. Add YiXiang priors only as an isolated ablation after the no-prior baseline.

## Validation
Tests are authored but have not been executed here. No CI pass or empirical benchmark result is claimed.