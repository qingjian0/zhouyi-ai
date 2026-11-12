# E09 / E12-A6 Process Isolation and IPC Contract v1

Status: design baseline for Issue #282; this document does not claim process isolation is implemented.
Date: 2026-11-12
Stack base: PR #278 head `9f8cfafa7e126a9862fe5bb8f48a95db3af7753d`.

## 1. Security objective

Remove learner/evaluator access to the E09 and E12-A6 SQLite files. Python facades are policy boundaries only; they are not security boundaries while callers share a process, store object, filesystem permissions or signing keys.

The security boundary is the combination of distinct OS service identities, exclusive database/key access, authenticated IPC with server-derived peer identity, narrow versioned schemas, durable idempotency/replay controls, and process-level adversarial/crash-recovery tests.

## 2. Target process topology

| Process | OS identity | Database access | Signing material | Exposed operations |
|---|---|---|---|---|
| Observer / ingress | `zhouyi-observer` | none | none | submit raw observation input and request trusted Observation append; no learner/evaluator DB access |
| Learner / SROK | `zhouyi-learner` | none | none | append learner commits/structures/revisions; read learner-safe projection; never read unrevealed target/feedback |
| Evaluator | `zhouyi-evaluator` | none | none | append reveal for an authorized committed prediction; no learner DB access |
| E09 Authority | `zhouyi-e09-authority` | read/write E09 DB + input payload vault | authorization issuer key through KMS/HSM | authenticated append; payload APIs; role-filtered reads |
| E09 Verifier | `zhouyi-e09-verifier` | read-only E09 snapshot/DB | receipt signer through KMS/HSM | verify ancestry/provenance; issue signed receipts |
| E12-A6 Writer | `zhouyi-e12-writer` | read/write ZPCM/E12-A6 DB | no E09 private key | verify receipt; recompute coordination; atomically consume receipt |
| Analytics | separate identity | read-only exported projections | none | bounded, redacted queries |

Learner/evaluator must not share an OS account with Authority, Verifier or Writer. They must not belong to database-owning groups or traverse service database directories.

## 3. IPC transport choice

### First implementation: Linux Unix domain sockets

Use Unix domain stream sockets with:
- socket path under a service-owned directory, e.g. `/run/zhouyi/e09-authority.sock`;
- directory mode `0750`, socket mode `0660`, owner `zhouyi-e09-authority`, group limited to explicitly authorized clients;
- Linux `SO_PEERCRED` (PID/UID/GID) read by the server immediately after accept;
- server-side UID/GID-to-workload mapping from a root-owned, non-writable policy file;
- no client-supplied role, workload ID, scope grant or authentication method;
- initially one request per connection; connection pooling only after framing/cancellation semantics are tested.

Socket permissions are an outer gate, not the complete authorization decision. The server maps kernel peer identity to a workload principal and checks operation, role, scope, episode and track. Never trust UID/PID fields in JSON.

### Later remote transport

Use mutually authenticated TLS with pinned workload trust roots, certificate rotation/revocation, SAN-to-workload mapping and the same authorization policy. Do not expose unauthenticated TCP or bearer-token-only endpoints.

Windows is not part of the first Linux UDS implementation. A later Windows transport must use named pipes with server-side peer identity and ACLs; it must not silently fall back to loopback TCP.

## 4. Wire protocol

Transport v1 uses UTF-8 JSON with a 4-byte unsigned big-endian frame length.

Request envelope:
- `protocol`: fixed string `zhouyi-ipc/1`;
- `request_id`: caller-generated UUID for tracing only;
- `operation_id`: stable idempotency key for a mutating operation;
- `operation`: allowlisted operation name;
- `deadline_ms`: bounded relative deadline, capped by server policy;
- `body`: operation-specific strict object.

Response envelope: `protocol`, `request_id`, `status`, `body`. Errors use stable machine-readable codes and bounded redacted messages. Never return stack traces, raw labels, database paths, secrets or private-key material.

Initial hard limits:
- maximum frame: 4 MiB, rejected before allocation;
- maximum nesting depth: 32;
- maximum list length: 10,000;
- maximum string length: 256 KiB;
- reject duplicate JSON object keys, NaN/Infinity, unknown fields and malformed types;
- enforce server-owned execution deadlines and per-peer concurrency limits;
- use canonical JSON for request digests and idempotency binding.

These are protocol ceilings, not per-operation allowances. Operation-specific limits should be smaller.

## 5. E09 Authority API

The secure adapter must no longer receive `SQLiteEvidenceStore`, a database path or a raw store client. Define a transport-neutral `E09AuthorityClient` protocol, implemented by an in-process test client and a Unix-socket RPC client.

Allowlisted operations:
- `observation.put_input`: observer-only; Authority validates peer role/scope, writes content-addressed input payload and returns digest reference;
- `observation.append`: observer-only; domain tuple derived from configured registry;
- `observation.read_input`: observer/learner only; returns input payload, never reveal labels;
- `prediction.commit`: learner-only; requires exact prior Observation causal reference;
- `evidence.reveal`: evaluator-only; requires exact prior Commit causal reference;
- `structure.append`, `revision.append`: learner-only; preserve existing scope/track/parent/support/causation checks;
- `episode.read_for_learner`: redacted projection excluding `target_or_feedback`, raw reveal payloads and evaluator-only fields;
- `episode.read_for_evaluator`: authorized evaluator view;
- `health`: non-sensitive readiness and protocol version only.

