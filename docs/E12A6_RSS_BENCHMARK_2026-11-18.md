# E12-A6 restore RSS benchmark (2026-11-18)

## Provenance

- Workflow: [Run 44334530274](https://github.com/qingjian0/zhouyi-ai/actions/runs/44334530274)
- Benchmark artifact: `e12a6-restore-rss-1faf564677398132c7f55132764a7c112afe9e8c` (Artifact ID `14441690329`)
- Benchmark code revision: `1faf564677398132c7f55132764a7c112afe9e8c`
- Runtime: Linux, Python 3.11.18
- Workload: synthetic candidate-registration histories; fixture generation and ZPCM initialization excluded from restore duration.

## Measurements

| Events | Fixture bytes | Restore duration | Events/s | Peak RSS |
|---:|---:|---:|---:|---:|
| 1,000 | 1,753,088 | 0.030689 s | 32,584.51 | 24.68 MiB |
| 10,000 | 16,220,160 | 0.296744 s | 33,699.06 | 27.76 MiB |
| 50,000 | 81,133,568 | 1.482601 s | 33,724.52 | 31.10 MiB |
| 100,000 | 162,664,448 | 2.933532 s | 34,088.60 | 30.96 MiB |
| 500,000 | 835,719,168 | 14.883178 s | 33,594.98 | 30.98 MiB |

Peak RSS is converted from the artifact's `peak_rss_bytes` using 1 MiB = 1,048,576 bytes. At 500,000 events, peak RSS was 32,485,376 bytes (about 30.98 MiB). The measured restore throughput remained close to 33.6k–34.1k events/s across the tested sizes.

## Interpretation and limits

1. The tested candidate-registration workload shows approximately flat peak RSS between 50k and 500k events, while restore time scales approximately linearly with event count.
2. This is evidence for bounded-memory replay under this synthetic workload, not evidence of sublinear or constant-time startup.
3. The fixture contains candidate-registration events only. The artifact reports zero action and evidence projection rows; it does not characterize mixed production event distributions or authorization-heavy replay.
4. cgroup memory current/peak values were unavailable in this runner. The numbers are process RSS from the benchmark's resource sampler.
5. Fixture generation and ZPCM initialization are excluded from `restore_duration_seconds`; do not present the restore duration as end-to-end application startup time.
6. No hardware-independent memory guarantee is established.

## Engineering consequence

Keep the authoritative event log replay and its fail-closed semantic checks. Do not skip replay using the current read-side projection: it is not a complete lifecycle snapshot and cannot by itself prove the integrity of the skipped event prefix. A safe checkpoint design still requires a complete validated state image, a defined event-prefix integrity anchor, atomic checkpoint/event ordering, crash-consistency tests, and full-replay fallback.

The next benchmark expansion should include mixed candidate/evidence/action histories and authorization-consumption events, then measure checkpoint design only after those correctness gates are implemented.
