# E12-A6 Writer Identity Audit v1

This increment binds the authenticated writer principal to the durable authorization-consumption event.

## Identity source

The writer service accepts an opaque IPC credential and delegates authentication to its configured workload authenticator. The resulting immutable principal supplies:

- workload identity (for example, a SPIFFE URI)
- identity provider
- authentication method
- SHA-256 fingerprint of the authenticated credential or peer certificate

These values are server-derived. They are not accepted from the submission request. The credential itself and bearer tokens are never persisted.

## Persistence contract

Receipt-backed candidate registration requires an explicit writer identity. The lifecycle bundle records the four identity attributes in the same authorization_consumed event and the same SQLite transaction as evidence and candidate registration.

The ZPCM event validator rejects missing, empty or malformed identity fields. The credential fingerprint must be 64 lowercase hexadecimal characters. The append-only event log therefore retains who consumed a verifier receipt, how the caller was authenticated and which credential instance was presented.

Receipt-free candidate registration does not accept consumption metadata.

## Security boundary

This improves durable attribution and prevents anonymous receipt consumption through the persistence API. It does not make a Python object an unforgeable identity token and does not protect against malicious code running inside the writer process. The authenticator must be backed by a real OS/workload identity mechanism at deployment.

## Remaining work

- Dedicated writer process and exclusive database file permissions.
- Authenticated local IPC (Unix domain socket with peer credentials) or mTLS for remote writer calls.
- Separate OS identities and credentials for E09 authority, E09 verifier and E12-A6 writer.
- KMS/HSM key custody, external monotonic checkpoints and restore-time anti-rollback checks.
- Process-crash, multi-process contention and load tests.
