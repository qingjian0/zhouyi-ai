# E12-A4-P — Counterexample-Gated Parameterized Operator Expansion

Status: finite symbolic prototype; source and tests are committed on a research branch. Test execution and CI are not yet verified.

## Research question

When the current A3 relational grammar cannot explain a training counterexample, can a bounded meta-operator propose a new parameterized relation, while keeping proposal evidence separate from validation evidence?

## Trigger boundary

The caller supplies `counterexample_pairs`: feature pairs implicated by an A3 residual/counterexample diagnosis. A4 expands only those pairs. The present prototype does **not** implement the upstream residual attribution algorithm; the pair list is an explicit interface and must be audited as Train-derived. Gate and Test values must never influence this trigger.

## Operator family

For each flagged numeric pair `(x, y)`, compute `d = abs(x - y)` on Train. For each adjacent pair of distinct observed distances `lo < hi`, propose:

`ABS_DIFF_GT(x, y, threshold=(lo+hi)/2)`

The operator predicts 1 iff `abs(x-y) > threshold`. Candidate thresholds and boundary evidence IDs come from Train only. The operator is symmetric by construction; no directional or causal meaning is implied.

This expands the grammar beyond A3's fixed LT/GT/EQ/SAME_PARITY pair predicates, but it is only **bounded parameterized operator-family expansion**. It is not arbitrary semantic invention or open-ended concept creation.

## Validation and abstention

- Train filters candidates for exact consistency.
- Independent Gate filters the Train-consistent set.
- Exactly one survivor: `IDENTIFIABLE_WITHIN_A4_OPERATOR_FAMILY`.
- Multiple survivors: `AMBIGUOUS`, no selection.
- No survivor: `INCONSISTENT`, no selection.
- Candidate budget truncation: `BUDGET_EXHAUSTED`, no selection.
- Train/Gate evidence-ID overlap, malformed schema, non-finite values, booleans as numbers, and invalid pair triggers fail closed.

A locked Test split is intentionally absent from the learner API. It must be held by an external evaluator and used only after model selection.

## Provenance

A selected operator records:
- stable operator ID and family;
- parent primitive IDs;
- Train boundary evidence IDs supporting the threshold gap;
- Gate validation evidence IDs;
- A3-triggered feature pairs;
- revision identifier.

The boundary IDs are not a complete causal explanation; they identify the adjacent observed distance values that define the threshold interval.

## Complexity

For P flagged feature pairs and N Train records, distance collection is O(PN). Sorting unique distances costs O(PN log N) in the worst case. If a pair has U distinct distances, it proposes at most U-1 thresholds. Evaluation costs O(C(N+G)) for C candidates and G Gate records.

Candidate budget currently limits evaluation after candidate construction; it does not cap threshold enumeration or memory. A production budget must separately cap generation, evaluation, and retained provenance.

## Required falsification experiments

1. **A3 vs A4:** same streams, splits, seeds, and prediction checkpoints; compare fixed A3 grammar with A4 expansion.
2. **Trigger ablation:** correct A3 residual pairs vs random pairs vs all numeric pairs.
3. **Capacity/compute matching:** cap generated candidates and total candidate evaluations independently.
4. **OOD:** unseen thresholds, unseen numeric scales, unseen feature pairs, noisy labels, and distribution shift.
5. **Metrics:** prequential accuracy, coverage, abstention, false expansion rate, operator count, candidate-generation cost, evaluation cost, wall time, and peak memory.
6. **Leakage audit:** verify trigger attribution uses Train only; Gate only validates; locked Test remains evaluator-owned.

## Tests authored

- discovers an ABS_DIFF_GT operator not expressible by A3's listed relation family;
- candidate proposal invariant to changed Gate values;
- only A3-flagged pairs are expanded;
- Gate rejects a Train-fit false operator;
- multiple surviving operators cause abstention;
- candidate budget causes abstention;
- provenance includes parents and evidence IDs;
- no observed threshold gap creates no candidate;
- Train/Gate evidence overlap is rejected;
- missing trigger and invalid numeric/budget types fail closed.

Command: `python -m unittest tests.test_e12a4_counterexample_operator_expansion -v`

No local execution or CI success is claimed in this commit.
