# P1.4 — Isolated Workspaces and Patch Validation

## Goal
Keep agent-generated changes as reviewable patch artifacts. Give each task a separate
working directory and validate patch metadata before any future application step.

## Included in this phase
- `WorkspaceManager` creates task-scoped temporary directories under one configured root.
- Cleanup rejects symlink workspaces and paths that do not resolve directly under that root.
- `PatchValidator` accepts conservative text unified diffs and checks path prefixes,
  traversal, duplicate targets, file count, patch size, and unsupported metadata.
- Validation is deliberately separate from patch application.

## Security boundary (important)
This is **not an OS sandbox**. A per-task directory does not prevent a process from
reading other files, opening network connections, spawning child processes, or consuming
unbounded CPU/memory. No generated code is executed here and no patch is applied.

The validator is a conservative first-pass parser, not a complete implementation of the
Git patch grammar. It rejects binary patches, rename/copy metadata, mode changes, and
symlink mode changes. It does not prove that a patch is semantically safe. Before
application, a later integration must re-check every resolved target against the
workspace root, reject symlink components, and apply only through a trusted patch engine.

## Required next controls before autonomous execution
1. OS-level sandbox/container or dedicated low-privilege worker with filesystem and
   network restrictions; never treat a temporary directory as a sandbox.
2. Resource limits for CPU, memory, process count, wall-clock time, and output size.
3. Test execution through a fixed allowlist runner, not arbitrary model-provided shell.
4. Independent review of the diff, test output, and evidence.
5. Human approval bound to the exact patch digest and target branch before application.
6. Audit records linking task, patch digest, reviewer, approval, tests, and resulting commit.

## Acceptance
- Each task gets a unique directory under the managed root.
- Cleanup cannot be redirected through a workspace symlink.
- Unsafe paths, duplicate targets, oversized patches, and unsupported patch features fail closed.
- The implementation does not execute or apply agent-produced content.
