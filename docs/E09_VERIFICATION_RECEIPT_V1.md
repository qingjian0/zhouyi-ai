# E09 Verification Receipt v1

Status: signed receipt reference contract implemented; atomic one-time consumption is implemented by the E12-A6 persistent ledger adapter.

## Purpose

The E09 verifier currently returns an in-process Python capability. That object cannot serve as proof across an IPC boundary. Receipt v1 replaces that handoff with a verifier-signed, short-lived JSON envelope that an E12-A6 writer can validate using a pinned verifier public key without opening the E09 database.

## Receipt contract

The closed schema is e09_verification_receipt@1. The signed statement uses the domain separator:

    zhouyi:e09:verification-receipt:v1

It binds:

- receipt ID and unpredictable nonce;
- fixed audience e12a6-lifecycle-writer;
- verifier identity / trust-bundle fingerprint;
- episode and original authorization event reference;
- scope, parent state, exact branch IDs, the grant-bound authorization evidence subset and the complete candidate evidence set;
- issuer ID and original authorization event digest;
- server-issued time interval;
- redacted E12-A6 Evidence DTOs;
- Ed25519 signature algorithm and signature.

The receipt expiry is capped by both the original grant expiry and the verifier's configured receipt TTL. The authorization evidence references must be a subset of the full candidate evidence set; all candidate evidence DTOs are resolved and redacted by the verifier. The verifier creates issue/expiry timestamps from its own clock. The caller cannot set the receipt's validity interval.

## Writer-side verification

verify_e09_verification_receipt validates:

1. exact closed schema and fixed audience;
2. trusted verifier ID and Ed25519 signature;
3. timezone-aware issue/expiry interval against writer time;
4. exact scope, parent, branch, authorization-evidence and complete candidate-evidence bindings supplied by the writer;
5. one DTO per evidence reference, with exact DTO field set;
6. evidence episode identity, valid E12-A6 types and mandatory redaction of outcome/provenance.

The resulting VerifiedE09VerificationReceipt is only an in-process result after cryptographic validation. The signed JSON receipt is the transferable credential.

## Remaining production gates

- The persistent ledger now consumes receipt_id/nonce atomically with candidate/evidence registration; the service boundary must still ensure only a receipt-verified writer can invoke this API.
- The verifier signing key must be held by an HSM/KMS and its public key pinned in the writer trust bundle.
- The receipt verifier and E12 writer must run in distinct processes with authenticated IPC and least-privilege filesystem permissions.
- External checkpointing and rollback detection remain separate release gates.

## Tests

Tests cover valid Ed25519 verification, signature mutation, wrong scope, expiry, unknown fields, rejection of raw-label leakage, and end-to-end receipt issuance from a real E09 reveal chain and signed branch grant.
