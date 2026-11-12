# CPG-EI learning-rate confirmation

## Motivation

The first known-support sweep found a strong monotonic improvement from learning rates 0.05 through 0.7. That result is a useful optimization signal, but two seeds are insufficient to establish robustness, and the tested range does not establish whether 0.7 is near an optimum.

This follow-up uses five fresh partition seeds and a wider learning-rate range. It is stacked on the known-support optimizer diagnostic and does not change default model training.

## Protocol

- Fresh seeds: 173, 211, 257, 307, 353. These are not used by the preceding optimizer sweep (seeds 11 and 47).
- Three finite six-bit parity families; exact support is supplied as an oracle to isolate optimization from candidate discovery.
- 40 training states and 12 locked states per seed/family.
- Learning rates: 2.1, 4.2, 6.0, 8.4, 12.0. These are scaled 6× to compensate for the corrected output-head gradient normalization (mean over six heads).
- Both existing regularization configurations; 800 epochs.
- Training uses only the 40 training states.
- The existing sweep implementation selects a configuration using mean final training BCE only. Locked and full-domain metrics remain report-only.
- Report per-configuration metrics and the aggregate summary. Treat each seed/family result as important; do not infer broad generalization from the small locked split.

## Decision rule

The experiment tests whether the improvement at 0.7 is reproducible on fresh partitions and whether higher rates improve training fit without unstable or degraded behavior. A follow-up learning-rate choice must be based on training-only selection and confirmed on a further untouched split before it becomes a default.

## Claim boundary

Synthetic six-bit parity only, with oracle-supplied support. This is not evidence of open-world relation induction, natural-language reasoning, or production training readiness.


## Gradient normalization update

The exact-head audit corrected output-weight gradients from 1/N to 1/(6N), matching the mean BCE objective across six output heads. This changes the SGD step scale by 6×. The original rate grid and its results are retained only as pre-correction historical measurements; this confirmation reruns the equivalent nominal step scales on the corrected implementation.