"""TX-02 representation codebooks.

These codebooks provide reversible symbol encodings for benchmark experiments.
They are not trained learners and do not establish that any encoding is better.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

FAMILIES = ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "LEARNED_INIT", "PERMUTED")


def _width(cardinality: int, base: int) -> int:
    width = 1
    capacity = base
    while capacity < cardinality:
        width += 1
        capacity *= base
    return width


def _digits(value: int, base: int, width: int) -> tuple[int, ...]:
    result = [0] * width
    remaining = value
    for index in range(width - 1, -1, -1):
        result[index] = remaining % base
        remaining //= base
    return tuple(result)


@dataclass(frozen=True)
class StateCodebook:
    family: str
    cardinality: int
    codewords: tuple[tuple[float, ...], ...]

    @property
    def dimension(self) -> int:
        return len(self.codewords[0])

    def encode(self, symbol: int) -> tuple[float, ...]:
        if type(symbol) is not int or not 0 <= symbol < self.cardinality:
            raise ValueError(f"symbol must be an integer in [0, {self.cardinality})")
        return self.codewords[symbol]

    def decode(self, codeword: Iterable[float]) -> int:
        key = tuple(codeword)
        reverse = {word: symbol for symbol, word in enumerate(self.codewords)}
        try:
            return reverse[key]
        except (KeyError, TypeError):
            raise ValueError("codeword is not a valid code in this codebook") from None


def build_codebook(cardinality: int, family: str, seed: int = 0) -> StateCodebook:
    if type(cardinality) is not int or cardinality < 2:
        raise ValueError("cardinality must be an integer >= 2")
    if family not in FAMILIES:
        raise ValueError(f"family must be one of {FAMILIES}")

    binary_width = _width(cardinality, 2)
    ternary_width = _width(cardinality, 3)
    rng = random.Random(seed)

    if family == "BINARY":
        words = [_digits(i, 2, binary_width) for i in range(cardinality)]
    elif family == "TERNARY":
        words = [_digits(i, 3, ternary_width) for i in range(cardinality)]
    elif family == "HYBRID":
        words = [
            _digits(i, 2, binary_width) + _digits(i, 3, ternary_width)
            for i in range(cardinality)
        ]
    elif family == "ONE_HOT":
        words = [
            tuple(1 if i == j else 0 for j in range(cardinality))
            for i in range(cardinality)
        ]
    elif family == "LEARNED_INIT":
        dimension = max(2, binary_width + ternary_width)
        words = [
            tuple(rng.uniform(-1.0, 1.0) for _ in range(dimension))
            for _ in range(cardinality)
        ]
    else:  # PERMUTED: preserve ternary codewords, randomize symbol assignment.
        words = [_digits(i, 3, ternary_width) for i in range(cardinality)]
        rng.shuffle(words)

    normalized = tuple(tuple(float(value) for value in word) for word in words)
    if len(set(normalized)) != cardinality:
        raise RuntimeError("encoder produced a non-injective codebook")
    return StateCodebook(family, cardinality, normalized)
