# SROK → E09 durable prequential integration

日期：2026-11-11  
状态：P1 integration slice; uses the existing E09 shared protocol and does not duplicate its event store.

## What this adds
- Canonical JSON encoding for typed SROK observations.
- A thin SROKPrequentialLearner implementing the existing PrequentialRunner learner contract.
- Refit-from-clean-support behavior through the existing E09 EvidenceLedger.
- Existing E09SharedProtocolAdapter persists observation → prediction commit → evidence reveal → structure version → revision.
- E09 structure identity/version fields are configurable; existing E09 defaults remain unchanged.

## Safety semantics
- SUPPORT reveals can enter the learner update path.
- GATE_DEV, GATE_FINAL and LOCKED_TEST are persisted but not delivered to learner revision.
- Role-pool truncation and expansion-budget exhaustion force abstention.
- Ranking scores are not calibrated probabilities.
- Batch refit resets weights and retrains from adjudicated evidence; it is not incremental learning.
- Current evaluator/learner isolation is process-local and is not a security boundary or crash-safe exactly-once learning.

## P1 boundary
This is a trusted single-process SROK-to-E09 prequential reference loop. It does not yet provide process isolation, crash recovery, ZPCM memory projection, device benchmarks or higher-order necessity proof.
