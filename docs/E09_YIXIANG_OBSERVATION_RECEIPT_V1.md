# E09 Candidate-Bound Yixiang Observation Receipt v1

## Purpose

The M2 → Yixiang/SROK adapter must not treat arbitrary event-ID strings as E09 provenance. A candidate enters the adapter only when it is paired with a short-lived, Ed25519-signed E09 observation receipt.

This receipt binds:
- the trusted E09 verifier identity and audience;
- the E09 episode, scope and learner track;
- the exact M2 candidate `record_id` and canonical `record_digest`;
- each E09 reveal event ID, immutable event-envelope digest and observation ID;
- the trusted domain ID, world family, registry ID and registry version;
- issue and expiry timestamps.

## Issuance boundary

`E09VerifierService.issue_yixiang_observation_receipt` resolves every requested reveal through `resolve_e09_reveal`. The caller cannot supply event digests, observation IDs, world-family metadata or registry metadata. All evidence refs must resolve in the requested episode, scope and learner track and share one active trusted domain binding.

The service signs the closed `e09_observation_receipt@1` schema with the configured verifier signer. The verifier key is configured out-of-band; private signing material must not be present in learner or adapter processes.

## Adapter validation

The Yixiang adapter receives a map from candidate record ID to signed receipt plus an `E09ObservationReceiptVerifier` configured by the trusted application composition root. Before creating SROK nodes, it verifies:
- exact closed schema and audience;
- pinned verifier identity and Ed25519 signature;
- validity interval using verifier-owned time;
- exact candidate ID and canonical body digest;
- candidate scope and current trusted domain-registry binding;
- unique observation/event identities and valid SHA-256 event digests.

Only event IDs from the verified result are copied to SROK evidence IDs. Caller-supplied strings and unsigned dictionaries are rejected. The trusted verifier object and its keyring/registry must be constructed by the service composition root, not from request JSON.

## Provenance and epistemic boundaries

M1 byte-span references remain M1 source provenance. E09 reveal references remain observation provenance. XSL transformation-prior references remain separate and are not copied into E09 evidence IDs.

A valid receipt proves that the trusted E09 verifier signed a particular candidate snapshot ↔ observation-event binding. It does **not** prove semantic truth, causal validity, or correctness of the M2 candidate. Yixiang/SROK/CSG-GCR outputs remain `HYPOTHESIS_ONLY`; this adapter does not consume E12-A6 authorization receipts or advance lifecycle state.

## Operational limitations

This is an in-process trust boundary. It does not isolate SQLite files, signing keys, or verifier code from other code running under the same OS identity. Production deployment still requires the authenticated process/IPC separation described in issue #282. Receipt expiry and domain-registry revocation are checked at adapter verification time; already-produced hypothesis artifacts are historical outputs and must not be treated as current authorization.
