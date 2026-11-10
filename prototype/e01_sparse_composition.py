"""E01: sparse, non-adjacent set composition baseline.

This is a transparent algorithmic baseline, not a trained neural model.
It selects candidate members by a supplied relevance score and supports
non-contiguous selections such as a,b,c,e from a,b,c,d,e.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Candidate:
    item: str
    score: float


def select_sparse(
    candidates: Sequence[Candidate],
    k: int,
    threshold: float = float("-inf"),
) -> list[str]:
    """Return at most k items, ordered by score then original input order."""
    if k < 0:
        raise ValueError("k must be non-negative")
    indexed = list(enumerate(candidates))
    eligible = [(i, c) for i, c in indexed if c.score >= threshold]
    eligible.sort(key=lambda pair: (-pair[1].score, pair[0]))
    chosen = eligible[:k]
    chosen.sort(key=lambda pair: pair[0])
    return [candidate.item for _, candidate in chosen]


def exact_match(predicted: Iterable[str], target: Iterable[str]) -> bool:
    return set(predicted) == set(target)


def demo() -> dict:
    items = [
        Candidate("a", 0.96),
        Candidate("b", 0.91),
        Candidate("c", 0.87),
        Candidate("d", 0.12),
        Candidate("e", 0.83),
    ]
    selected = select_sparse(items, k=4, threshold=0.5)
    return {
        "input": [c.item for c in items],
        "scores": {c.item: c.score for c in items},
        "selected": selected,
        "demonstrates_non_adjacent_selection": selected == ["a", "b", "c", "e"],
        "note": "Toy deterministic example; not an experimental performance result.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()
    result = demo()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
