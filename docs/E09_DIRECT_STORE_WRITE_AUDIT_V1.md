# E09 Direct Store-Write Audit v1

Date: 2026-11-12
Original audit revision: `ce8145525ed148e6d00592be4875282b3fb7157f`
Migration revision: `security/e09-adapter-authority-migration-v1-2026-11-12`
Scope: Python runtime/prototype modules under `prototype/`; test fixtures are not production writers.

## Original inventory

The original source-level scan found two runtime modules containing low-level event-store writes:

1. `prototype/e09_authority_services.py`
   - Intended authority boundary.
   - Narrow methods authenticate workload identity, derive actor role, bind domain provenance, and then write through the store.
2. `prototype/e09_shared_protocol_adapter.py`
   - Contains a compatibility-only legacy trusted-runner path.
   - The default legacy mode writes Observation, Commit, Reveal, StructureVersion and Revision events directly and remains non-receipt-eligible.

## Authenticated adapter migration

The adapter now has an explicit secure mode requiring:
- an `E09AuthorityService` with a configured trusted `E09DomainRegistry`;
- observer, learner and evaluator credentials, validated against the adapter scope before bootstrap;
- authority-routed Observation, Prediction Commit, Evidence Reveal, StructureVersion and Revision writes.

The secure mode uses narrow authority operations only. The adapter still uses the store for payload-vault writes, replay/read access and memory projection; these are not event-writer operations. Legacy mode remains available for historical prequential experiments and is not upgraded implicitly. Its runner-role Observation events remain ineligible for trusted receipts.

The authority facade now validates:
- authenticated learner role and scope for StructureVersion and Revision;
- learner-track and scope binding on the persisted payload;
- prior parent versions and support reveals within the same episode, structure, scope and learner track;
- explicit causation links from support/trigger evidence and from resulting structure events.

## Static guard

`tests/test_e09_store_write_allowlist.py` keeps the two reviewed low-level writer modules explicitly allowlisted. This is a source-level guard: it does not prove that secure-mode control flow can never reach a legacy branch, nor does it establish a process boundary. Secure-mode integration tests exercise the authority-routed path and assert authenticated actor metadata across the full event chain.

## Security boundary and remaining work

This remains an in-process reference implementation. `E09AuthorityService` and `SQLiteEvidenceStore` coexist in one Python process; code holding the store object can bypass the facade. Hash chains and signed receipts do not prevent a process with database write access from fabricating source events.

Before production promotion:
1. Move authority and store into a dedicated authority process.
2. Restrict database file and write permissions so learner/evaluator workloads cannot open or mutate it.
3. Expose authenticated IPC with role-, scope-, episode- and track-bound request schemas.
4. Test process-level denial, restart/replay and partial-failure recovery across the IPC boundary.

Current guarantee: secure adapter calls are authenticated and registry-bound through the in-process facade; legacy mode remains explicitly non-authoritative; production-grade process isolation is not yet implemented.
