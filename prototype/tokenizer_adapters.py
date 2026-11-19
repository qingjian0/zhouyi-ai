"""Reference adapter for exact whole-document tokenizer parity.

This adapter intentionally buffers the complete logical document and calls the
underlying tokenizer exactly once at finalization. It is a correctness oracle
and compatibility bridge, NOT a bounded-memory streaming tokenizer. Production
adapters should replace it only after proving chunk-boundary parity against this
oracle and the tokenizer's canonical whole-document encode API.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence


class BufferedTokenizerOracle:
    """Adapt a canonical whole-text encoder to the IncrementalTokenizer API."""

    def __init__(
        self,
        tokenizer_id: str,
        encode: Callable[[str], Sequence[int]],
    ) -> None:
        if not isinstance(tokenizer_id, str) or not tokenizer_id.strip():
            raise ValueError("tokenizer_id must be a stable non-empty string")
        if not callable(encode):
            raise TypeError("encode must be callable")
        self.tokenizer_id = tokenizer_id
        self._encode = encode
        self._parts: list[str] = []
        self._finalized = False

    @property
    def buffered_characters(self) -> int:
        """Number of buffered source characters (memory grows with input)."""
        return sum(map(len, self._parts))

    def feed(self, text: str, *, final: bool = False) -> Sequence[int]:
        if self._finalized:
            raise RuntimeError("tokenizer oracle has already been finalized")
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        self._parts.append(text)
        if not final:
            return ()

        self._finalized = True
        encoded = self._encode("".join(self._parts))
        if isinstance(encoded, (str, bytes)) or not isinstance(encoded, Sequence):
            raise TypeError("canonical encode() must return a sequence of token IDs")
        token_ids = tuple(encoded)
        for token_id in token_ids:
            if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
                raise ValueError("canonical encode() returned an invalid token ID")
        self._parts.clear()
        return token_ids
