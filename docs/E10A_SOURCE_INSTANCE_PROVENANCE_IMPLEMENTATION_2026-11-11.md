# E10-A Source-Instance Provenance Implementation (2026-11-11)

## Scope

This branch implements the A-S source-instance split track on top of the label-blind A-P splitter. It is a narrow implementation follow-up; it does not claim object-disjoint transfer, connected-component entity isolation, cross-episode transfer, or open-world discovery.

## Changes

- Add evaluator-only `source_group_id` to each generated `InstanceTruth`.
- Assign one source ID to the base instance before emitting its positive, context-negative, and role-near-miss variants.
- Include provenance only in `audit_view()`; it is absent from `learner_view()`.
- Validate that every evaluator row has a non-empty source ID and that a source group does not span relation symbols.
- Build split components as the transitive closure of two constraints:
  - A-P: same relation symbol and unordered participant set.
  - A-S: same source instance ID.
- Assign whole components to Support or Query using a seeded label-blind shuffle.
- Require at least three independent components per relation after both constraints; fail closed rather than silently falling back to participant-only grouping.
- Add tests for source-variant partition integrity and provenance absence from learner-facing task views.

## Why connected components?

A source group can contain role-near-miss variants whose participant sets differ. Conversely, the same participant set can occur in more than one source group. Grouping by either key alone is insufficient. Unioning observations that share either key, then splitting connected components, preserves both invariants simultaneously.

## Explicitly unresolved

- A-O object-disjointness is not implemented. Support still receives the episode-wide object table, so Query object identities and attributes can remain visible.
- Evaluator truth is still returned alongside learner views by this adapter. A separate evaluator process/service and learner-only serialization boundary are required.
- A-C connected-component-disjoint object/observation graph isolation is not implemented.
- This does not address relation-family OOD, cross-episode mechanism transfer, noise/missingness, finite-DSL identifiability, or learner performance.

## Validation status

- Changed source and tests were fetched back from GitHub and statically inspected.
- Tests have been authored but have not been executed in this environment.
- No GitHub Actions run exists for this branch head at the time of this document.
- No empirical benchmark or autonomous-discovery claim is made.
