# E09 Ed25519 issuer keyring v1

## Implementation

`prototype/e09_ed25519_keyring.py` implements the E09 authorization signature-verifier callback using Ed25519 public keys from the `cryptography` package.

- The caller supplies an immutable mapping from issuer ID to raw 32-byte Ed25519 public key.
- Authorization events must declare algorithm `Ed25519`; unsupported algorithms fail closed.
- Signatures are standard Base64 encodings of the 64-byte Ed25519 signature.
- Unknown and revoked issuers fail closed.
- No private key is loaded, stored, generated or committed by the verifier.
- `verifier_id` is a deterministic SHA-256 fingerprint of the active issuer public-key set and revocation set.

## Rotation and revocation

Rotation is performed by constructing and deploying a new keyring with the replacement public key. A signature made by the old key will fail against the new keyring. Revocation is performed by adding the issuer ID to `revoked_issuers`; revoked keys cannot authorize events even if their signatures remain mathematically valid. Every keyring configuration change produces a different `verifier_id`, which should be recorded with verification/audit output.

This v1 contract treats one issuer ID as one active public key. Multi-key overlap windows and key IDs are deferred until a real issuer deployment requires them.

## Trust and operations

Public keys must be provisioned out-of-band from a trusted identity/authorization system. The repository does not contain production issuer keys. Production deployment must protect the keyring configuration, distribute revocations promptly, define emergency key replacement procedures, and preserve historical verifier IDs for audit.

Ed25519 event signature verification authenticates the grant only when the supplied public key is itself trusted. It does not authenticate the SQLite host, isolate evaluator and learner processes, prevent rollback of the entire database, or provide remote tamper-evident replication.

## End-to-end evidence

The integration test generates an ephemeral Ed25519 keypair, signs an E09 grant over canonical episode/event/payload bytes, verifies the grant through the keyring, merges two branch deltas, and ingests the combined typed candidate and verified evidence into E12-A6/ZPCM. It also verifies unknown issuer, revoked issuer, key rotation, and raw-label redaction.
