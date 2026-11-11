# E12-A6 Authenticated Unix-Domain-Socket Boundary v1

## Trust model

The UDS server obtains PID, UID and GID from Linux `SO_PEERCRED` on the accepted socket. Those kernel-supplied values are passed to the dispatcher as an immutable `E12A6PeerCredentials`. Any `pid`, `uid` or `gid` values in request JSON are untrusted data and must never affect identity or authorization.

The dispatcher is the integration seam: map the kernel peer tuple through a server-side UID/workload allowlist, derive a server-owned IPC credential, and pass that credential to `E12A6WriterService.submit_authorized_merge_candidate`. The client cannot select its workload ID, roles, scopes, identity provider, authentication method or credential fingerprint.

## Socket and framing contract

- Linux only; fail closed unless `SO_PEERCRED` is available.
- Parent state directory must be service-owned and mode `0700`.
- Existing socket paths, regular files and symlinks are never replaced or unlinked during startup.
- Bound socket path is forced to mode `0600` and checked as a service-owned socket.
- One newline-terminated UTF-8 JSON object per connection; duplicate keys, malformed JSON, non-object roots, trailing frames and oversized requests are rejected.
- Request size defaults to 1 MiB and is bounded at construction (maximum 16 MiB); each client has a read timeout.
- Only explicitly allowlisted UIDs reach the dispatcher.
- Responses are bounded JSON objects; transport errors expose a generic rejection to clients.

## Operational deployment

Run the writer under a dedicated unprivileged UID. Create a private state directory owned by that UID with mode `0700`. Restrict the socket's parent directory to that service account. If multiple local workloads need access, grant access by group/ACL only after reviewing the UID/GID policy; do not broaden the directory to world-readable or world-writable.

## Explicit limitations

This module is a transport boundary, not a complete application protocol. It does not itself decode typed CSG-GCR proposals or manufacture workload claims. The dispatcher must perform a strict operation/schema allowlist, map `E12A6PeerCredentials` to a server-side credential, and call the writer service. `SO_PEERCRED` authenticates the peer process credentials at connection time; it does not protect against root or a compromised process running as an allowlisted UID. This is local Linux IPC, not a network API.
