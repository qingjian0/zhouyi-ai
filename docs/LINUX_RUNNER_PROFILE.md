# Linux Runner Capability Preflight (P1.6.1)

## Purpose

P1.6 defines an execution manifest, resource budget, approval binding, and
runner-reported execution record. P1.6.1 adds a fail-closed policy evaluator
for a Linux runner's capability report. It prevents an execution controller
from treating an incomplete or stale report as sufficient.

## Contract

- `CapabilityReport` is a supervisor-produced snapshot: platform, kernel,
  namespaces, cgroup mode, seccomp/LSM enforcement, identity, filesystem and
  network isolation, resource enforcement, process-tree termination, output
  quota, immutable image digest, probe ID, and observation time.
- `LinuxSandboxProfile` declares required controls. The default profile
  requires user/PID/mount/network namespaces, cgroup v2, seccomp, an enforcing
  LSM, non-root identity, read-only root, network isolation, enforced resource
  limits, process-tree kill, output quota, and immutable image identity.
- `evaluate_linux_profile` returns `ready` only when every required capability
  is present and the report is fresh. Missing, stale, future-dated, or
  non-Linux reports are blocked.
- Profiles can be relaxed for unit tests or explicitly trusted workloads, but
  production callers should use a reviewed policy profile rather than silently
  weakening requirements.

## Critical trust boundary

This is a pure policy evaluator. It does **not** probe Linux, create namespaces,
configure cgroups, install seccomp filters, enable AppArmor/SELinux, mount a
read-only filesystem, isolate networking, enforce quotas, or kill processes.
The report must be produced by a trusted supervisor from actual checks and
must not be synthesized from an experiment manifest or agent-supplied values.
A fabricated report can produce a false `ready` decision.

A fresh report can become stale immediately after preflight. A production
supervisor must bind the report to the runner instance and execution request,
revalidate immediately before launch, keep controls active for the entire
process lifetime, and fail closed if enforcement or monitoring is lost.
The probe ID is correlation metadata, not cryptographic attestation.

## Platform policy

This profile is Linux-specific. Windows and macOS need separately designed
native isolation backends and must not be treated as equivalent merely because
the Python policy object can parse their reports. Until a platform backend has
demonstrated equivalent controls, the production launcher must refuse to run
untrusted experiments there.

## Not implemented

- No host capability probe or kernel feature detection.
- No container/VM lifecycle, namespace creation, cgroup configuration,
  seccomp/LSM policy installation, network firewall, or filesystem mount setup.
- No process launcher, watchdog, audit ledger, signed attestation, or
  integration with the experiment registry.
- No claim of OS-level isolation or security certification.

## Validation

Unit tests cover complete reports, missing controls, stale/future reports,
non-Linux platform refusal, explicit profile relaxation, and invalid values.
These tests validate policy logic only; they do not validate a real Linux host.
