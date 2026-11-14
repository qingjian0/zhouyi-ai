# ZPCM v0.1 bounded persistent memory projection

日期：2026-11-11；状态：可运行参考实现，不是完整 ZPCM/DCMF。

## Ownership
E09 remains authoritative for protocol events and evidence visibility. ZPCM stores an append-only, idempotent projection plus typed assertions and bounded retrieval. E12-A6 remains the only candidate lifecycle authority. This does not create a second evidence ledger.

## Implemented
- SQLite append-only journal with SHA-256 content digests and idempotent event IDs.
- E09 projection filtered by learner track; non-SUPPORT labels are always redacted; SUPPORT labels require explicit opt-in and default off.
- Typed assertions retain source provenance and explicit ACTIVE/CONTESTED/RETRACTED states.
- Scope-isolated retrieval with item and byte budgets plus honest completeness/truncation.
- Integrity check and reopen persistence tests.

## Limits
No vector/embedding retrieval, temporal interval reasoning, process ACL isolation, automatic consolidation or crash-safe E09 learner restore. Raw observations are not copied; source payload references remain authoritative. ZPCM is a rebuildable derived view in this slice.
