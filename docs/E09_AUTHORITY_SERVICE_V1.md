# E09 authenticated authority service v1

## Scope

PR #236 introduces an in-process authority service boundary for issuing signed
branch-merge grants. It is deliberately separate from the resolver and the
Ed25519 public-key verifier.

## Security properties

- A credential is passed to an injected authenticator; callers cannot assert
  their own role or issuer identity in the issue request.
- Only an authenticated principal with the explicit
  `branch_merge_authorizer` role and the configured issuer ID can issue.
- The service signs the complete E09 authorization envelope v2 using Ed25519.
- The signed integrity metadata records the authenticated subject and
  credential identifier for audit correlation.
- Grant lifetime is bounded by service policy and uses an injected,
  timezone-aware clock.
- Sequence is read from the durable episode and committed with
  `expected_sequence`; concurrent issuers race safely and one loses CAS.
- Private signing keys are injected as runtime key objects and are never
  serialized or persisted by this module.

## Explicit limitations

This is not yet a production process boundary. The authenticator, private-key
custody, trusted clock, service deployment, IPC transport, rate limiting,
audit export, revocation distribution and database anti-rollback remain
deployment responsibilities. The default clock is a local system clock and
must be replaced by a trusted time source in production. The SQLite store is
still a single-host reference implementation.

The service does not make a valid signature equivalent to a valid merge:
E12-A6 must still validate the exact parent, branch set, evidence chain,
lifecycle state and one-writer transition.
