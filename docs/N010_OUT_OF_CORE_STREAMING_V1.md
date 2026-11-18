# N0.10 out-of-core streaming v1

## Scope

This integration adds a deterministic JSONL experiment runner and a SQLite-backed metadata index for N0.10. Training and development records are streamed from one immutable input artifact; locked-test labels are opened only by the separate evaluation entry point.

## Runtime design

- JSONL rows are parsed one at a time with a configurable per-record byte limit.
- A temporary SQLite index stores split and source-group metadata rather than materializing the complete row graph in Python.
- Every stream iteration checks the dataset digest and record metadata before yielding training examples.
- Train/dev group overlap is rejected; each row must carry a source grouping key.
- Full-batch training reopens the deterministic stream for each epoch, accumulates gradients against frozen weights, and applies one update per epoch. It is not mini-batch SGD.
- Checkpoint resume binds to the dataset manifest and the digest of the SQLite group index.
- Locked-test evaluation is a separate API and checks the training group index before evaluation.

## Validation included

- Stream repeatability and source-group leakage rejection.
- Exact parity between materialized and reiterable full-batch updates.
- Dataset drift, checkpoint/index tampering, missing index and resume rejection tests.
- Subprocess RSS scaling smoke test and platform-specific `ru_maxrss` unit normalization.
- An opt-in million-row-per-split benchmark script.

## Claim boundary

The implementation is a bounded-memory data/experiment path for the declared N0.10 synthetic task. The unit tests and RSS smoke test do not establish a universal constant-memory guarantee, production-scale throughput, real-world reasoning ability, or generalization beyond the benchmark's declared data families. The million-row benchmark is opt-in and its results must be reported with the exact commit, environment, split sizes, epochs, wall time and peak RSS.
