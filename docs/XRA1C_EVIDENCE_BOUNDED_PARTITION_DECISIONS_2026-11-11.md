# XRA-1c: Evidence-Bounded MERGE / SPLIT / UNRESOLVED

Date: 2026-11-11
Status: protocol and reference implementation added; tests not executed here
Branch: research/triadic-representation-arbitration-2026-11-11

## Research objective

Prevent a representation learner from converting absence of observed
counterexamples into an unjustified equivalence claim. Pair decisions must
distinguish positive counterevidence, sufficient scoped coverage, and missing
evidence.

## Learner-visible evidence contract

A paired challenge record contains only:
- a declared action chosen from the public task interface;
- a unique trial identifier;
- the observed immediate outcome on each side;
- the learner's observable successor signature on each side.

It must not contain evaluator-only latent state IDs, generator family labels,
the oracle partition, true K, future observations, or hidden transition tables.
The evaluator may retain those privately for scoring.

Successor signatures are model-visible summaries produced under the same
frozen representation version. If their schema or version differs between
sides, the comparison is invalid and the challenge must be marked unresolved
by the calling protocol; it must not be silently coerced.

## Decision rule for deterministic XRA-P1

For the declared action set A and minimum paired repetitions m:

- **SPLIT** if any paired record has unequal immediate outcomes or unequal
  successor signatures. A single valid counterexample is sufficient to
  reject the current merge proposal.
- **MERGE** only if every action has at least m paired records and every
  observed pair matches on both fields.
- **UNRESOLVED** otherwise, including any missing action coverage or
  insufficient repetitions.

A detected counterexample takes precedence over incomplete coverage. The
decision can therefore be SPLIT even if some other actions were never tested.

A MERGE is deliberately scoped to the declared actions, tested successor
signature schema, deterministic protocol, and observed horizon. It is not a
proof of global, stochastic, or infinite-horizon equivalence.

## Reference implementation

- `prototype/xra_partition_decision.py`: immutable evidence/result records
  and conservative deterministic decision function.
- `tests/test_xra_partition_decision.py`: missing coverage, scoped merge,
  immediate and successor counterexamples, split precedence, repetition
  threshold, duplicate trial IDs, undeclared actions, and invalid arguments.

The function is a protocol reference, not a statistical learner. XRA-P2 must
replace exact equality with a preregistered statistical procedure including
uncertainty, multiple-comparison control, stopping rules, and calibration.
Do not retrofit stochastic confidence claims into this deterministic helper.

## Versioning and evidence integrity

Every challenge must be bound by the surrounding task manifest to:
- a task and episode identifier;
- representation version and successor-signature schema version;
- action protocol and observation horizon;
- train/development/locked-test split;
- measurement cost and missingness status.

A representation change invalidates direct comparison across versions unless
an explicit, tested migration map is supplied. Censored or missing outcomes
are not matching evidence and do not count toward the repetition threshold.
Duplicate trial IDs are rejected to prevent accidental double counting.

## Known limitations and next gates

1. Current helper accepts already paired records; it does not schedule or
   randomize paired challenges.
2. Exact equality assumes deterministic XRA-P1 observations.
3. Successor signatures are supplied by the learner-facing representation;
   the evaluator must independently score them without leaking latent labels.
4. The current helper does not calculate confidence intervals or prove
   identifiability.
5. Add task-manifest validation and challenge randomization before any
   adaptive K selector is trained.
6. Then connect E12-A8 action selection to competing partition hypotheses,
   ensuring action-selection cost is included in matched budgets.

## Falsification requirement

Include observationally equivalent latent states and remove the only
discriminating action in separate benchmark variants. The system must return
MERGE only within the declared observed scope, and UNRESOLVED when required
coverage is absent. In noisy variants, this deterministic helper is not
applicable; a calibrated XRA-P2 procedure is required.
