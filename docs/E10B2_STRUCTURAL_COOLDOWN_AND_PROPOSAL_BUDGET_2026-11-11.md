# E10-B2: Structural Cooldown and Bounded Proposal Search

## Changes

This follow-up adds two explicit controls to the E10-B concept reviser:

- `revision_cooldown`: minimum number of accepted observation steps between revisions of the same concept node. A node split at step t cannot be merged (or re-split after a merge) before the cooldown expires.
- `proposal_budget`: maximum number of feature-key proposals evaluated per accepted observation. Once exhausted, search stops and no partial split is committed for the current node proposal.
- Snapshots expose observation step, proposal evaluations, configured budget, and whether the budget was exhausted.

## Why cooldown is not statistical validation

Cooldown is a temporal anti-churn guard, not evidence that a boundary is correct. It can delay a valid merge as well as prevent a premature reversal. It is not a substitute for held-out predictive evidence, confidence calibration, or a sequential hypothesis test.

The current split criterion (in-sample Gini gain) and merge criterion (sibling target-rate spread) are different statistics. Their numeric thresholds must not be described as a shared hysteresis margin. A later calibrated design should define a common predictive utility or MDL objective and use distinct enter/exit thresholds on that objective.

## Budget semantics

The proposal budget is per accepted observation and counts feature keys evaluated by `_best_split`. Exhaustion is fail-closed for the current split search: no incomplete candidate is committed. This is not yet a global transaction across all nodes visited in one observation; earlier independent node revisions in that observation are not rolled back. Snapshot telemetry makes the bound auditable.

## Regression tests

- A high-cardinality nuisance feature consumes the limited proposal budget before a useful feature is reached; the learner reports exhaustion and does not commit a partial split.
- A split cannot be immediately reversed by a merge before the configured cooldown; merge becomes eligible after the interval.

## Next experiment

Replay identical prequential streams with matched compute for five arms: no revision, split-only, merge-only, split+merge, and random-boundary proposals. Report per-seed predictive accuracy, coverage, selective accuracy, false split/merge rate, concept count, cumulative complexity, revision churn, proposal evaluations, and runtime.

Add held-out entity and feature-combination tests. Separate the proposal-generation mechanism from the evidence used to validate and commit a proposed boundary. A future Zhouyi-inspired prior must be compared against random proposals under the same proposal budget.

## Interpretation

These controls improve bounded search governance and temporal stability. They do not establish that the learner discovers semantic concepts autonomously, learns raw features, or benefits from Zhouyi priors.
