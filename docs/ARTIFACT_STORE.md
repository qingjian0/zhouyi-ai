# Agent Artifact Store

## Purpose
Persist agent deliverables separately from scheduler checkpoints. The first backend
is a local filesystem store with content-addressed objects and atomic publication.

## Contract
- `ArtifactStore.put(AgentArtifact) -> ArtifactRef`
- `ArtifactStore.get(ArtifactRef) -> AgentArtifact`
- References carry artifact ID, kind, and a SHA-256 content digest.
- JSON is canonicalized (UTF-8, sorted keys, compact separators, finite numbers only)
  before hashing, so equivalent JSON objects produce stable content identifiers.
- Object paths are derived only from the validated digest, never from user-provided IDs.
- Writes use a temporary file, fsync, and atomic hard-link publication; concurrent
  writers of identical content converge on the same object.
- Reads validate schema, reference metadata, and content digest before returning data.
- A configurable byte limit prevents unbounded individual artifacts.

## Scope and limitations
This is a local single-host backend, not a distributed object store. It does not
provide encryption-at-rest, access control between tenants, retention policy,
garbage collection, or transactional indexing. The caller must keep the artifact
root in a protected workspace and back it up as needed. Do not store credentials,
private chain-of-thought, or raw sensitive user data in artifacts.

The digest proves integrity against accidental corruption; it is not a signature
and does not prove who created an artifact. For multi-user or remote execution,
add authenticated storage, ownership/namespace policy, signed provenance, and
retention controls before deployment.

## Acceptance
1. Round-trip preserves artifact identity, kind, and JSON content.
2. Identical content maps to the same digest.
3. Tampered content and mismatched references are rejected.
4. Oversized artifacts are rejected before publication.
5. Concurrent identical writes do not expose partial objects.
