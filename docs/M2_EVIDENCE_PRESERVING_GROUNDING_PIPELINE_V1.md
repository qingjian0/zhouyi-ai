# M2 Evidence-Preserving Grounding Pipeline v1

## Purpose

This pipeline adds a separate identity-resolution stage after semantic candidate extraction:

`persisted UNRESOLVED candidate -> resolver decision -> immutable grounded-state revision`.

It does not infer truth, rewrite the original observation, or create another event ledger.

## Authoritative input gate

Every input candidate is re-read through the candidate store's indexed event-ID lookup. The supplied object must exactly equal the persisted, digest-checked, evidence-verified record. Unpersisted candidates and caller-modified copies are rejected before the resolver runs.

The candidate store now exposes `get_candidate(record_id)` and `get_receipt(record_id)` using one indexed ZPCM event lookup. Reads validate event identity, body digest, sequence, and current M1 evidence; they do not replay the full candidate stream.

## Resolver contract

The injected resolver returns a typed decision bound to the exact candidate ID and exact immutable M1 EvidenceRef tuple. A `GROUNDED` result must provide a canonical key and a matched surface form that occurs in the candidate's source forms. Non-grounded decisions cannot carry canonical identity fields.

- `UNRESOLVED`: no revision is appended.
- `PARTIALLY_GROUNDED`, `CONFLICTED`, `REJECTED`, and `STALE`: preserved as distinct immutable revisions.
- `GROUNDED`: a new immutable revision records the canonical key.
- Truth and epistemic status are preserved; identity resolution never promotes truth.

The full bounded input batch and every resolver decision are validated before the first write. Output revision IDs are deterministic from candidate digest, resolver identity/version, decision, and source refs. Appends remain individually durable; a failed append loop can leave a prefix, and retries must use identical IDs/content.

## Limits

This module provides a resolver boundary, not an entity-linking model or registry. Registry authorization, resolver quality, collision handling, and calibration must be validated independently. A successful test proves provenance-safe state transition, not semantic correctness.
