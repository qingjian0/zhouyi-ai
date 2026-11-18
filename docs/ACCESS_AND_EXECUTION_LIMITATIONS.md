# Access and Execution Limitations

This document records permission, authorization, and tool-access limitations encountered while maintaining this repository. It is also the required audit trail for future automation and maintenance runs.

## Recording rule

Whenever an intended GitHub operation cannot be completed because of insufficient repository permission, missing authorization/connection, or an API access denial, append an entry here. Include:

- Date and time (UTC, with timezone)
- Repository and exact operation attempted (for example: merge PR, push commit, update file, inspect Actions logs, or delete branch)
- The observed error/status, preserving the useful error text while removing tokens and private data
- Permission or authorization apparently required
- What could not be completed and its impact
- A concrete manual remediation step for an authorized maintainer

Do not describe an operation as completed unless GitHub confirms success. Distinguish permission denial from unrelated failures (network errors, rate limits, merge conflicts, failed checks, missing resources, or unsupported API endpoints). Record those separately when they materially block work. Never include credentials, access tokens, private keys, or personal data.

If the active integration lacks permission to write this document, report that limitation explicitly in the run report and provide the exact entry that an authorized maintainer should add manually. Do not claim that the documentation was updated.

## Initial access check — 2026-11-15

- Repository: `qingjian0/zhouyi-ai`
- Default branch: `main`
- Repository permission metadata returned by the connected GitHub integration: `admin=true`, `maintain=true`, `push=true`, `pull=true`, `triage=true`.
- Outcome: repository metadata and project files were readable; no permission-denied response was encountered during this access check.
- Limitation: this metadata is the permission view exposed by the current integration. It does not guarantee that every individual API endpoint, organization policy, branch rule, or future operation is authorized.
- Required follow-up: for each future blocked operation, record the exact failure below rather than assuming access from this initial check.

## Permission / authorization incident log

_No permission-denied incidents have been confirmed at the time of this initial entry._

Append new incidents below in reverse chronological order.
