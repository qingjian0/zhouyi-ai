# E10-A Source-Group Provenance and Split Track

Date: 2026-11-11  
Base: PR #42 head `03f13b701009bac7d99efb6928e70bf298e46ad6`  
Status: implementation and regression tests authored; execution/CI pending.

## Problem

The current participant-set split groups observations by:

`(relation_symbol, unordered_participant_set)`

The generator derives multiple observations from one base role assignment:
- a positive observation;
- a context-negative observation with the same participants;
- role-near-miss observations where one participant is replaced.

A near-miss changes the participant set. It can therefore be assigned to a different partition from the positive observation that generated it. Participant-set disjointness does not guarantee source-instance disjointness.

## Implementation

This branch adds an evaluator-only `source_group_id`:
- generated once per base role assignment;
- shared by its positive, context-negative, and all near-miss observations;
- serialized only in `audit_view()`, never in learner observations;
- validated as a non-empty provenance field.

The task adapter now accepts two explicit policies:

| Policy | Group key | Meaning |
|---|---|---|
| `participant_set` | relation symbol + unordered participants | Existing A-P track |
| `source_group` | relation symbol + evaluator source-group ID | A-S source-instance holdout |

The source-group ID is used only by the evaluator-side splitter. Query and Support observation payloads are still constructed by explicit allowlists and do not expose that ID.

## Required invariants

1. Every generated observation has exactly one evaluator truth row and one source-group ID.
2. All observations derived from the same base role assignment stay in one partition.
3. A-S assignment depends on source-group provenance and seed, not on outcome, validity, violation, template ID, or role mapping.
4. Learner Support/Query rows contain no source-group ID.
5. The existing A-P participant-set policy remains available as a separate comparison track.
6. Group-size histograms and observation counts remain internally consistent.

## Interpretation

A-S prevents the specific positive/near-miss source-instance crossing described above. It does not guarantee object-disjointness: different source groups may still reuse objects. It also does not establish cross-episode mechanism transfer, relation-family OOD, or open-world autonomous discovery.

A-O and A-C remain separate generator-level tasks. They must not be approximated by relabeling or post-hoc filtering of A-P/A-S observations.

## Validation status

Focused tests have been added for source-group completeness, evaluator-metadata mutation invariance, missing provenance, and learner-payload omission. They have not been executed in this environment. No test or CI pass is claimed.
