# E09 Authority and Verifier Service Contracts v1

Status: implemented reference service facades; not a production process boundary.

## Scope

This increment adds two narrow service contracts around the existing E09 reference store:

- Authority service: accepts a transport credential, resolves it through a configured workload authenticator, checks the authenticated workload's role and scope, and derives the event role itself. Evaluator reveal writes and authorizer grant issuance are separate methods.
- Verifier service: verifies branch-merge grants through the existing strict E09 resolver and obtains verification time from a server-owned clock. A request cannot supply the verification time.

The authorizer's issuer_id is taken from the authenticated workload identity, not from a request payload. The authority constructs the complete v2 envelope, derives issue/expiry timestamps from its server-owned clock, enforces a maximum grant lifetime, obtains the signature through a signer interface (intended for HSM/KMS integration), and appends with expected-sequence compare-and-swap.

## Invariants covered

1. Unknown credentials fail authentication.
2. Learner workloads cannot append evaluator reveals.
3. Role and scope checks happen before E09 writes.
4. Event actor role is derived by the service, not caller input.
5. Grant issuer identity is mapped from the authenticated workload.
6. Grant signing covers the authority-generated envelope, including identity metadata and the reserved sequence.
7. Grant lifetime is bounded by authority policy and timestamps are server-generated.\n8. Concurrent append races fail through the existing E09 sequence CAS.
9. Verification time is server-owned; caller-provided time is rejected.
10. Verifier still checks E09 reveal ancestry, strict v2 schema, audience, exact scope/parent/branches/evidence, expiry and Ed25519 signature.

## Deployment boundary — still not solved

These Python classes are not an authentication boundary against code in the same process. A caller with direct access to SQLiteEvidenceStore, the database file, or the service object's private attributes can bypass this facade. The authenticator and signer are trusted injected dependencies; their production implementations are not included here.

Production must still:

- run E09 authority and verifier in separate service processes under distinct OS identities;
- use mTLS or equivalent workload identity and enforce method/scope authorization at the IPC endpoint;
- keep private issuer keys in an HSM/KMS and distribute public trust bundles out of band;
- deny learner filesystem access to the E09 database and raw-label vault;
- issue a short-lived, audience-bound, cryptographically authenticated verification receipt for E12-A6 rather than passing an in-process Python object;
- provide trusted time, nonce/replay consumption, key-rotation overlap and revocation epochs;
- move E12-A6 writes behind a sole writer service and independently checkpoint ZPCM to detect rollback.

## Test status

The new unit tests use an in-memory credential authenticator, ephemeral Ed25519 keys and a fixed test clock. They validate policy wiring and cryptographic integration only; they do not prove mTLS, HSM, OS isolation, trusted wall-clock operation or remote anti-rollback.
