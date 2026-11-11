# E12-A6 Atomic E09 Receipt Consumption v1

Status: implemented in the persistent lifecycle ledger reference adapter.

## Transaction contract

A verified E09 receipt is not considered consumed when it is merely received or signature-checked. It becomes consumed only in the same ZPCM SQLite transaction that appends:

1. all redacted evidence registration events;
2. the OBSERVED candidate registration event;
3. the authorization-consumed event containing receipt ID, nonce, grant reference, episode, scope, parent, branch/evidence bindings, issuer/verifier identity, original authorization digest, candidate identity, receipt validity interval and server consumption time.

The batch uses ZPCM append_lifecycle_events with expected_sequence and BEGIN IMMEDIATE. It is all-new or all-replayed; partial replay is rejected. The receipt event is appended after the candidate/evidence events in the same transaction.

## Replay and recovery

- Receipt ID and nonce are independently unique in the lifecycle stream.
- A receipt already consumed for one candidate cannot be rebound to another candidate.
- A receipt-backed candidate retry must present the same receipt and the same consumption payload.
- A receipt cannot be consumed outside its issue/expiry interval.
- Startup replay reconstructs consumed receipt and nonce indexes from the append-only event log and validates the event's candidate, parent, branch and evidence bindings.
- Snapshot output includes the consumed authorization records for audit.

## Security boundary

This change makes receipt consumption durable and atomic inside the SQLite reference ledger. It does not by itself prevent code in the same process from directly writing to ZPCM or constructing the in-process VerifiedE09VerificationReceipt dataclass. The next service layer must verify the signed JSON receipt, derive the verified object only after cryptographic validation, and be the sole writer process with exclusive database access.

Authenticated IPC, OS-level process isolation, HSM/KMS verifier keys and external anti-rollback checkpoints remain production gates.
