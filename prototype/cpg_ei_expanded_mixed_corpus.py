"""Fourfold family-scale expansion of the mixed Boolean relation corpus.

The v2 corpus reuses the v1 typed rule semantics and deterministic generator,
increasing independent teacher families from 400 to 1,600 at 8x8x256 states.
It is a synthetic benchmark artifact, not evidence of natural-language reasoning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus, write_jsonl


BASE_FAMILY_COUNT = 400
EXPANDED_FAMILY_COUNT = 1600
BASE_DATASET_ID = "zhouyi-cpg-ei-mixed-operators-v1"
DATASET_ID = "zhouyi-cpg-ei-expanded-mixed-operators-v2"


def _canonical_digest(corpus: dict[str, Any]) -> str:
    payload = json.dumps(
        {"manifest": corpus["manifest"], "teachers": corpus["teachers"],
         "rows": corpus["rows"]},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_expanded_corpus(*, family_count: int = EXPANDED_FAMILY_COUNT,
                             input_dim: int = 8, output_dim: int = 8,
                             seed: int = 20261114) -> dict[str, Any]:
    if (isinstance(family_count, bool) or not isinstance(family_count, int)
            or family_count < BASE_FAMILY_COUNT):
        raise ValueError(f"family_count must be an integer >= {BASE_FAMILY_COUNT}")
    corpus = generate_mixed_corpus(
        family_count=family_count, input_dim=input_dim,
        output_dim=output_dim, seed=seed,
    )
    manifest = corpus["manifest"]
    manifest.update({
        "dataset_id": DATASET_ID,
        "generator_version": "2.0.0",
        "parent_dataset_id": BASE_DATASET_ID,
        "parent_reference_family_count": BASE_FAMILY_COUNT,
        "expansion_factor_vs_reference": family_count / BASE_FAMILY_COUNT,
        "expansion_axis": "independent_teacher_families",
        "claim_boundary": (
            "Fourfold-or-greater expansion of a deterministic synthetic mixed "
            "Boolean-operator corpus. Family diversity increases; state coverage "
            "per family remains exhaustive over the configured Boolean dimension. "
            "This does not establish natural-language reasoning, causal discovery, "
            "or cross-family zero-shot learning."
        ),
    })
    manifest["corpus_sha256"] = _canonical_digest(corpus)
    return corpus


def write_manifest(corpus: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(corpus["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=EXPANDED_FAMILY_COUNT)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    corpus = generate_expanded_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    write_jsonl(corpus, args.jsonl)
    write_manifest(corpus, args.manifest)
    print(json.dumps(corpus["manifest"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
