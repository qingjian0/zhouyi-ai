# E09 Direct Store-Write Audit v1

Date: 2026-11-12
Audited revision: `ce8145525ed148e6d00592be4875282b3fb7157f`
Scope: Python runtime/prototype modules under `prototype/`; test fixtures are not production writers.

## Result

The audit found two production modules with direct event-store writes:

1. `prototype/e09_authority_services.py`
   - Expected and intentional authority boundary.
   - Its narrow methods authenticate a workload, derive the actor role, bind the domain registry tuple, and then call the private store writer.
   - The class has no generic caller-facing append method.
2. `prototype/e09_shared_protocol_adapter.py`
   - Legacy trusted-runner integration, not an authenticated workload boundary.
   - Directly writes `structure_version`, `observation`, `prediction_commit`, `evidence_reveal`, and `revision` events through `SQLiteEvidenceStore` methods.
   - It remains usable for its legacy prequential/training experiments, but it is not eligible to create trusted verifier receipts. The receipt resolver rejects runner-role observations and observations without authenticated, registry-bound domain provenance.

No other `prototype/` Python runtime module in the audited tree directly invokes `append_event`, `commit_prediction`, `reveal_evidence`, `append_revision`, or constructs `SQLiteEvidenceStore` as an event writer. The shared store implementation necessarily owns the generic low-level append primitives. Tests contain direct writes as protocol fixtures and are not production entry points.

## Security interpretation

This is a source-level call-site audit, not proof of process isolation. `E09AuthorityService` and `SQLiteEvidenceStore` currently coexist in one Python process, and code holding the store object can bypass the facade. Hash chains and signed receipts do not prevent a process with database write access from fabricating source events.

Therefore the current guarantee is:

- Trusted receipt issuance is fail-closed against legacy runner observations and caller-controlled domain relabeling.
- The legacy adapter remains a non-authoritative experiment path.
- Production-grade source authentication still requires a dedicated authority process, restricted database permissions, authenticated IPC, and removal of learner/evaluator direct database write access.

## Follow-up required before production promotion

1. Add authenticated facade operations for the adapter's structure-version and revision events, with learner identity and strict causation/evidence binding.
2. Migrate `E09SharedProtocolAdapter` observation, prediction commit, and reveal writes to authenticated observer/learner/evaluator credentials and the configured domain registry.
3. Keep legacy mode explicitly non-receipt-eligible; do not silently upgrade old runner events.
4. Add a static architecture guard over production `prototype/` modules so new direct store-writer call sites must be explicitly allowlisted and reviewed.
5. Move the authority/store behind a process boundary and verify that learner/evaluator workloads cannot open or mutate the underlying SQLite database.

Until these steps are complete, this audit must not be described as production-grade process isolation.
