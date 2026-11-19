# P5-A: real tokenizer oracle and chunk-boundary parity

Status: optional Hugging Face Tokenizers adapter, runtime JSON loading test, and exact token-ID parity harness added. A bounded-memory production streaming adapter and 1M device measurements remain unverified.

## Adapter

`prototype/hf_tokenizer_oracle.py` loads a tokenizer JSON with the optional `tokenizers` package and wraps its canonical `Tokenizer.encode(text).ids` API in `BufferedTokenizerOracle`.

Install the optional extra:

```bash
pip install 'zhouyi-ai-cpg-ei[tokenizers]'
```

Example:

```python
from prototype.hf_tokenizer_oracle import load_tokenizer_oracle
from prototype.streaming_token_count import count_token_stream

oracle = load_tokenizer_oracle(
    "tokenizer.json",
    tokenizer_id="model-name@revision:tokenizer-json-sha256",
)
result = count_token_stream(document_chunks, oracle)
print(result.token_count)
```

Use a stable tokenizer identity that includes the model/revision and tokenizer asset revision or digest. Never reuse persisted counts across tokenizer identity changes. The caller is responsible for supplying this identity; the loader does not calculate or attest to the asset digest.

## Exact parity gate

`verify_chunk_boundary_parity` compares the exact emitted token-ID sequence with the canonical whole-text encode output. Equal token counts alone are insufficient. The parity harness computes the canonical sequence once and reuses it as the oracle result, avoiding a second full-document tokenization during a large check.

Tests cover CJK, emoji, accented characters, whitespace, punctuation, long runs, and chunk boundaries at the beginning, middle, and end. An optional runtime integration test builds a real Hugging Face BPE tokenizer, serializes it to `tokenizer.json`, reloads it through `Tokenizer.from_file`, and checks exact token IDs and document counts. Research-branch CI installs the optional package so this integration test runs there; default core-only test runs skip it if the extra is absent.

## Limitations

- The oracle buffers the complete document and therefore has memory proportional to input size.
- It is a correctness reference, not an incremental bounded-memory tokenizer.
- The runtime test uses a generated fixture tokenizer, not a released production model tokenizer.
- No production tokenizer asset is bundled; no particular model tokenizer or 1M corpus has been certified.
- Hugging Face Tokenizers is optional, preserving the dependency-free core.
- Production streaming requires a tokenizer-specific safe-boundary strategy or equivalent stateful API, exact token-ID parity, bounded suffix memory, and measured peak RSS.
