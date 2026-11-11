# Production Trust Boundary v1 — Architecture Decision Record

Status: proposed engineering contract; research/reference implementation only.
Parent: PR #231 (Ed25519 issuer keyring and cross-branch integration).
This document does not claim that the current prototype is production-isolated.

## 1. Verified baseline

At PR #231 head cea92a99786018bfc62a46837bd19b9ee92cf6e1:

- The concrete Ed25519 verifier checks a pinned issuer public key and rejects unknown/revoked issuers, unsupported algorithms and invalid signatures.
- The cross-branch integration test exercises signed authorization, typed candidate composition, E09 evidence resolution and ZPCM lifecycle ingestion.
- GitHub Actions run 43050925777 reports success; its returned job summary contains a successful unit-tests job.
- E09 and ZPCM remain SQLite-backed reference stores. The current code explicitly does not provide OS process isolation, database-host authentication, anti-rollback, or remote tamper-evident replication.

## 2. Threat model and trust domains

The system must distinguish five principals. A Python object, function argument, database column or caller-supplied string is not an authenticated principal.

| Principal | Trust | Allowed operations | Forbidden operations |
|---|---|---|---|
| Evaluator / E09 authority service | Trusted, separately deployed | Reveal evidence; issue signed merge grants; append E09 events | Mutate learner state directly |
| Learner / CSG-GCR workers | Untrusted with respect to labels and authorization | Read scoped redacted evidence; propose typed candidates and branch deltas | Read raw labels; issue grants; write E09 or ZPCM |
| E09 verifier service | Trusted verifier | Read E09 events; verify envelope, evidence ancestry, signature, expiry and revocation | Sign grants; mutate learner lifecycle |
| E12-A6 lifecycle writer | Trusted state-transition authority | Revalidate command; apply legal transition; append one atomic ZPCM event bundle | Accept caller-created verified objects as proof |
| ZPCM readers / analytics | Read-only | Query bounded projections and replay authorized scopes | Append, rewrite or delete lifecycle history |

The OS account and process boundary is the enforcement mechanism. Module-private names, dataclasses, Python seals and SQLite conventions are not security boundaries against code running in the same process or with the same filesystem permissions.

## 3. Required service topology

    Evaluator / Authorizer
            |
            | authenticated E09 write API
            v
    +-----------------------+       signed, scoped verification receipt
    | E09 Evidence Authority| -----------------------------------+
    | DB + issuer key policy|                                    |
    +-----------------------+                                    v
                                                       +----------------------+
    Learner / CSG-GCR workers -- typed proposal ------>| E12-A6 Lifecycle API |
       (no raw labels, no DB)                           | sole write authority |
                                                       +----------+-----------+
                                                                  |
                                                       one DB transaction
                                                                  |
                                                                  v
                                                       +----------------------+
                                                       | ZPCM append-only log |
                                                       | readers are read-only|
                                                       +----------------------+

Deployment requirements:

1. Run E09 authority, E09 verifier, learner workers and E12-A6 writer under distinct OS identities or containers.
2. Do not mount E09 or ZPCM database files into learner workers. Do not pass SQLite connections or filesystem paths over IPC.
3. Authenticate service-to-service IPC (mTLS or equivalent workload identity); authorize each method and scope independently.
4. Give learner workers only read-only, redacted evidence DTOs and a proposal-submission endpoint.
5. Permit exactly one logical E12-A6 write service per database. SQLite transaction locking remains a storage concurrency guard, not a substitute for caller authentication.
6. Make read/analytics credentials read-only at both API and filesystem/database layers.

## 4. Authorization contract v2

The current PR #231 signature input is canonical episode ID + event ID + payload (with the signature field omitted). It does not cryptographically bind every envelope field that the E09 resolver later inspects.

Before production, define a domain-separated canonical signing statement that binds at minimum:

- protocol version and a fixed domain string (for example zhouyi:e09:branch-merge:v2);
- episode ID, event ID, event type and payload schema;
- authenticated issuer identity and actor role;
- exact ordered causation references;
- scope, parent state digest, exact branch IDs and evidence references;
- issued-at, expires-at, audience / target lifecycle service and nonce;
- the complete authorization payload excluding only the signature bytes.

