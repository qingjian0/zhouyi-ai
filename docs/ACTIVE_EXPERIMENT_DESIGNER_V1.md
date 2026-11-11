# Active Experiment Designer v1

## Scope

This component selects among candidate experiments authored by a researcher.
It is not an autonomous scientific theorist and does not generate hypotheses,
estimate real information gain, execute experiments, or preregister protocols.

## Candidate contract

Each candidate must identify:

- `candidate_id` and the exact `hypothesis_id`
- `covers`: one or more gates from `ood`, `control`, `replication`, `parameter_match`
- `estimated_compute`: caller-supplied resource estimate
- `expected_discrimination`: caller-supplied heuristic in [0, 1]
- `preregistration_ref` and `preregistered=true`
- `design`: finite JSON object containing the proposed protocol/configuration

Unregistered, mismatched-hypothesis, irrelevant, and over-budget candidates are
excluded with explicit reasons.

## Selection rule

Among feasible candidates, rank lexicographically by:

1. Number of currently required gates covered (descending)
2. Declared expected discrimination (descending)
3. Estimated compute cost (ascending)
4. Candidate ID (ascending, deterministic tie-break)

The output preserves alternatives, exclusions, and a deterministic input
digest. The algorithm deliberately does not collapse these dimensions into an
opaque score.

## Safety and scientific limits

- The caller, not this module, defines missing evidence gates.
- Expected discrimination is not a probability, measured information gain,
  or validated scientific quantity.
- The selector does not establish that the proposed split is truly OOD.
- It does not estimate power, correct multiple comparisons, or prevent data
  leakage by itself.
- Selection is a recommendation only; execution and preregistration remain
  separate explicit steps.
