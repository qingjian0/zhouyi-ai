# M1 Streaming Ingestion Benchmark

Use a fresh database for each run. The benchmark streams an existing UTF-8 file, measures process RSS with M0, and reports SQLite/WAL size and throughput.

```bash
python -m prototype.benchmark_streaming_ingest input.txt run.sqlite3 \
  --document-id corpus-v1 --chunk-bytes 8192 --json
```

For exact token accounting, supply a tokenizer adapter importable in the current Python environment:

```bash
python -m prototype.benchmark_streaming_ingest input.txt run.sqlite3 \
  --document-id corpus-v1 --tokenizer your_adapter:count_tokens --json
```

The adapter callable receives one decoded chunk and returns the exact integer token count for that chunk. Use a tokenizer whose chunk-boundary behavior is documented; chunk-wise token counts may differ from whole-document tokenization if the tokenizer merges across chunk boundaries. For a release gate, also compare the sum against a whole-document reference count or use tokenizer-native incremental state.

The benchmark refuses an existing database path to prevent accidental reuse of completed data. Run each size in a fresh process and fresh database. Current RSS sampling is supplementary; retain OS high-water/cgroup metrics for strict memory gates. The benchmark does not itself establish a 1M-token pass.
