# E12-A1 — Typed Predicate Induction Baseline

Status: research prototype and falsifiable protocol. This is not a neural learner or evidence of open-world concept discovery.

## Question
Can a learner propose executable, typed predicates from observed feature values without receiving a fixed list of candidate predicates?

## Scope
The first implementation supports numeric features (GE, GT, LE, LT thresholds, EQ, integer parity), categorical equality, binary outcomes, Train-only proposal, independent labelled Gate selection, and explicit candidate-budget exhaustion. It excludes temporal, geometric, relational, latent-factor, and Yijing-inspired proposal families until this baseline is stable.

## Protocol
1. The environment declares a feature schema and provides Train and Gate examples.
2. The proposal engine derives thresholds from adjacent unique Train values, plus equality and parity candidates.
3. Candidates are type-checked and deterministically canonicalized.
4. Train consistency filters candidates.
5. Independent Gate evidence selects a unique candidate, preserves ambiguity, or rejects all candidates.
6. The learner receives no evaluator-truth object and no locked Test payload.

Statuses:
- IDENTIFIABLE: exactly one generated candidate survives Train and Gate.
- AMBIGUOUS: multiple generated candidates survive.
- INCONSISTENT: no candidate survives.
- BUDGET_EXHAUSTED: the generated candidate set exceeds the declared evaluation budget.

## Important limitation
The implementation discovers predicates only within a finite declared grammar. IDENTIFIABLE means unique within this grammar and supplied evidence, not globally unique over all possible predicates. The budget policy is conservative: if the candidate set exceeds budget, it abstains rather than selecting from a biased partial search.

## Next experiments
- Compare typed proposal against fixed-feature, random-proposal, and exact-search baselines at equal candidate-evaluation budgets.
- Add hard negatives and nuisance features.
- Separate feature-family OOD from composition OOD.
- Measure candidate recall, false discovery, abstention coverage, and Gate overfitting.
- Add evaluator process isolation and locked Test only after the learner interface is stable.
- Test Yin/Yang complement, four-state partition, and trigram factorization against capacity-matched generic controls. Never hard-code these correspondences as truths.

## Run
python -m unittest tests.test_e12a1_typed_predicate_induction -v
python -m prototype.e12a1_typed_predicate_induction
