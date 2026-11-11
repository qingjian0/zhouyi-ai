# E09 Authorization Envelope v2

Status: implemented reference contract; production deployment remains blocked on authenticated IPC, trusted time, and process isolation.

## Canonical signature statement

The Ed25519 message is canonical UTF-8 JSON with sorted keys and compact separators. The fixed domain is `zhouyi:e09:branch-merge:v2`. The signed statement includes episode ID, event ID, event type, protocol version, payload schema, actor role, exact ordered causation references, integrity metadata, and every authorization payload field except signature bytes, including the sequence number reserved for the authorization event.

Changing any of those values invalidates the signature. The assigned sequence number and creation timestamp are not signed because the store assigns them after authorization signing; they remain covered by the event envelope digest and require external checkpoint anchoring for tamper resistance.

## Required v2 grant fields

The closed payload schema is `branch_merge_authorization@2`. It requires `signature_version=E09-AUTHZ-SIG-V2`, `audience=e12a6-lifecycle`, issuer, scope, parent state, exact branch set, evidence refs, issue/expiry timestamps, the expected durable event sequence, algorithm and signature. The append uses an expected-sequence compare-and-swap, and the verifier requires the signed sequence to equal the committed event sequence. Unknown and missing fields fail closed. Legacy v1 authorization signatures are no longer accepted by the strict resolver.

## Tests

Real Ed25519 tests mutate every envelope field and every payload field independently. Every mutation must fail signature verification. Domain separation is tested, and the cross-branch E09 → E12-A6 → ZPCM integration path now uses v2.

## Remaining production requirements

Cryptographic binding is not caller authentication. The actor role is a signed claim but must still be authorized by a separately authenticated authorizer service. Production must add workload identity, trusted verifier time, nonce/replay tracking, external checkpoints and anti-rollback.
