# P1.6 Controlled Execution: Threat Model and Runner Contract

## Status and scope

This phase defines an execution contract and threat model. The current Python
module validates declarations and approval bindings only. It is **not** a
sandbox, process launcher, resource enforcer, cryptographic signer, or execution
attestation system. No generated patch or command is executed by this phase.

## Security objectives

1. Execute only a reviewed, immutable experiment specification.
2. Bind approval to the exact manifest digest, patch digest, and target branch.
3. Default to no network access and read-only source/data inputs.
4. Enforce resource limits outside the child process.
5. Preserve auditable execution metadata and output artifact digests.
6. Fail closed when isolation or resource enforcement cannot be established.

## Threat model

Assume an agent-produced patch, dataset, model artifact, command argument,
dependency, or experiment process may be malicious or compromised. Threats
include path traversal, symlink escapes, arbitrary code execution, shell
injection, network exfiltration, credential theft, fork bombs, CPU/memory/disk
exhaustion, output flooding, stale approvals, artifact substitution, and
cleanup failure.

The existing `WorkspaceManager` provides directory lifecycle management
only. It does not isolate syscalls, network, credentials, processes, or the
host filesystem. `PatchValidator` performs conservative syntax checks but
does not prove patch safety. Neither is a security boundary.

## Contract

- `ExecutionManifest` pins a full Git commit SHA, dataset SHA-256 digest,
  model ID/version, seed, allowlisted command identifier, argv array, resource
  limits, creation timestamp, and optional exact patch digest.
- `manifest_digest` fingerprints the canonical manifest representation.
- `ApprovalBinding` binds approval to the manifest digest, exact patch digest,
  target branch, approver identifier, and timestamp.
- `validate_approval` rejects a changed manifest, patch, or target branch.
- `ExecutionRecord` records runner identity, terminal status, exit code,
  observed CPU time, peak memory, disk writes, output bytes, and output digest.

Argument arrays are required; shell command strings are not part of the
contract. A command ID must resolve through a separately maintained,
administrator-controlled executable allowlist. Environment variables must be
constructed from a minimal allowlist; secrets must never be inherited or
written into logs, manifests, checkpoints, or artifacts.

## Required runner architecture before executing untrusted code

### Linux

Use a disposable container or stronger VM boundary, non-root UID/GID,
user/PID/mount/network namespaces, read-only root and input mounts, a dedicated
writable output mount, dropped capabilities, seccomp, and AppArmor/SELinux
where available. Apply cgroup CPU, memory, PID, and I/O limits; enforce wall
clock from an external supervisor. Container isolation is not equivalent to a
VM against kernel exploits.

### macOS and Windows

Do not claim that Linux namespace/seccomp controls transfer to these systems.
Use platform-native isolation (for example, a disposable VM or a separately
evaluated sandbox facility) and document weaker or unavailable controls.
If the configured security profile cannot be met, refuse execution rather
than silently falling back to a normal process.

### All platforms

- Network disabled by default; allowlist egress only through an enforceable
  proxy/firewall policy. Hostname allowlists alone do not prevent DNS rebinding.
- No host credentials, home directory, SSH agent, Docker socket, package
  manager credentials, or writable repository mount in the child environment.
- Pin dependencies and images by immutable digest; no unreviewed install hooks.
- Set CPU, memory, process count, wall-clock, disk, file-size, and output limits.
- Kill the entire process tree on timeout/cancellation; verify cleanup.
- Mount inputs read-only and publish outputs only after validation.
- Record actual resource observations from the supervisor, not self-reported
  values from the child.
- Store stdout/stderr with bounded size and redact secrets before persistence.
- Use append-only audit records; digest values provide integrity checks only,
  not signer identity or non-repudiation.

## Approval lifecycle

1. Construct the manifest and compute its digest.
2. Validate the patch and compute the exact patch digest.
3. Present manifest, patch digest, target branch, and risk summary to a human.
4. Store an approval binding to those exact values.
5. Immediately before launch, recompute all digests and revalidate approval.
6. Any patch, manifest, or target-branch change invalidates approval.
7. After execution, persist the supervisor-observed record and output artifacts.

Approval does not authorize changes to the approved patch or grant repository
write permission. Publishing a patch remains a separate action and permission.

## Explicit non-goals / limitations

This contract does not itself provide a sandbox, enforce limits, prevent a
host-kernel exploit, attest hardware identity, verify that a dataset was
truthfully used, or guarantee that runner observations are tamper-proof.
The current `ExecutionRecord` is a data structure; trusted attestation
requires a supervisor outside the untrusted workload and protected audit
storage. A SHA-256 digest is not a digital signature.

## Next implementation gates

1. Select and document a Linux runner profile; test namespace, cgroup,
   seccomp, mount, network, timeout, and cleanup enforcement.
2. Add an external supervisor with a fixed command allowlist and no shell.
3. Add integration tests that attempt filesystem escape, network access,
   process exhaustion, memory exhaustion, output flooding, and timeout.
4. Add platform capability detection and fail-closed behavior.
5. Link execution records and output artifacts to the Experiment Registry.
6. Only then run controlled baseline-vs-candidate model experiments.
