"""Reproducible task-level comparison for the P5-B binary recurrent baselines.

This runner deliberately reports synthetic-mechanism results only. It does not
claim language-model quality, million-token context, or mobile feasibility.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import tracemalloc
from dataclasses import asdict, dataclass
from typing import Callable

from prototype.diagonal_gated_rnn import DiagonalGatedRNN
from prototype.diagonal_linear_rnn import DiagonalLinearRNN
from prototype.selective_diagonal_ssm import SelectiveDiagonalSSM
from prototype.recurrent_benchmark_tasks import (
    SequenceExample,
    associative_recall,
    delayed_copy,
    distractor_recall,
    periodic_next_symbol,
)


@dataclass(frozen=True)
class BenchmarkConfig:
    task: str = "delayed_copy"
    train_examples: int = 128
    eval_examples: int = 128
    epochs: int = 5
    seed: int = 101
    payload_length: int = 5
    gap_length: int = 16
    pair_count: int = 4
    key_bits: int = 3
    learning_rate: float = 0.03
    eval_gap_length: int | None = None


def _dataset(
    task: str, count: int, seed: int, config: BenchmarkConfig, *,
    gap_length: int | None = None,
):
    effective_gap = config.gap_length if gap_length is None else gap_length
    if task == "periodic":
        return periodic_next_symbol(count=count, period=7, seed=seed)
    if task == "delayed_copy":
        return delayed_copy(count=count, payload_length=config.payload_length,
                            distractor_length=effective_gap, seed=seed)
    if task == "associative_recall":
        return associative_recall(count=count, pair_count=config.pair_count,
                                  key_bits=config.key_bits, seed=seed)
    if task == "distractor_recall":
        return distractor_recall(count=count, payload_length=config.payload_length,
                                 distractor_length=effective_gap, seed=seed)
    raise ValueError(f"unsupported task: {task}")


def _parameter_count(model) -> int:
    if isinstance(model, DiagonalGatedRNN):
        return 7 * model.hidden_size + 1
    if isinstance(model, DiagonalLinearRNN):
        return 4 * model.hidden_size + 1
    if isinstance(model, SelectiveDiagonalSSM):
        return model.parameter_count
    raise TypeError(f"unsupported model type: {type(model).__name__}")


def _score(model, examples: list[SequenceExample]):
    loss = 0.0
    correct = 0
    started = time.perf_counter()
    total_symbols = 0
    for example in examples:
        probabilities, _ = model.predict_chunk(example.context)
        probability = min(max(probabilities[-1], 1e-12), 1.0 - 1e-12)
        loss -= example.target * math.log(probability)
        loss -= (1 - example.target) * math.log(1 - probability)
        correct += int((probability >= 0.5) == bool(example.target))
        total_symbols += len(example.context)
    elapsed = max(time.perf_counter() - started, 1e-12)
    return {
        "binary_cross_entropy": loss / len(examples),
        "accuracy": correct / len(examples),
        "examples_per_second": len(examples) / elapsed,
        "context_symbols_per_second": total_symbols / elapsed,
        "evaluation_examples": len(examples),
        "evaluation_context_symbols": total_symbols,
        "evaluation_seconds": elapsed,
    }


def _chunk_state_parity(model, example: SequenceExample, chunk_size: int = 7):
    whole, whole_state = model.predict_chunk(example.context)
    state = None
    chunked = []
    for offset in range(0, len(example.context), chunk_size):
        part, state = model.predict_chunk(example.context[offset:offset + chunk_size], state)
        chunked.extend(part)
    if len(whole) != len(chunked):
        return False
    max_delta = max((abs(a - b) for a, b in zip(whole, chunked)), default=0.0)
    state_delta = max(
        (abs(a - b) for a, b in zip(whole_state.hidden, state.hidden)), default=0.0
    )
    return max(max_delta, state_delta) <= 1e-12


def _run_one(model_name: str, config: BenchmarkConfig, train, evaluation, seed: int):
    if model_name == "gated_rnn":
        model = DiagonalGatedRNN(hidden_size=4, seed=seed)
    elif model_name == "linear_rnn":
        model = DiagonalLinearRNN(hidden_size=7, seed=seed)
    elif model_name == "selective_diagonal_ssm":
        model = SelectiveDiagonalSSM(hidden_size=7, seed=seed)
    else:
        raise ValueError(f"unsupported model: {model_name}")

    tracemalloc.start()
    started = time.perf_counter()
    train_losses = []
    for _ in range(config.epochs):
        for example in train:
            train_losses.append(model.train_final_target(
                example.context, example.target, learning_rate=config.learning_rate
            ))
    train_seconds = max(time.perf_counter() - started, 1e-12)
    train_context_symbols = sum(len(example.context) for example in train)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    score = _score(model, evaluation)
    parity = all(_chunk_state_parity(model, row) for row in evaluation[:min(16, len(evaluation))])
    return {
        "model": model_name,
        "parameter_count": _parameter_count(model),
        "seed": seed,
        "train_examples": len(train),
        "train_context_symbols": train_context_symbols,
        "epochs": config.epochs,
        "train_updates": len(train) * config.epochs,
        "train_mean_sequence_loss": sum(train_losses) / max(len(train_losses), 1),
        "train_seconds": train_seconds,
        "train_examples_per_second": len(train) * config.epochs / train_seconds,
        "peak_traced_python_bytes": peak_bytes,
        "chunk_state_parity": parity,
        **score,
    }


def run_benchmark(config: BenchmarkConfig, seeds: tuple[int, ...] | None = None):
    if config.train_examples < 1 or config.eval_examples < 1 or config.epochs < 1:
        raise ValueError("example counts and epochs must be positive")
    if config.gap_length < 1 or (
        config.eval_gap_length is not None and config.eval_gap_length < 1
    ):
        raise ValueError("training and evaluation gap lengths must be positive")
    seeds = seeds or (config.seed, config.seed + 1, config.seed + 2)
    results = []
    for seed in seeds:
        train = _dataset(config.task, config.train_examples, seed * 17 + 1, config)
        evaluation = _dataset(
            config.task, config.eval_examples, seed * 17 + 2, config,
            gap_length=config.eval_gap_length,
        )
        for model_name in ("gated_rnn", "linear_rnn", "selective_diagonal_ssm"):
            results.append(_run_one(model_name, config, train, evaluation, seed))
    return {
        "schema_version": 1,
        "scope": "synthetic_binary_recurrent_mechanism_benchmark",
        "claim_boundary": (
            "Not a language model, not a million-token test, and not a mobile "
            "feasibility result."
        ),
        "config": asdict(config),
        "seeds": list(seeds),
        "results": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("periodic", "delayed_copy",
                        "associative_recall", "distractor_recall"), default="delayed_copy")
    parser.add_argument("--train-examples", type=int, default=128)
    parser.add_argument("--eval-examples", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--payload-length", type=int, default=5)
    parser.add_argument("--gap-length", type=int, default=16,
                        help="training distractor gap length")
    parser.add_argument("--eval-gap-length", type=int, default=None,
                        help="held-out evaluation gap length; defaults to --gap-length")
    parser.add_argument("--pair-count", type=int, default=4)
    parser.add_argument("--key-bits", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    config = BenchmarkConfig(
        task=args.task, train_examples=args.train_examples,
        eval_examples=args.eval_examples, epochs=args.epochs, seed=args.seed,
        payload_length=args.payload_length, gap_length=args.gap_length,
        eval_gap_length=args.eval_gap_length,
        pair_count=args.pair_count, key_bits=args.key_bits,
        learning_rate=args.learning_rate,
    )
    report = run_benchmark(config)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output == "-":
        print(rendered)
    else:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")


if __name__ == "__main__":
    main()
