"""Explicit mixed-radix codebooks for XRA.

Semantic state cardinality and coordinate radix are deliberately separate:
three semantic states can be encoded in base 2 (two bits) or base 3 (one trit).
This module is an encoding primitive, not a learner or a claim of superiority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def _capacity(radix: int, digits: int) -> int:
    if isinstance(radix, bool) or not isinstance(radix, int) or radix < 2:
        raise ValueError("radix must be an integer >= 2")
    if isinstance(digits, bool) or not isinstance(digits, int) or digits < 1:
        raise ValueError("digits must be an integer >= 1")
    return radix ** digits


def _to_digits(code: int, radix: int, digits: int) -> tuple[int, ...]:
    capacity = _capacity(radix, digits)
    if isinstance(code, bool) or not isinstance(code, int) or not 0 <= code < capacity:
        raise ValueError("code is outside the representable range")
    out = [0] * digits
    value = code
    for index in range(digits - 1, -1, -1):
        out[index] = value % radix
        value //= radix
    return tuple(out)


def _from_digits(values: Sequence[int], radix: int) -> int:
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError("digits must be a non-empty tuple or list")
    code = 0
    for digit in values:
        if isinstance(digit, bool) or not isinstance(digit, int) or not 0 <= digit < radix:
            raise ValueError("each digit must be an integer in [0, radix)")
        code = code * radix + digit
    return code


@dataclass(frozen=True)
class RadixCodebook:
    """Injective mapping from semantic state IDs to fixed-width radix codes.

    symbol_to_code stores integer codewords, not digit tuples. Its position
    is the stable semantic state ID. Unused codewords decode to None.
    """
    radix: int
    digits: int
    symbol_to_code: tuple[int, ...]

    def __post_init__(self) -> None:
        capacity = _capacity(self.radix, self.digits)
        if not isinstance(self.symbol_to_code, tuple) or not self.symbol_to_code:
            raise ValueError("symbol_to_code must be a non-empty tuple")
        if len(self.symbol_to_code) > capacity:
            raise ValueError("semantic states exceed codebook capacity")
        if any(isinstance(code, bool) or not isinstance(code, int)
               or not 0 <= code < capacity for code in self.symbol_to_code):
            raise ValueError("every codeword must be an integer within capacity")
        if len(set(self.symbol_to_code)) != len(self.symbol_to_code):
            raise ValueError("codebook must be injective")

    @property
    def semantic_cardinality(self) -> int:
        return len(self.symbol_to_code)

    @property
    def capacity(self) -> int:
        return self.radix ** self.digits

    @property
    def unused_codes(self) -> int:
        return self.capacity - self.semantic_cardinality

    def encode(self, symbol_id: int) -> tuple[int, ...]:
        if (isinstance(symbol_id, bool) or not isinstance(symbol_id, int)
                or not 0 <= symbol_id < self.semantic_cardinality):
            raise ValueError("unknown semantic state ID")
        return _to_digits(self.symbol_to_code[symbol_id], self.radix, self.digits)

    def decode(self, digits: Sequence[int]) -> int | None:
        if len(digits) != self.digits:
            raise ValueError("digit width does not match codebook")
        code = _from_digits(digits, self.radix)
        try:
            return self.symbol_to_code.index(code)
        except ValueError:
            return None


def canonical_codebook(semantic_cardinality: int, radix: int) -> RadixCodebook:
    """Assign semantic IDs to consecutive codewords in the chosen radix."""
    if (isinstance(semantic_cardinality, bool)
            or not isinstance(semantic_cardinality, int)
            or semantic_cardinality < 1):
        raise ValueError("semantic_cardinality must be an integer >= 1")
    if isinstance(radix, bool) or not isinstance(radix, int) or radix < 2:
        raise ValueError("radix must be an integer >= 2")
    digits = 1
    while radix ** digits < semantic_cardinality:
        digits += 1
    return RadixCodebook(radix, digits, tuple(range(semantic_cardinality)))


def permuted_codebook(
    semantic_cardinality: int, radix: int, code_order: Sequence[int]
) -> RadixCodebook:
    """Build a codebook from an explicit permutation of codeword assignments."""
    if len(code_order) != semantic_cardinality:
        raise ValueError("code_order length must equal semantic_cardinality")
    digits = 1
    while radix ** digits < semantic_cardinality:
        digits += 1
    return RadixCodebook(radix, digits, tuple(code_order))


def minimum_digits(semantic_cardinality: int, radix: int) -> int:
    """Return the minimum fixed-width digit count without floating-point logs."""
    if (isinstance(semantic_cardinality, bool)
            or not isinstance(semantic_cardinality, int)
            or semantic_cardinality < 1):
        raise ValueError("semantic_cardinality must be an integer >= 1")
    _capacity(radix, 1)
    digits = 1
    while radix ** digits < semantic_cardinality:
        digits += 1
    return digits