Do not expose generic `append_event`, arbitrary SQL, arbitrary file paths, unscoped replay or raw database handles.

### Data-flow correction required

PR #327 moves secure-mode input payload writes behind `E09AuthorityService.put_observation_input`; the legacy adapter mode still writes directly to the store. The combined adapter nevertheless retains a concrete `SQLiteEvidenceStore` handle for startup checks, replay and memory projection, and its legacy fallback still performs direct writes. These remaining database dependencies must be removed from learner/evaluator processes before claiming isolation.

Authority owns secure-mode payload persistence. Learner input reads and learner replay are explicitly role-filtered. Evaluator reveal writes are isolated. Raw target/feedback remains in E09 evidence events and is released only through the verifier/evaluator policy; learner-facing replay must not return it. The next adapter increment must replace the concrete store dependency with a transport-neutral client and add a separately authorized learner checkpoint-read contract before restart recovery is moved off the store.

## 6. E09 Verifier API

Verifier has a separate OS identity and read-only E09 data access. It must not share Authority's write-capable connection object.

Allowlisted operation:
- `receipt.issue`: accepts episode, scope, track, candidate/authorization references and expected branch bindings; derives evidence domain provenance from durable Observation ancestry; validates exact Observation → Commit → Reveal lineage; signs a short-lived receipt for fixed audience `e12a6-writer`.

Receipt requirements: strict schema version; issuer/verifier key ID and key epoch; audience, scope, episode, learner track and exact evidence set; issued-at/expiry from verifier-owned clock; cryptographically random nonce and unique receipt ID; signature over canonical bytes; maximum TTL; public-key trust bundle pinned by Writer out of band.

Verifier private key stays in KMS/HSM. Verifier receipt signer must be separate from the E09 authorization issuer key/process unless a documented key-separation exception is approved.

## 7. E12-A6 Writer API

Writer is the sole process with write permission to the ZPCM/E12-A6 database. It has no E09 database dependency and no E09 private signing key.

Allowlisted operation:
- `candidate.submit_authorized_merge`: authenticated candidate submitter sends typed proposals, base state, branch snapshots, selected proposal IDs, grammar version and signed receipt.

Writer must authenticate peer identity, enforce candidate_submitter role and exact scope, verify receipt signature/audience/expiry/key epoch/nonce/binding, recompute CSG-GCR typed coordination inside Writer, compare recomputed parent/branches/authorization evidence/candidate evidence to the signed receipt, and atomically persist redacted evidence/candidate/receipt consumption.

Retries are idempotent by receipt ID + nonce + canonical request digest. Do not accept a serialized Python `VerifiedBranchMergeAuthorization` capability or caller-precomputed merge result.

## 8. Database and filesystem permissions

Use service-owned directories, restrictive umask and explicit ownership:
- E09 DB/raw reveal vault: owner `zhouyi-e09-authority`, mode `0600`; Verifier receives read-only access through a consistent snapshot or a separately tested read-only group with correct SQLite journal semantics.
- E12/ZPCM DB: owner `zhouyi-e12-writer`, mode `0600`; no E09 process or learner/evaluator access.
- KMS/HSM access: Authority can request authorization signatures; Verifier can request receipt signatures; Writer can verify public keys only.
- IPC socket directories: service-owned, non-world-writable, no symlink following; stale sockets removed safely at startup.
- Logs exclude raw inputs, labels, credentials, private key material and sensitive receipt payloads.

Prefer a transactionally consistent E09 snapshot for Verifier if shared SQLite WAL sidecar access cannot be made safe. Never copy a live DB file without a consistent SQLite backup/snapshot operation.

## 9. Idempotency, replay and crash semantics

- Request ID is correlation only, not an idempotency key.
- Mutating operations require operation-specific idempotency key and canonical request digest.
- Same key + same digest returns original durable result; same key + different digest is a hard conflict.
- E09 event IDs and sequence CAS remain authoritative for event append.
- E12 receipt ID and nonce are consumed in the same transaction as candidate/evidence persistence.
- If a process dies after commit but before response, retry returns committed result without duplicate writes; before commit, retry may safely execute.
- Deadline expiration before commit aborts; after commit, retry reports committed status rather than claiming rollback.
- Startup performs integrity/replay validation before accepting requests.

## 10. Rollback and key lifecycle

SQLite digests/hash chains alone do not detect restoration of an older internally consistent snapshot. Production needs an external monotonic checkpoint, for example a separately administered append-only store or KMS-backed monotonic service recording service identity, database epoch, last sequence, root digest and timestamp.

Refuse startup or require explicit recovery authorization if local state is behind the last trusted checkpoint. Key rotation requires overlapping public-key trust windows, revocation epochs and receipt TTL limits.

