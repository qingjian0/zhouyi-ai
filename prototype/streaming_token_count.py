"""Exact token counting over bounded text chunks.

A tokenizer adapter must preserve its internal state between calls and emit only
IDs that can no longer change when later text arrives. Concatenating all IDs
returned by feed(..., final=False) and the final flush must equal the tokenizer's
ordinary whole-document encoding. Chunk-local encode(text) counts are NOT exact
for arbitrary BPE/tokenizer boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


class TokenStreamContractError(ValueError):
    """Raised when an incremental tokenizer violates the streaming contract."""


class IncrementalTokenizer(Protocol):
    """Stateful adapter around a concrete tokenizer implementation."""

    tokenizer_id: str

    def feed(self, text: str, *, final: bool = False) -> Sequence[int]:
        """Consume text and return newly finalized token IDs.

        The implementation must retain any suffix whose tokenization may
        change after future input. On final=True it must flush all remaining
        state. Calling final=True more than once is not supported.
        """


@dataclass(frozen=True)
class TokenCountResult:
    tokenizer_id: str
    token_count: int
    chunks: int
    characters: int


def count_token_stream(
    chunks: Iterable[str], tokenizer: IncrementalTokenizer
) -> TokenCountResult:
    """Count one logical document without resetting tokenizer state at chunks."""
    tokenizer_id = getattr(tokenizer, "tokenizer_id", None)
    if not isinstance(tokenizer_id, str) or not tokenizer_id.strip():
        raise TokenStreamContractError("tokenizer_id must be a stable non-empty string")

    total = 0
    chunk_count = 0
    character_count = 0

    def consume(text: str, *, final: bool) -> None:
        nonlocal total
        token_ids = tokenizer.feed(text, final=final)
        if isinstance(token_ids, (str, bytes)) or not isinstance(token_ids, Sequence):
            raise TokenStreamContractError("feed() must return a sequence of token IDs")
        for token_id in token_ids:
            if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
                raise TokenStreamContractError("token IDs must be non-negative integers")
        total += len(token_ids)

    for chunk in chunks:
        if not isinstance(chunk, str):
            raise TokenStreamContractError("document chunks must be strings")
        consume(chunk, final=False)
        chunk_count += 1
        character_count += len(chunk)

    consume("", final=True)
    return TokenCountResult(
        tokenizer_id=tokenizer_id,
        token_count=total,
        chunks=chunk_count,
        characters=character_count,
    )


def count_evidence_document(
    store,
    document_id: str,
    tokenizer: IncrementalTokenizer,
    *,
    page_size: int = 128,
) -> TokenCountResult:
    """Count a completed SQLiteEvidenceIngestor document as one token stream.

    The document is read in bounded pages, but tokenizer state is continuous
    across every chunk and page. This does not trust or sum per-chunk token_count
    fields, which may have been produced by independent chunk encodes.
    """
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= store.MAX_PAGE_ROWS:
        raise TokenStreamContractError(
            f"page_size must be between 1 and {store.MAX_PAGE_ROWS}"
        )
    state = store.document_state(document_id)
    if state is None:
        raise TokenStreamContractError("document does not exist")
    _, _, complete = state
    if not complete:
        raise TokenStreamContractError("document must be complete before exact token counting")

    def text_pages():
        offset = 0
        while True:
            page = store.get_chunks(document_id, limit=page_size, offset=offset)
            if not page:
                break
            for chunk in page:
                yield chunk.text
            offset += len(page)
            if len(page) < page_size:
                break

    return count_token_stream(text_pages(), tokenizer)
