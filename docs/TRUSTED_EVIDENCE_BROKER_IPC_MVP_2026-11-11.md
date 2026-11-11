# Trusted Evidence Broker IPC MVP (2026-11-11)

Status: experimental Linux-only learner-read MVP. Do not treat this as production isolation.

## Implemented in this branch

- `TrustedEvidenceBroker` constructs and owns one `SQLiteEvidenceStoreV03` instance inside the service process.
- A Unix-domain stream socket accepts one bounded JSON-line request per connection.
- On Linux, the server obtains peer PID/UID/GID from kernel `SO_PEERCRED`; the UID is mapped to a server-side `PrincipalPolicy`.
- The client cannot select its role or learner track. Unknown envelope keys, operation names, and payload keys are rejected.
- The only exposed operation is learner `get_snapshot(episode_id)`; episode scope is checked against the authenticated principal policy.
- Learner snapshots are serialized through the v0.1 allowlisted DTO. The cursor is an HMAC token over the visible snapshot and principal scope; global SQLite sequence numbers are not exported.
- Database parent directory is forced to mode 0700, database file to 0600, socket directory to 0750 and socket to 0660. The socket directory's group must be configured for intended client access.
- Requests and responses are size-bounded; authorization failures use a generic error response.

## Run

The service must run under a dedicated OS account that owns the private database directory. Configure a separate learner OS account and grant it only the socket directory's group access.

Example environment (do not commit the secret):

    EVIDENCE_BROKER_LEARNER_UID=<numeric learner uid>
    EVIDENCE_BROKER_LEARNER_TRACK=track-a
    EVIDENCE_BROKER_CURSOR_SECRET_HEX=<at least 32 random bytes, hex encoded>

Start:

    python -m prototype.trusted_evidence_broker_ipc \
      --socket /run/zhouyi-evidence/broker.sock \
      --database /var/lib/zhouyi-evidence/evidence.sqlite3

Client:

    from prototype.trusted_evidence_broker_ipc import request_snapshot
    snapshot = request_snapshot("/run/zhouyi-evidence/broker.sock", "episode-001")

Do not run the broker and learner under the same UID in a deployment intended to demonstrate isolation. The current CI test runs both sides as the same runner UID and validates kernel credential retrieval, server-side UID mapping, scope checks and filesystem modes; it does not prove separation between distinct OS accounts.

## Deliberate omissions

- No evaluator or policy-authority API is exposed.
- No learner write, evidence ingestion, prediction commit or challenge acknowledgement is exposed.
- No capability minting, credential rotation, signed policy authorization or revocation endpoint exists.
- No systemd unit, account/group provisioning or container profile is shipped.
- No protection against a privileged host administrator or compromised broker process.
- No timing-side-channel hardening beyond generic denial responses.
- No multi-client write concurrency is exposed because this MVP is read-only.

## Acceptance gates before production claims

1. Run broker as a dedicated service UID, learner as a different UID, evaluator as a third UID.
2. Prove learner cannot read database, WAL, shared-memory or backup files.
3. Prove evaluator can access only evaluator API and cannot mutate learner state.
4. Add authenticated policy authority and cumulative cross-version/episode challenge budgets.
5. Add restart/replay, request framing, denial uniformity, permission and tamper tests.
6. Add operational key rotation, socket lifecycle, audit retention and backup/restore procedures.

Correct claim: **this branch implements a Linux kernel-peer-credential-gated, read-only learner snapshot broker prototype. It does not yet implement full learner/evaluator/policy process separation.**
