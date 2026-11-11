# Per-Execution Sandbox Attestation (P1.6.3)

## Problem

P1.6.1 validates a host/supervisor capability report. P1.6.2 inventories
read-only host facts. Neither by itself binds a successful enforcement check
to one exact experiment execution. A stale report could otherwise be replayed
for a different patch, branch, runner, image, or execution request.

## Attestation contract

A supervisor-issued attestation binds:
- exact execution ID and execution manifest digest;
- exact patch digest (including explicit absence);
- target branch;
- runner and supervisor identities;
- immutable image digest;
- one-time 256-bit challenge nonce;
- the complete required control set;
- issue and expiry timestamps;
- key ID for key rotation.

The required controls include namespaces, cgroup v2, seccomp, enforcing LSM,
non-root identity, read-only root, network isolation, resource enforcement,
process-tree termination, output quota, and immutable image identity.

The verifier checks HMAC-SHA256 over canonical JSON, all execution bindings,
challenge equality, required controls, key ID (when supplied), timestamp
freshness, and a short maximum attestation lifetime. HMAC comparison uses
constant-time comparison.

## Trust and replay boundaries

- The HMAC key must be available only to the trusted supervisor and the
  verifier. Never put it in manifests, prompts, artifacts, logs, checkpoints,
  or source control.
- HMAC is symmetric: any party holding the key can forge attestations. This
  module does not provide asymmetric identity, hardware attestation, or key
  storage/rotation infrastructure.
- The supervisor must issue a fresh unpredictable nonce per execution and
  reject nonce reuse. The verifier must maintain a consumed-nonce ledger;
  this module checks equality but does not persist replay state.
- A valid signature proves that the key holder signed these bytes. It does not
  prove the supervisor measured controls honestly, that the host is uncompromised,
  or that controls remain active after issuance.
- A runtime watchdog must continuously enforce controls and terminate the
  workload if enforcement is lost. Attestation expiry limits replay but does
  not replace runtime monitoring.

## Not implemented

- No supervisor process, nonce issuer/consumption database, HMAC key vault,
  asymmetric signing, hardware root of trust, or runner launch implementation.
- No OS sandbox setup or enforcement.
- No automatic bridge from host probe facts to attested controls.
- No permission to execute untrusted code is granted by constructing an
  attestation object in an untrusted process.

## Validation

Tests cover valid signatures, tampering, manifest/patch/branch/runner/image/
nonce binding, expiry, future timestamps, maximum lifetime, key ID, missing
controls, unknown controls, malformed nonce, and malformed signature.
