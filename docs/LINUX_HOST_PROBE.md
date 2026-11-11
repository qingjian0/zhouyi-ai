# Linux Host Capability Probe (P1.6.2)

## Purpose

P1.6.1 defines a policy evaluator for a trusted supervisor capability report.
P1.6.2 adds a conservative, read-only host probe to distinguish visible host
primitives from controls that can only be established by the execution
supervisor.

## Observations

The probe reads only:
- current process namespace handles under `/proc/self/ns`;
- presence of the cgroup v2 controller file;
- current process `Seccomp` mode in `/proc/self/status`;
- kernel LSM names from `/sys/kernel/security/lsm`;
- current process effective UID.

Each observation is tri-state: `available`, `unavailable`, or `unknown`.
Unreadable or malformed evidence is `unknown`, not success.

## Explicit non-inferences

The probe deliberately does NOT claim that:
- visible namespace handles mean the process can create fresh namespaces;
- current-process seccomp mode means a child sandbox will receive a filter;
- cgroup v2 is mounted means CPU, memory, PID, or I/O limits are configured;
- an active LSM name means the target workload is confined by an enforcing policy;
- the current process UID predicts the identity of the target workload;
- the target root filesystem is read-only;
- the target network is isolated;
- process-tree termination or output quotas are enforced;
- the execution image is immutable.

Those target-runtime properties remain `unknown` until a trusted supervisor
configures and verifies them for the exact execution instance.

## Safety properties

- No subprocesses are launched.
- No files are written.
- No mounts, namespaces, cgroups, seccomp filters, or LSM policies are changed.
- No execution authorization is returned.
- The result is an inventory snapshot, not an attestation and not a sandbox.

The probe output must not be converted directly into a P1.6.1
`CapabilityReport`: host observations and target-runtime enforcement are
different trust domains.

## Validation

Unit tests use injected readers and platform facts, so CI does not depend on
the host running Linux. Tests verify observed facts, unavailable facts,
unknown-on-error behavior, non-Linux behavior, and invalid inputs.
