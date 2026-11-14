# E09/SROK trusted-process crash resume v0.1

日期：2026-11-11  
状态：可测试的单进程恢复切片；不是 OS 级 evaluator/learner 隔离。

## Durable state
- E09 stores canonical observation input payloads in a digest-addressed payload vault.
- Initial and post-revision structure versions store the learner snapshot plus the SUPPORT evidence-ledger snapshot and runner version/step.
- Prediction commits continue to reference the immutable input payload digest.
- Evidence reveals and revisions remain in the E09 append-only episode log.

## Resume algorithm
1. Replay the episode and load the latest structure checkpoint.
2. Verify and restore the SROK learner snapshot.
3. Restore the E09 SUPPORT ledger from the checkpoint.
4. Reconstruct all prediction commits from protocol events plus digest-verified input payloads.
5. Reconstruct SUPPORT reveals; append any reveal newer than the latest checkpoint exactly once.
6. Reconstruct revision deduplication state.
7. If a structure version was committed but its following revision event was interrupted, use that structure's support-evidence reference as the durable completion marker and synthesize the in-memory dedupe record.
8. Resume prediction/reveal/revision with existing event IDs and monotonic model version.

## Delivery and recovery semantics
- At-least-once replay with idempotent event/payload IDs; no distributed exactly-once claim.
- Missing/tampered input payloads fail closed.
- Generic ZPCM projection continues to redact reveal labels.
- The current SQLite store and adapter remain trusted single-process components. The payload vault and event table do not provide OS-level ACL isolation or cryptographic evaluator authentication.

## Acceptance covered
- Payload digest binding and idempotent storage.
- Restart after a completed revision restores the same SROK learner snapshot.
- Restart after a durable SUPPORT reveal but before revision reconstructs pending learning evidence.
- Repeated revision of a completed reveal is blocked by reconstructed runner state.

## Remaining security gate
Evaluator and learner must still be moved behind separate OS identities/processes with authenticated IPC and signed reveal envelopes before claiming adversarial isolation. Device crash/power-loss fault injection and atomic multi-process learner checkpointing remain future hardening.
