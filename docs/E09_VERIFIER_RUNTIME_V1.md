# E09 Verifier Runtime v1

Status: initial read-only process boundary implementation; not the complete #282 production deployment.

## Process and file boundary

- The Verifier runs under its own OS UID.
- It reads an immutable, Authority-published SQLite snapshot, never the live Authority database.
- The snapshot directory is owned by Authority, group-owned by a dedicated Verifier reader group, mode 0750; the snapshot file is mode 0440.
- SQLite opens the snapshot using URI `mode=ro` and enables `PRAGMA query_only=ON`.
- The Verifier UDS is owned by the Verifier process and exposes only `issue_verification_receipt@1`.
- Linux `SO_PEERCRED` UID mapping is server-side. Each UID receives an explicit scope allowlist; request JSON cannot assert an identity or expand scope.
- The Verifier uses its own receipt signer and pinned Authority signature verifier. Production private-key storage must be an HSM/KMS-backed signer.

## Snapshot publication contract

The snapshot must be a transactionally consistent copy produced by Authority's SQLite backup API after a committed event boundary. Publish by writing a temporary file, fsyncing it, validating its schema, setting the Authority owner / Verifier-reader group and 0440 mode, then atomically renaming it into place. Never copy a live WAL database file with ordinary filesystem copy.

The runtime intentionally does not implement snapshot publication or anti-rollback. A production composition root must provide a signed monotonic snapshot manifest (generation, database digest, event high-water marks) and reject stale generations before starting the Verifier. This is a remaining #282 acceptance gate.

## RPC

Request schema is closed and versioned by the operation name. The only operation in v1 is `issue_verification_receipt@1`; fields are `episode_id`, `authorization_ref`, `parent_state_ref`, `branch_ids`, `scope`, `learner_track`, and optional `candidate_evidence_refs`. Unknown fields fail closed. The transport applies bounded newline-delimited JSON frames and deadlines.

## Limitations

This increment establishes a distinct Verifier process entrypoint and a read-only SQLite snapshot boundary. It does not by itself prove the full Authority → Verifier → Writer deployment, automated snapshot freshness, KMS key rotation/revocation, or cross-process kill/restart recovery. Keep #282 open until those gates have end-to-end integration tests.
