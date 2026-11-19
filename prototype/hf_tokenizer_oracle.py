"""Optional Hugging Face Tokenizers adapter and exact chunk-boundary oracle.

The adapter deliberately buffers a complete logical document and invokes the
canonical Tokenizers encode() once. It is a real-tokenizer correctness oracle,
not a bounded-memory incremental implementation.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from prototype.tokenizer_adapters import BufferedTokenizerOracle


class HuggingFaceTokenizerUnavailable(RuntimeError):
    """Raised when the optional tokenizers package is not installed."""


def load_tokenizer_oracle(tokenizer_json: str, *, tokenizer_id: str):
    """Load a Hugging Face Tokenizers JSON and wrap its canonical encode API."""
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise HuggingFaceTokenizerUnavailable(
            "Install the optional dependency with: pip install 'zhouyi-ai-cpg-ei[tokenizers]'"
        ) from exc
    tokenizer = Tokenizer.from_file(tokenizer_json)
    return BufferedTokenizerOracle(tokenizer_id, lambda text: tokenizer.encode(text).ids)


@dataclass(frozen=True)
class ChunkBoundaryParity:
    tokenizer_id: str
    text_characters: int
    canonical_token_count: int
    chunk_sizes: tuple[int, ...]
    token_ids_equal: bool


def verify_chunk_boundary_parity(
    encode,
    *,
    tokenizer_id: str,
    text: str,
    chunk_sizes: Iterable[int],
) -> ChunkBoundaryParity:
    """Compare emitted token IDs against canonical whole-text encode exactly."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    sizes = tuple(chunk_sizes)
    if any(isinstance(size, bool) or not isinstance(size, int) or size < 0 for size in sizes):
        raise ValueError("chunk sizes must be non-negative integers")
    if sum(sizes) != len(text):
        raise ValueError("chunk sizes must sum to the text length")

    canonical = tuple(encode(text))
    oracle = BufferedTokenizerOracle(tokenizer_id, encode)
    emitted: list[int] = []
    offset = 0
    for size in sizes:
        emitted.extend(oracle.feed(text[offset:offset + size], final=False))
        offset += size
    emitted.extend(oracle.feed("", final=True))
    return ChunkBoundaryParity(
        tokenizer_id=tokenizer_id,
        text_characters=len(text),
        canonical_token_count=len(canonical),
        chunk_sizes=sizes,
        token_ids_equal=tuple(emitted) == canonical,
    )
