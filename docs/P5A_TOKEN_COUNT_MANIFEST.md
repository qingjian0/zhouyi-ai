# P5-A exact token-count persistence manifest

`prototype/token_count_manifest.py` persists a whole-document token count only after the document has been counted through the stateful `IncrementalTokenizer` contract.

## Identity and invalidation

Each record is keyed by `(document_id, tokenizer_id)` and stores:
- exact token count, character count, and chunk count;
- the evidence document's immutable manifest digest;
- the evidence chunk generation observed before counting.

The implementation checks the evidence identity before counting and again inside the write transaction. If evidence changes during counting, the result is not persisted. Reads return a record only while the current evidence digest and generation still match. A different tokenizer revision uses a different identity and cannot silently reuse a previous count.

## Example

```python
from prototype.token_count_manifest import (
    count_and_persist_evidence_document,
    get_token_count_manifest,
)

manifest = count_and_persist_evidence_document(
    store, "document-v1", incremental_tokenizer, page_size=128
)
cached = get_token_count_manifest(
    store, "document-v1", incremental_tokenizer.tokenizer_id
)
```

## Claim boundaries

- This persists a count; it does not make a buffered oracle bounded-memory.
- The caller must supply a stable tokenizer identity that includes model/revision and tokenizer asset digest. The module does not independently hash or attest the tokenizer asset.
- Exactness still depends on the supplied adapter satisfying whole-document token-ID parity.
- No production model tokenizer or 1M input/output device run is certified.
