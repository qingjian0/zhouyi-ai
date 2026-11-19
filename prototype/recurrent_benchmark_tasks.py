"""Deterministic synthetic episodes for controlled recurrent-model comparisons.

Each example is a binary context followed by one supervised next-symbol target.
The generators intentionally separate task construction from model code so the
same examples can be evaluated by multiple recurrent architectures.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Sequence


@dataclass(frozen=True)
class SequenceExample:
    context: tuple[int, ...]
    target: int
    task: str
    metadata: tuple[tuple[str, int], ...] = ()

    def training_sequence(self) -> list[int]:
        return [*self.context, self.target]


def _bits(rng: random.Random, count: int) -> list[int]:
    if count < 1:
        raise ValueError("bit count must be positive")
    return [rng.randrange(2) for _ in range(count)]


def periodic_next_symbol(
    *, count: int, period: int = 7, seed: int = 1
) -> list[SequenceExample]:
    """Predict the next bit of a fixed periodic binary pattern."""
    if count < 1 or period < 2:
        raise ValueError("count must be positive and period at least two")
    rng = random.Random(seed)
    pattern = _bits(rng, period)
    if len(set(pattern)) == 1:
        pattern[-1] ^= 1
    return [
        SequenceExample(
            tuple(pattern[(i - 5) % period] for i in range(6)),
            pattern[i % period],
            "periodic",
            (("phase", i % period), ("period", period)),
        )
        for i in range(count)
    ]


def delayed_copy(
    *, count: int, payload_length: int = 5, distractor_length: int = 12,
    seed: int = 2,
) -> list[SequenceExample]:
    """Recall the first payload bit after a variable-length distractor gap.

    The context is a random payload, a fixed binary delimiter, random gap
    symbols, and a query delimiter. The task target is payload[0].
    """
    if count < 1 or payload_length < 1 or distractor_length < 1:
        raise ValueError("count, payload_length and distractor_length must be positive")
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        payload = _bits(rng, payload_length)
        gap = _bits(rng, distractor_length)
        context = [1, 1, 0, *payload, 1, 0, 1, *gap, 0, 1, 1]
        rows.append(SequenceExample(tuple(context), payload[0], "delayed_copy",
                                    (("payload_length", payload_length),
                                     ("distractor_length", distractor_length))))
    return rows


def associative_recall(
    *, count: int, pair_count: int = 4, key_bits: int = 3, seed: int = 3
) -> list[SequenceExample]:
    """Retrieve a value bit for a queried binary key from stored key/value pairs."""
    if count < 1 or pair_count < 2 or key_bits < 1:
        raise ValueError("invalid associative-recall dimensions")
    rng = random.Random(seed)
    key_space = 1 << key_bits
    if pair_count > key_space:
        raise ValueError("pair_count exceeds the unique key space")
    rows = []
    for _ in range(count):
        keys = rng.sample(range(key_space), pair_count)
        values = [rng.randrange(2) for _ in keys]
        query_index = rng.randrange(pair_count)
        encoded: list[int] = [1, 1, 1, 0]
        for key, value in zip(keys, values):
            encoded.extend((key >> shift) & 1 for shift in reversed(range(key_bits)))
            encoded.extend((1, value, 0))
        query = keys[query_index]
        encoded.extend((0, 0, 1))
        encoded.extend((query >> shift) & 1 for shift in reversed(range(key_bits)))
        rows.append(SequenceExample(tuple(encoded), values[query_index],
                                    "associative_recall",
                                    (("pair_count", pair_count), ("key_bits", key_bits))))
    return rows


def distractor_recall(
    *, count: int, payload_length: int = 5, distractor_length: int = 24,
    seed: int = 4,
) -> list[SequenceExample]:
    """Recall a marked payload bit after distractors containing decoy markers."""
    if count < 1 or payload_length < 1 or distractor_length < 1:
        raise ValueError("invalid distractor-recall dimensions")
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        payload = _bits(rng, payload_length)
        distractors = _bits(rng, distractor_length)
        # Insert repeated near-delimiters so a model cannot rely on one marker.
        noisy_gap = []
        for i, bit in enumerate(distractors):
            noisy_gap.append(bit)
            if i % 5 == 4:
                noisy_gap.extend((1, 0))
        context = [1, 1, 0, *payload, 1, 0, 1, *noisy_gap, 0, 1, 1]
        rows.append(SequenceExample(tuple(context), payload[0], "distractor_recall",
                                    (("payload_length", payload_length),
                                     ("distractor_length", distractor_length))))
    return rows


def distribution_shift(
    *, count: int, train_period: int = 5, eval_period: int = 11, seed: int = 5
) -> tuple[list[SequenceExample], list[SequenceExample]]:
    """Return train/evaluation episodes from distinct periodic regimes."""
    return (
        periodic_next_symbol(count=count, period=train_period, seed=seed),
        periodic_next_symbol(count=count, period=eval_period, seed=seed + 1),
    )


def validate_examples(examples: Iterable[SequenceExample]) -> int:
    total = 0
    for example in examples:
        if not example.context or any(x not in (0, 1) for x in example.context):
            raise ValueError("contexts must be non-empty binary sequences")
        if example.target not in (0, 1):
            raise ValueError("targets must be binary")
        total += len(example.context) + 1
    return total
