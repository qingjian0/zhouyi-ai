# E12-A3 — Relational Primitive Induction

Status: finite typed relational grammar prototype. This is a controlled extension of E12-A1's unary predicate grammar, not unrestricted concept discovery.

## Research question

Can the learner propose a relation between two observed features when no single-feature predicate is sufficient, while keeping candidate generation separate from independent evidence validation?

## New primitive family

For pairs of same-typed features, generate:
- numeric: LT, GT, EQ; additionally SAME_PARITY when both Train columns contain integers;
- categorical: SAME and DIFFERENT.

Pairs follow schema order and candidates are canonicalized. Candidate generation uses schema and Train only. Gate values are used only to filter Train-consistent candidates. The learner receives no evaluator truth or locked Test payload.

## Inference statuses

- IDENTIFIABLE_WITHIN_RELATIONAL_GRAMMAR: exactly one candidate survives Train and Gate.
- AMBIGUOUS: multiple candidates survive; no selection.
- INCONSISTENT: no candidate survives.
- BUDGET_EXHAUSTED: candidate budget truncates search; no selection.

Uniqueness is only relative to this finite grammar and supplied evidence.

## Complexity

For F features, candidate generation is O(F²) pairs, with up to four numeric relations per numeric pair or two categorical relations per categorical pair. Evaluation is O(C * N * 2), where C is the candidate count and N is the number of Train/Gate examples.

## Tests authored

- numeric cross-feature order relation discovery;
- categorical same/different relation;
- Train-only candidate generation boundary;
- Gate rejection of a spurious Train-fit relation;
- budget abstention;
- mixed-type exclusion;
- bool-vs-number type safety;
- ambiguity handling.

## Limitations and next falsification

- No temporal, causal, higher-order, geometric, or latent relation operators.
- The grammar is hand-specified; it does not invent arbitrary operator semantics.
- Feature selection, missing values, continuous noise, and calibration are out of scope.
- Compare against unary E12-A1 at equal candidate-evaluation budgets, random pairwise operators, and exhaustive finite relational search.
- Test relation-family OOD and composition OOD separately.
- Only after generic relational induction is validated should Yin/Yang complement, four-state transitions, trigram factorization, and hexagram composition be added as capacity-matched inductive-bias arms.

## Run

`python -m unittest tests.test_e12a3_relational_primitive_induction -v`
