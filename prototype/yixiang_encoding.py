"""Explicit, convention-safe binary encoding for trigram/hexagram states.

Bit convention: 1 = yang, 0 = yin; line arrays are bottom-to-top.
The 6-bit identifier is a computational index, NOT King Wen sequence order.
No semantic prediction is implied by an encoded state.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    if any(type(bit) is not int or bit not in (0, 1) for bit in lines):
        raise ValueError("each line must be the integer 0 (yin) or 1 (yang)")
    return tuple(lines)


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
    if any(type(index) is not int for index in changing_indices):
        raise ValueError("changing line indices must be integers")
    if len(set(changing_indices)) != len(changing_indices):
        raise ValueError("changing line indices must be unique")
    for index in changing_indices:
        if not 0 <= index < 6:
            raise ValueError("line index must be in [0, 5], bottom line is index 0")
        lines[index] = 1 - lines[index]
    return tuple(lines)


def all_hexagram_states() -> list[HexagramState]:
    return [
        encode_hexagram(tuple((value >> bit) & 1 for bit in range(6)))
        for value in range(64)
    ]


@dataclass(frozen=True)
class HexagramTransition:
    """A purely structural line-change transition; no divinatory meaning inferred."""
    before: HexagramState
    after: HexagramState
    changing_indices_bottom_to_top: tuple[int, ...]


def transition_hexagram(
    lines_bottom_to_top: Sequence[int],
    changing_indices: Sequence[int],
) -> HexagramTransition:
    """Apply distinct moving-line indices and retain both six-line states.

    Indices are zero-based from the bottom. The returned binary identifiers
    are computational indices only; no King Wen or other sequence is implied.
    """
    before = encode_hexagram(lines_bottom_to_top)
    indices = tuple(changing_indices)
    after_lines = change_lines(before.lines_bottom_to_top, indices)
    after = encode_hexagram(after_lines)
    return HexagramTransition(
        before=before,
        after=after,
        changing_indices_bottom_to_top=indices,
    )
