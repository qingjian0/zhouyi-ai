"""Explicit, convention-safe binary encoding for trigram/hexagram states.

Bit convention: 1 = yang, 0 = yin; line arrays are bottom-to-top.
The 6-bit identifier is a computational index, NOT King Wen sequence order.
No semantic prediction is implied by an encoded state.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Sequence


TRIGRAMS_BOTTOM_TO_TOP = {
    (1, 1, 1): "乾",
    (1, 1, 0): "兑",
    (1, 0, 1): "离",
    (1, 0, 0): "震",
    (0, 1, 1): "巽",
    (0, 1, 0): "坎",
    (0, 0, 1): "艮",
    (0, 0, 0): "坤",
}


@dataclass(frozen=True)
class HexagramState:
    lines_bottom_to_top: tuple[int, int, int, int, int, int]
    binary_id: int
    lower_trigram: str
    upper_trigram: str


def validate_lines(lines: Sequence[int]) -> tuple[int, ...]:
    if len(lines) not in (3, 6):
        raise ValueError("expected exactly 3 trigram lines or 6 hexagram lines")
    if any(isinstance(bit, bool) or not isinstance(bit, Integral) for bit in lines):
        raise ValueError("each line must be an integer encoded as 0 (yin) or 1 (yang)")
    normalized = tuple(int(bit) for bit in lines)
    if any(bit not in (0, 1) for bit in normalized):
        raise ValueError("each line must be encoded as 0 (yin) or 1 (yang)")
    return normalized


def trigram_name(lines_bottom_to_top: Sequence[int]) -> str:
    lines = validate_lines(lines_bottom_to_top)
    if len(lines) != 3:
        raise ValueError("trigram requires exactly 3 lines")
    return TRIGRAMS_BOTTOM_TO_TOP[lines]


def encode_hexagram(lines_bottom_to_top: Sequence[int]) -> HexagramState:
    lines = validate_lines(lines_bottom_to_top)
    if len(lines) != 6:
        raise ValueError("hexagram requires exactly 6 lines")
    binary_id = sum(bit << index for index, bit in enumerate(lines))
    lower = trigram_name(lines[:3])
    upper = trigram_name(lines[3:])
    return HexagramState(lines, binary_id, lower, upper)


def change_lines(
    lines_bottom_to_top: Sequence[int],
    changing_indices: Sequence[int],
) -> tuple[int, ...]:
    lines = list(validate_lines(lines_bottom_to_top))
    if len(lines) != 6:
        raise ValueError("line changes require a six-line hexagram")
    for index in changing_indices:
        if isinstance(index, bool) or not isinstance(index, Integral):
            raise ValueError("line index must be an integer in [0, 5]")
        if not 0 <= index < 6:
            raise ValueError("line index must be in [0, 5], bottom line is index 0")
        lines[index] = 1 - lines[index]
    return tuple(lines)


def all_hexagram_states() -> list[HexagramState]:
    return [
        encode_hexagram(tuple((value >> bit) & 1 for bit in range(6)))
        for value in range(64)
    ]
