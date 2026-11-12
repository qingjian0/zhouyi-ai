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

E09 v0.3 can be inspected only through the resolver's explicit
`allow_legacy_migration=True` compatibility path and caller-supplied migration
context. It is not accepted by the v0.4 verifier receipt path, direct E12-A6
evidence registration, or cross-branch merge authorization. Legacy
`VerifiedBranchMergeAuthorization` capabilities carry
`domain_provenance_verified=False` and are rejected by the merge validator.
Do not silently infer domain metadata from scope names or rewrite old events.
Migration requires an independently authorized registry mapping and a new
v0.4 provenance event; otherwise quarantine old evidence from domain-sensitive
training and cross-domain transfer.

## Trust and deployment boundary

The included `StaticE09DomainRegistry` is a reference/test implementation,
not a production registry service. `E09AuthorityRuntime` provides the
reference process boundary: the database lives in a service-owned 0700
directory with a 0600 file; the IPC socket lives in a separate 0710
service-owned/client-group directory with a 0660 socket; and client UIDs must
differ from the database-owner UID. Kernel `SO_PEERCRED` selects a
server-side UID-to-workload-credential binding. Requests cannot provide
credentials, roles, UIDs, domain fields, or integrity metadata. Only the
authority runtime opens the database.

The same-UID mode is explicitly test-only. A production deployment must run
the authority under a dedicated service UID, configure the socket client
group, map each runner/learner/evaluator UID to a distinct workload
credential, and inject a managed versioned registry. The tests prove the
filesystem/IPC policy and peer rejection; they do not claim that this service
has already been deployed on a production host.

Receipt signatures prove that the trusted verifier signed the receipt bytes.
The source domain is trustworthy only because the signed receipt binds values
that the verifier independently derived from authenticated, immutable E09
events and a trusted registry version.
