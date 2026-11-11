# CSG-GCR to E12-A6 Lifecycle Adapter v0.1

Date: 2026-11-11
Status: integration prototype; exact-head CI pending.

## Purpose

Project a complete Typed CSG-GCR candidate into the existing E12-A6 native
Candidate contract and read-only CPG-EI interchange DTOs. This closes the
proposal-to-lifecycle boundary without creating a second lifecycle state
machine.

## Mapping

- Candidate identity is a deterministic digest of the typed semantic
  definition, parent state, and (when present) merged branch-state digest.
- Proposal IDs, branch lineage, evidence references, temporal interval, and
  branch-merge provenance are retained in the canonical expression.
- CSG-GCR's numeric score remains `raw_score` metadata with explicit
  `uncalibrated_ranking_score` semantics. It is never mapped to uncertainty
  or confidence; E12-A6 uncertainty remains 1.0 until calibrated evidence
  justifies another value.
- Evidence references are unioned from typed hyperedges, branch delta events,
  and branch-merge authorization receipts.
- The native candidate enters E12-A6 as OBSERVED. The caller must add it to
  LifecycleLedger and use an explicit PROPOSE action to transition it.

## Ownership

E12-A6 LifecycleLedger remains the sole lifecycle authority. The adapter does
not add evidence records, authenticate E09 authorization receipts, commit or
reveal evidence, mutate candidate state, or persist lifecycle events. The
read-only E12-A6 interop adapter remains the sole DTO projection path.

## Tests

Tests cover deterministic projection, shared DTO identity/digest, score versus
uncertainty separation, stable candidate identity across score changes,
explicit OBSERVED-to-PROPOSED lifecycle transition, branch-delta provenance
projection, and invalid parent/scope/version rejection.

## Limitations

This is a trusted in-process adapter over existing prototypes. Durable E12-A6
lifecycle event persistence and direct E09 evidence authorization remain
separate integration requirements.
