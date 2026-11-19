# P5-A whole-document tokenizer scale oracle

Status: reproducible large-input canonical count/resource benchmark. It is a
reference baseline, not bounded-memory streaming.

## Run a one-million-token check

```bash
pip install 'zhouyi-ai-cpg-ei[tokenizers]'
python -m prototype.hf_tokenizer_scale_benchmark corpus.txt tokenizer.json \
  --tokenizer-id 'model-name@revision'
```

The default expected count is exactly 1,000,000 tokenizer IDs. A mismatch is
reported and the command exits with status 3; it never pads, truncates, or
adjusts the corpus to manufacture a match. Use `--allow-any-count` only for
exploratory measurements.

## Report

The JSON contains source and tokenizer asset SHA-256 digests, exact whole-text
token count, source byte/character counts, elapsed time, throughput, runtime
platform, and sampled process RSS when supported. The tokenizer identity is
caller-supplied and should include model and revision; the asset digest is
computed independently and recorded in the result.

## Critical limits

- This invokes the canonical Hugging Face `Tokenizer.encode(full_text)` API.
- The complete UTF-8 source and returned token ID sequence are resident in
  memory. The benchmark therefore measures an oracle upper-memory baseline,
  not a bounded-memory production stream.
- It does not prove chunk-boundary parity for a production incremental adapter.
- It does not establish a 1M-token result until run with an actual source corpus
  and production tokenizer JSON. A generated fixture tokenizer is only a test.
- A run on a desktop does not establish mobile feasibility. Run separately on
  each target device and retain raw JSON plus device/OS/thermal/power metadata.
- Sampled RSS can miss short-lived peaks; it is not accelerator memory.
