"""Reproducible microbenchmark for cached Boolean feature encoding."""
from __future__ import annotations

import argparse
import copy
import json
import platform
import time
import tracemalloc
from pathlib import Path

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, encode_relations,
)
from prototype.cpg_ei_early_stopping import _train_preencoded_one_epoch
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def run_benchmark(*, families: int = 8, input_dim: int = 8,
                  output_dim: int = 8, seed: int = 20261114,
                  epochs: int = 100) -> dict:
    corpus = generate_mixed_corpus(
        family_count=families, input_dim=input_dim,
        output_dim=output_dim, seed=seed,
    )
    family_id = sorted({row["family_id"] for row in corpus["rows"]})[0]
    rows = [
        row for row in corpus["rows"]
        if row["family_id"] == family_id and row["state_split"] == "train"
    ]
    examples = [
        TransitionExample(tuple(row["state"]), tuple(row["target"]))
        for row in rows
    ]
    reference = RelationalTransitionModel.create(
        input_dim, output_dim, 1, input_dim
    )
    cached = copy.deepcopy(reference)

    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(epochs):
        reference.train(examples, epochs=1, learning_rate=0.1, l2=1e-4)
    reference_seconds = time.perf_counter() - started
    _, reference_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()

    encoded = [
        (encode_relations(row.state, cached.supports), row.target)
        for row in examples
    ]
    feature_encodings_cached = len(encoded) * (len(cached.supports) + 1)
    started = time.perf_counter()
    for _ in range(epochs):
        _train_preencoded_one_epoch(
            cached, encoded, learning_rate=0.1, l2=1e-4
        )
    cached_seconds = time.perf_counter() - started
    _, cached_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "benchmark_id": "zhouyi-cpg-ei-preencoded-feature-cache-v1",
        "corpus_sha256": corpus["manifest"]["corpus_sha256"],
        "seed": seed,
        "family_id": family_id,
        "input_dim": input_dim,
        "output_dim": output_dim,
        "training_rows": len(examples),
        "epochs": epochs,
        "feature_columns_including_bias": len(reference.supports) + 1,
        "reference_feature_encodings": epochs * feature_encodings_cached,
        "cached_feature_encodings": feature_encodings_cached,
        "reference_wall_seconds": reference_seconds,
        "cached_wall_seconds": cached_seconds,
        "speedup": reference_seconds / cached_seconds if cached_seconds else None,
        "reference_peak_traced_bytes": reference_peak,
        "cached_peak_traced_bytes": cached_peak,
        "weights_identical": reference.weights == cached.weights,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_benchmark(
        families=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed, epochs=args.epochs,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
