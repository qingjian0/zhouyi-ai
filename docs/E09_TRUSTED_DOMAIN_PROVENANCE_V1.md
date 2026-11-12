# E09 Trusted Domain Provenance v1

## Security invariant

A signed E09 verification receipt must never take `world_family` from a verifier request, learner request, candidate bundle, or E12-A6 writer request. The value is derived from the trusted Observation event and is covered by the immutable E09 event envelope.

The accepted provenance tuple is:

- `domain_provenance_schema = e09-domain-provenance@1`
- `domain_registry_id`
- `domain_registry_version`
- `world_family`

The registry ID and version are retained in the redacted Evidence provenance string that is included in the verifier-signed receipt.

## Write path

1. The E09 authority authenticates an observer workload.
2. `E09AuthorityService.append_observation` resolves the domain binding from the injected, trusted `E09DomainRegistry`; the caller cannot supply or override the binding.
3. The authority writes the Observation as actor role `observer`, with the workload identity in the integrity envelope.
4. `append_prediction_commit` derives the same domain tuple from the prior Observation. A caller-supplied mismatch is rejected.
5. `append_evidence_reveal` derives the tuple from the committed Observation and rejects caller or commit mismatches before writing the evaluator reveal.
6. The evidence resolver independently verifies Observation → Commit → Reveal domain equality and derives `world_family` from Observation.
7. The verifier signs only the resolver-derived Evidence DTO. The source registry ID/version are retained in its provenance.
8. E12-A6 verifies the verifier signature and receipt bindings; it does not maintain a second domain registry.

## Compatibility and migration

E09 v0.3 remains the event protocol version for existing query/scope/split semantics. Domain provenance is an additional closed, versioned metadata contract (`e09-domain-provenance@1`) rather than a global protocol-version bump.

Historical v0.3 Observation/Commit/Reveal chains without authenticated observer identity and the domain tuple remain readable and replayable, but are not eligible for the trusted E09 → E12-A6 receipt path. There is no inference from scope strings, episode IDs, caller labels, or legacy fixtures. They must be re-observed through the authenticated authority path or explicitly migrated by a trusted authority.

Legacy request fields `world_family_by_evidence` and `candidate_evidence_world_family_by_ref` are compatibility assertions only. If supplied, they must exactly match the Observation-derived value; they are never used as the source of truth. New clients should omit them.

## Tests added

- Caller attempts to relabel a valid evidence reference.
- Missing domain provenance fails closed.
- Commit registry-version mismatch is rejected.
- Reveal world-family mismatch is rejected.
- Receipt signing path rejects caller-supplied relabeling.
- Valid receipt retains registry ID/version in signed Evidence provenance.

## Direct store-write audit

The source-level call-site inventory and remaining migration requirements are recorded in [E09 Direct Store-Write Audit v1](E09_DIRECT_STORE_WRITE_AUDIT_V1.md). The legacy adapter below is intentionally not trusted for receipt issuance.

## Existing legacy writer path

`prototype/e09_shared_protocol_adapter.py` still has a trusted-runner prototype path that writes Observation/Commit/Reveal directly through `SQLiteEvidenceStore`, with Observation actor role `runner`. It is not upgraded by this PR and is intentionally not eligible for trusted verifier receipts: the resolver rejects runner-role observations and observations without the authenticated, registry-bound domain tuple. This keeps the older training adapter usable for its existing non-receipt experiments without silently granting it the new evidence authority.

A separate follow-up is required to migrate that adapter to the authenticated authority facade, including observer/learner/evaluator workload credentials and a configured domain registry, before its events can participate in the secure E09 → E12-A6 receipt path.

## Security boundary

The SQLite reference store is not itself an authentication or process-isolation boundary. Event digests provide integrity binding, not source identity. Production must ensure only the authenticated E09 authority service can write to the E09 database, using a dedicated process, restricted database permissions and authenticated IPC. Direct database access by learner/evaluator workloads remains outside this in-process reference implementation's guarantee.