The verifier must reject duplicate/ambiguous encodings, unknown fields where the schema is closed, unsupported versions, wrong audience, stale/replayed nonces, revoked keys and expired grants. Signature verification must be performed by the verifier service using an immutable, versioned trust bundle. The trust-bundle ID and revocation epoch must be recorded with every decision.

A successful verification result must be a short-lived, audience-bound receipt that the E12-A6 service can independently validate or revalidate. A Python VerifiedBranchMergeAuthorization instance is useful as an in-process type guard only; its private factory/seal must never be treated as a cross-process security credential.

## 5. Trusted time, key lifecycle and replay

- Production verification time comes from the verifier service's trusted clock, not a caller-provided now argument.
- Define maximum grant lifetime, permitted clock skew, nonce uniqueness and replay-retention policy.
- Key rotation supports explicit key IDs and an overlap window; revocation has an auditable effective time and monotonic revocation epoch.
- Historical verification records retain the exact public-key fingerprint, trust-bundle ID, policy version, verification time source and result.
- Emergency revocation must invalidate new uses immediately while preserving the ability to explain prior decisions.

## 6. E09 evidence isolation

Current SQLiteEvidenceStore.append_event accepts actor_role as a function argument. That field is metadata, not proof of caller identity. In production:

- E09 writes are accepted only through the authority service after authenticating the workload and checking its role/scope policy.
- Learner workers cannot call the append API or open the evidence database.
- The evaluator-only reveal path and authorizer-only grant path are separate permissions.
- Redaction happens inside the trusted boundary before data crosses IPC.
- Evidence references are resolved server-side; a caller-supplied world-family or evidence-role assertion is not trusted without policy validation.

## 7. E12-A6 / ZPCM single-writer and atomicity

The reference implementation already batches candidate + evidence lifecycle events in one SQLite transaction and checks the expected sequence. Preserve that invariant, but move the authority to a service boundary:

- The lifecycle service owns the only writable ZPCM connection.
- Every command includes an idempotency key, expected candidate version, expected stream sequence, caller identity, scope and authorization receipt.
- Validate all evidence and state transitions against a staged copy before opening the write transaction.
- Commit the complete event bundle atomically; publish the success receipt only after COMMIT.
- On stale sequence, conflict or storage error, reject without partial events and require a fresh read/revalidation.
- Startup replay validates sequence continuity, event schema, payload digest and legal transition history before serving writes.
- A successful transaction receipt is not issued if the process crashes before durable commit confirmation.

## 8. Tamper evidence and rollback resistance

A per-event SHA-256 digest detects accidental corruption only when the expected digest is independently trusted. It does not prevent an attacker with database write access from editing both payload and digest, nor restoring an older database snapshot.

Production acceptance requires:

1. A per-scope or per-episode hash chain whose prior hash is included in each signed/committed event.
2. Periodic signed checkpoints exported to an independently administered append-only or WORM store.
3. Monotonic checkpoint sequence / epoch anchored outside the SQLite host.
4. Restore procedure that compares local history with the latest external checkpoint and refuses silent rollback.
5. Backup encryption, least-privilege access, audit logging and tested recovery.

Do not describe a local SQLite database as immutable or tamper-proof.

## 9. Release gates

No production or large-scale training readiness claim until all gates pass:

- [ ] Threat-model review and service identity / scope authorization tests.
- [ ] Envelope-v2 signature vectors and mutation tests for every signed field.
- [ ] Trusted-clock, expiry, skew, nonce replay and revocation tests.
- [ ] Cross-process negative tests proving learner cannot read labels or write E09/ZPCM.
- [ ] Concurrent-writer and crash-injection tests at every transaction boundary.
- [ ] Restart/replay tests from clean backup and corrupted / truncated database.
- [ ] External checkpoint, rollback detection and recovery drill.
- [ ] Key rotation overlap, emergency revocation and historical audit tests.
- [ ] CI validates the exact PR head and records artifact hashes.

Until then, label the system: validated research reference implementation; not production isolated; not anti-rollback hardened.

## 10. Recommended implementation order

1. Authorization envelope v2 and canonical test vectors.
2. E09 authority/verifier service interfaces plus authenticated principal model.
3. E12-A6 writer API and removal of direct learner-side database access.
4. Cross-process integration tests and least-privilege deployment.
5. ZPCM external checkpointing and rollback detection.
6. Only then start controlled cognition/类象/易象 training experiments with separate evidence, gate and locked-test domains.
