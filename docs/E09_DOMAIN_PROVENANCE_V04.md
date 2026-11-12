# E09 Domain Provenance v0.4

## Security objective

Bind each evidence reference to a trusted domain at its source observation. A
signed verifier receipt authenticates the verifier's statement; it does not
make caller-supplied metadata trustworthy. Domain attribution must therefore
be derived before receipt issuance.

## v0.4 event path

1. An authenticated observer calls `E09AuthorityService.append_observation`.
2. The authority resolves the observation scope through its server-owned
   `E09DomainRegistry` and writes `domain_id`, `world_family`,
   `domain_registry_id`, and `domain_registry_version` into the immutable
   `observation@4` payload.
3. The authenticated learner appends `prediction_commit@4` through the
   authority facade. E09 copies the domain tuple from the prior observation;
   caller-supplied domain fields are not accepted.
4. The authenticated evaluator appends `evidence_reveal@4`. E09 copies the
   same domain tuple from the prior commit and verifies the active registry
   binding.
5. The verifier replays observation → commit → reveal, checks exact domain
   equality, resolves the current trusted registry entry, and derives
   `world_family` itself.
6. The signed `e09_verification_receipt@2` carries the domain ID, registry ID,
   and registry version with each redacted evidence DTO. E12-A6 verifies the
   signature and persists the provenance fields with the evidence record.

## Closed schemas and roles

- `observation@4`: exact payload fields; `actor_role=observer`.
- `prediction_commit@4`: exact payload fields; `actor_role=learner`.
- `evidence_reveal@4`: exact payload fields; `actor_role=evaluator`.
- All v0.4 events require authenticated workload metadata in the immutable
  event envelope, exact payload-schema identifiers, and causal references.
- Domain fields must match across all three events and the active registry.
- Unknown fields, missing fields, wrong schema versions, mismatched domains,
  missing registry entries, and revoked registry entries fail closed.

## Legacy policy

E09 v0.3 remains readable only through the explicit legacy compatibility
resolver that requires caller-supplied migration context. It is not accepted
by the v0.4 verifier receipt path. Do not silently infer domain metadata from
scope names or rewrite old events. Migration requires an independently
authorized registry mapping and a new provenance event; otherwise quarantine
the old evidence from domain-sensitive training and cross-domain transfer.

## Trust and deployment boundary

The included `StaticE09DomainRegistry` is a reference/test implementation,
not a production registry service. Production must inject a managed,
versioned registry and ensure that only the authenticated E09 authority
process can write the E09 database. Learner and evaluator processes must not
have direct database-file access; use the dedicated authenticated IPC/service
boundary in the security stack.

Receipt signatures prove that the trusted verifier signed the receipt bytes.
The source domain is trustworthy only because the signed receipt binds values
that the verifier independently derived from authenticated, immutable E09
events and a trusted registry version.
