# Durable verification of M2 Observation receipts

Status: local append-log membership and integrity check; not a cryptographic trust attestation.

## Problem

A caller can construct the public `ObservationReceipt` dataclass. Matching its event ID and record digest to a supplied Observation does not prove that the referenced event was ever committed to ZPCM. The receipt's payload digest and sequence must be checked against the authoritative event stream.

## Change

- `PersistentM2ObservationStore.verify_observation_receipt` locates the exact event at the receipt sequence using a one-event keyset read.
- It checks event ID, event type, scope, payload digest, event schema/kind, body digest, decoded record equality and current M1 EvidenceRef resolution.
- `ObservationCandidatePipeline` now requires the observation store and calls this verifier before invoking the extractor.
- Observation and candidate stores must share the same scope.

## Security boundary

This closes the accidental/forged-receipt gap within the local ZPCM persistence boundary. It does not authenticate a remote caller, prove that a trusted observer produced the content, provide tamper evidence against an attacker who can rewrite the SQLite database and recompute hashes, or grant E09 authorization. Those require a separately deployed authenticated service and cryptographic attestation protocol.

The E09 v2 verification receipt inspected in the security branch is audience-bound to `e12a6-lifecycle-writer`; it must not be repurposed as a generic M2 observation receipt.
