# YJ-10.5: Symmetry Evolution and Hysteresis

## Goal

Turn YJ-10.4 per-snapshot exact slot permutation groups into temporal events, while avoiding permanent cognitive-state updates from one-off topology perturbations or environmental changes.

## Mechanisms

- PERSIST: the group is unchanged; no structural change event is emitted.
- SYMMETRY_BREAK: the target group is a proper subgroup of the previous group.
- SYMMETRY_EXPAND: the target group is a proper supergroup.
- RECONFIGURE: group membership changes without subset/superset containment.
- CONTEXT_SHIFT: context, attributes, validity interval, or domain changes. The event is UNCERTAIN and no structural symmetry claim is made across the boundary.

## Hysteresis

For each group change, count consecutive snapshots in which the target group remains unchanged under the same coordinate frame and environmental conditions.
- At least min_consecutive_target_snapshots: CONFIRMED.
- Below threshold: CANDIDATE.
- Environment/domain changes interrupt confirmation.
- Steps must increase, but need not be numerically contiguous. Consecutive means adjacent complete snapshots in the input sequence.

## Data contract

- YJ-10.4 observations now preserve step and domain metadata.
- A lineage is identified by relation type, arity, slot frame, entity-type frame, and symmetry policy.
- Context, attributes, validity interval, and domain are environmental conditions. A change emits a boundary event.
- Each exact group is checked for identity, inverse closure, and composition closure.
- Multiple observations in one lineage at the same step fail closed.

## Limits

- This is structural group stability, not semantic or causal interpretation.
- CONFIRMED means only that the deterministic snapshot hysteresis threshold was met; it is not statistical confidence or causal confirmation.
- No automatic memory write or operator-weight update is performed.
- Incomplete snapshots remain rejected by YJ-10.4; this module does not treat missing data as symmetry breaking.

## Tests

Persistent symmetry break, transient candidate, expansion, incomparable-group reconfiguration, context/domain boundaries, persistence, non-contiguous step values, duplicate steps/evidence, invalid group, and threshold validation.
