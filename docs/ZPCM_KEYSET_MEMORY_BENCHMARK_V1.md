# ZPCM Keyset Reader Memory Benchmark v1

## Purpose

Measure the incremental memory cost of reading a typed ZPCM event stream through keyset pagination. The benchmark deliberately reports two different measurements:

- **Python allocation peak** from `tracemalloc`, useful for Python-managed object growth.
- **Process RSS** sampled from Linux `/proc/self/statm`, which includes native allocations and SQLite page-cache effects.

Neither measurement is a model KV-cache measurement.

## Run

From the repository root:

```bash
python benchmarks/benchmark_zpcm_keyset_memory.py --events 10000 --page-size 128 --payload-bytes 256
```

Sweep page sizes while keeping event count and payload size fixed:

```bash
for page in 16 32 64 128 256 512; do
  python benchmarks/benchmark_zpcm_keyset_memory.py --events 10000 --page-size "$page" --payload-bytes 256
done
```

Then hold page size fixed and increase the durable event count:

```bash
for count in 1000 10000 50000; do
  python benchmarks/benchmark_zpcm_keyset_memory.py --events "$count" --page-size 128 --payload-bytes 256
done
```

## Interpretation

The reader fetches at most `page_size` raw SQLite rows per query and decodes each payload while yielding it. The expected Python working-memory growth should be governed primarily by page size and payload size, rather than the total number of historical events.

The benchmark samples RSS during iteration and reports the peak above the pre-iteration baseline. RSS sampling itself has overhead; use repeated runs and compare trends rather than treating one sample as a hard bound.

This benchmark does **not** establish a hard process-memory ceiling. SQLite page cache, allocator behavior, Python object overhead, evidence verification, the TRLW selected packet, and downstream SROK/CSG-GCR structures all contribute to total runtime RSS. Measure those layers separately before making a whole-agent memory claim.

## Acceptance target for future optimization

For fixed page size and payload size, increasing total historical event count should not cause a proportional increase in the reader's incremental Python allocation peak. For fixed total event count, increasing page size should show a predictable increase in peak allocation/RSS. Record the Python version, OS, page size, payload size, event count, elapsed time, Python allocation peak, and RSS baseline/peak/delta for every comparison.
