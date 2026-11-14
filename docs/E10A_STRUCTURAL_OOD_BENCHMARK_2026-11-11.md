# E10-A Structural OOD Benchmark v1 (2026-11-11)

## Target capability

Test compositional generalization over context constraints, not merely object identity transfer. The hidden rule is a conjunction of two categorical context predicates plus the existing participant role-value constraint.

## Support construction

Support contains:
- three positive rows with both required context values, using distinct object instances;
- a negative row violating only the first context condition;
- a negative row violating only the second condition;
- a negative row violating both conditions.

Thus the learner can identify the two context conjuncts from Support without seeing evaluator truth.

## Query construction

Query uses a separately generated object pool. It recombines the two known context dimensions into all four value combinations, and includes a role-composition near-miss. The positive/negative labels and mechanism specification remain in the evaluator payload only.

## Hypothesis grammar change

The E10-A candidate now represents context as a conjunction of all context key/value pairs common to Support positives. Each candidate must fit every Support positive and reject every Support negative. This prevents collapsing two necessary conditions into one disjunctive or arbitrary single-key rule.

## Scope and caveats

This is still a finite, hand-specified categorical DSL. It tests recombination of known context dimensions, not invention of new context dimensions, unknown relation symbols, open-world ontology formation, causal discovery, or general intelligence. It is a stronger structural test than object-disjoint transfer but remains synthetic.

## Validation status

Tests are authored. They have not been run locally; no CI pass or empirical score is claimed.