## 11. Verification plan and acceptance gates

### Gate A — transport correctness
Test frame truncation, oversized frames, invalid UTF-8/JSON, duplicate keys, unknown fields, malformed schemas, slow-client timeouts, spoofed body identity fields, unauthorized UIDs, wrong role/scope/episode/track, cancellation and bounded concurrency.

### Gate B — process/filesystem isolation
Run tests as distinct OS users:
- learner cannot open E09 DB, raw reveal vault or E12 DB;
- evaluator cannot open E09 DB or E12 DB;
- Verifier can read E09 but cannot write;
- Authority can write E09 but cannot write E12;
- Writer can write E12 but cannot read E09;
- no workload can enumerate service-owned secret/key files.

### Gate C — end-to-end recovery
Kill processes before/after each E09 append and receipt issue, and before/after E12 atomic bundle commit. Test retries, duplicate receipt/nonce, stale sequence, expiry, backup restore/checkpoint verification, multi-process contention and concurrent duplicate requests.

### Gate D — end-to-end vertical slice
Separate observer and learner processes, both without DB handles:
`Observer Input → Authority RPC (payload + Observation) → Learner reads authorized input → Commit RPC → Evaluator Reveal RPC → Verifier Receipt RPC → E12 Writer RPC → ZPCM durable commit → restart/replay`.

The test must inspect OS file permissions and process identities, not merely mock credentials or instantiate two Python objects.

## 12. Migration sequence

1. Replace adapter's concrete `E09AuthorityService` and `SQLiteEvidenceStore` dependencies with narrow transport-neutral protocols; retain in-process implementation for unit tests.
2. Add Linux UDS Authority server/client, kernel peer identity mapping, strict framed JSON and role-filtered reads/payload APIs.
3. Add Verifier process with read-only E09 snapshot and independent receipt signer.
4. Add Writer RPC with typed DTO serialization, server-side recomputation and atomic ZPCM persistence.
5. Add OS deployment harness with service users, directories, permissions and explicit configuration.
6. Add adversarial process tests proving negative access-control properties and kill/restart recovery.
7. Add external checkpoint, KMS/HSM integration, key rotation/revocation, monitoring and backup restore drill.

No phase may claim full process isolation until Gates A–D pass on the target deployment OS.


## 13. Implementation status — 2026-11-12

The current stacked implementation has reached the following code increments:

| Layer | Implementation | Current scope |
|---|---|---|
| IPC transport | `prototype/unix_ipc.py` (PR #289) | Linux UDS framing, SO_PEERCRED mapping, bounded JSON, deadlines and worker limits |
| E09 Authority | `prototype/e09_unix_rpc.py` (PR #295) | Observer input vault, Observation, Commit, Reveal, Structure and Revision RPCs |
| Verifier storage | `SQLiteEvidenceReader` (PR #296) | Read-only SQLite replay interface for verification |
| E09 Verifier | `prototype/e09_verifier_unix_rpc.py` (PR #297) | Writer-only receipt issuance, durable operation reservation and retry ledger |
| E12-A6 Writer | `prototype/e12a6_writer_unix_rpc.py` (PR #301) | Typed DTO decoding, signed receipt binding, in-process recomputation and atomic lifecycle bundle write |
| Learner feedback | `read_support_feedback` (PR #302) | Learner-only release of lineage-verified SUPPORT feedback; gate/test labels remain blocked |
| Learner memory projection | `read_learner_episode` (PR #304) | Authenticated event projection with raw reveal labels and checkpoint blobs redacted |
| Learner assignment | `E09LearnerBindingResolver` (PR #327) | Server-side episode/scope/track binding; Observer RPC cannot choose a learner workload ID |

These are service-boundary implementations and CI-tested local UDS integrations. They do **not** yet establish production process isolation.

### Remaining production gates

1. Provision separate non-root OS identities and service-owned database/key directories; test real cross-UID socket authorization and filesystem denials.
2. Publish a transactionally consistent E09 snapshot to the Verifier identity; prove SQLite journal/WAL and sidecar access semantics.
3. Move E09 Authority, Verifier and E12-A6 Writer signing material into separate KMS/HSM-backed identities.
4. Split the current combined E09 adapter into observer ingress, learner and evaluator roles. Remove its direct SQLite handle, direct payload-vault access and unrestricted replay/memory projection.
5. Keep learner assignment resolution server-side and provision it from the authenticated experiment/tenant assignment system; never accept learner_workload_id from an Observer request. Add a dedicated learner checkpoint-read API that validates ledger snapshot records against authorized SUPPORT evidence; the redacted ZPCM projection intentionally omits restart snapshots.
6. Add E12 Writer OS deployment, DB-exclusive ownership, external monotonic checkpoint, backup/restore and receipt-consumption recovery tests.
7. Run the full Observation → Commit → Reveal → Receipt → Writer → ZPCM → restart/replay vertical slice across separate OS processes, then execute Gates A–D from this contract.

Until these gates pass on the target deployment OS, describe the system as **authenticated IPC prototype**, not production-isolated or production-secure.
