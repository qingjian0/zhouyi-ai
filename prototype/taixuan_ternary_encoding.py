"""Minimal reversible Taixuan-inspired ternary index encoding.

This is a computational indexing convention, not a claim about the
historical semantic meaning of the Taixuan symbols.
"""
from itertools import product

TRIT_BASE = 3
HEAD_TRITS = 4
PRAISE_TRITS = 2
HEAD_COUNT = TRIT_BASE ** HEAD_TRITS
PRAISE_COUNT = TRIT_BASE ** PRAISE_TRITS
STATE_COUNT = HEAD_COUNT * PRAISE_COUNT


def _check(values, length):
    values = tuple(values)
    if len(values) != length:
        raise ValueError(f"expected {length} trits, got {len(values)}")
    if any(type(v) is not int or v not in (0, 1, 2) for v in values):
        raise ValueError("trits must be integers in {0, 1, 2}")
    return values


def encode_trits(values):
    values = _check(values, HEAD_TRITS + PRAISE_TRITS)
    result = 0
    for value in values:
        result = result * TRIT_BASE + value
    return result


def decode_index(index):
    if type(index) is not int or not 0 <= index < STATE_COUNT:
        raise ValueError(f"index must be in [0, {STATE_COUNT})")
    digits = [0] * (HEAD_TRITS + PRAISE_TRITS)
    for pos in range(len(digits) - 1, -1, -1):
        digits[pos] = index % TRIT_BASE
        index //= TRIT_BASE
    return tuple(digits)


def encode_head_praise(head, praise):
    return encode_trits(_check(head, HEAD_TRITS) + _check(praise, PRAISE_TRITS))


def decode_head_praise(index):
    values = decode_index(index)
    return values[:HEAD_TRITS], values[HEAD_TRITS:]


def iter_all_indices():
    for values in product(range(TRIT_BASE), repeat=HEAD_TRITS + PRAISE_TRITS):
        yield encode_trits(values)


if __name__ == "__main__":
    indices = tuple(iter_all_indices())
    assert len(indices) == STATE_COUNT
    assert len(set(indices)) == STATE_COUNT
    assert all(decode_index(i) == decode_index(encode_trits(decode_index(i)))
               for i in range(STATE_COUNT))
    print({"heads": HEAD_COUNT, "praises_per_head": PRAISE_COUNT,
           "combined_states": STATE_COUNT, "round_trip": True})
