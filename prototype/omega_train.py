"""Minimal corpus trainer for the ZhouyiAI Omega research MVP.

Example:
  python -m prototype.omega_train corpus.txt --steps 500 --seq-len 128 \
      --checkpoint artifacts/omega.pt --report artifacts/omega-report.json

The tokenizer is deliberately a transparent character tokenizer for smoke tests.
It is not a production multilingual tokenizer. No pretrained weights are loaded.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import torch

from prototype.omega_model import (
    OmegaConfig, OmegaModel, causal_language_loss,
    classiang_composition_consistency_loss, save_checkpoint,
)


def encode_corpus(text: str) -> tuple[list[str], list[int]]:
    vocab = sorted(set(text))
    if len(vocab) < 2:
        raise ValueError("corpus must contain at least two distinct characters")
    lookup = {char: index for index, char in enumerate(vocab)}
    return vocab, [lookup[char] for char in text]


def sample_batch(tokens: torch.Tensor, batch_size: int, seq_len: int,
                 device: torch.device) -> torch.Tensor:
    max_start = tokens.numel() - seq_len - 1
    if max_start < 1:
        raise ValueError("each data split must contain more than seq_len + 1 tokens")
    starts = torch.randint(0, max_start + 1, (batch_size,))
    batch = torch.stack([tokens[start:start + seq_len] for start in starts.tolist()])
    return batch.to(device)


def train(args: argparse.Namespace) -> dict:
    if args.steps < 1 or args.batch_size < 1 or args.eval_batches < 1:
        raise ValueError("steps, batch_size and eval_batches must be >= 1")
    if not 0.0 < args.validation_fraction < 0.5:
        raise ValueError("validation_fraction must be between 0 and 0.5")
    if args.learning_rate <= 0 or args.dropout < 0 or args.dropout >= 1:
        raise ValueError("learning_rate must be positive and dropout must be in [0, 1)")
    if args.composition_loss_weight < 0:
        raise ValueError("composition_loss_weight must be >= 0")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    text = Path(args.corpus).read_text(encoding="utf-8")
    vocab, encoded = encode_corpus(text)
    split = int(len(encoded) * (1.0 - args.validation_fraction))
    if split <= args.seq_len + 1 or len(encoded) - split <= args.seq_len + 1:
        raise ValueError("corpus is too short for the requested sequence length/split")
    train_tokens = torch.tensor(encoded[:split], dtype=torch.long)
    valid_tokens = torch.tensor(encoded[split:], dtype=torch.long)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    config = OmegaConfig(
        vocab_size=len(vocab), d_model=args.d_model, n_heads=args.n_heads,
        n_layers=args.n_layers, num_classiang_slots=args.classiang_slots,
        max_seq_len=args.seq_len, dropout=args.dropout, branch_mode=args.branch_mode,
    )
    model = OmegaModel(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    initial_loss = None
    for step in range(1, args.steps + 1):
        model.train()
        batch = sample_batch(train_tokens, args.batch_size, args.seq_len, device)
        optimizer.zero_grad(set_to_none=True)
        outputs = model(batch)
        language_loss = causal_language_loss(outputs["logits"], batch)
        composition_loss = classiang_composition_consistency_loss(
            outputs["relation_logits"], outputs["composition_logits"]
        )
        loss = language_loss + args.composition_loss_weight * composition_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1:
            initial_loss = float(loss.detach().cpu())
    model.eval()
    with torch.no_grad():
        validation_losses = []
        for _ in range(args.eval_batches):
            batch = sample_batch(valid_tokens, args.batch_size, args.seq_len, device)
            validation_losses.append(float(causal_language_loss(model(batch)["logits"], batch).cpu()))
    validation_loss = sum(validation_losses) / len(validation_losses)
    checkpoint = Path(args.checkpoint)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    save_checkpoint(model, str(checkpoint))
    vocab_path = checkpoint.with_suffix(checkpoint.suffix + ".vocab.json")
    vocab_path.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "format": "zhouyi-ai-omega-training-report-v1",
        "model": "ZhouyiAI Omega",
        "parameters": model.parameter_count(),
        "device": str(device),
        "vocabulary_size": len(vocab),
        "corpus_characters": len(encoded),
        "train_characters": len(train_tokens),
        "validation_characters": len(valid_tokens),
        "steps": args.steps,
        "sequence_length": args.seq_len,
        "initial_step_loss": initial_loss,
        "composition_loss_weight": args.composition_loss_weight,
        "validation_loss": validation_loss,
        "validation_perplexity": math.exp(min(validation_loss, 20.0)),
        "checkpoint": str(checkpoint),
        "vocabulary": str(vocab_path),
        "limitations": [
            "character tokenizer is a smoke-test tokenizer, not production multilingual tokenization",
            "a small corpus smoke run does not establish general language ability",
            "classiang slots are learned latent aspects; their semantic grounding needs labeled evidence and evaluation",
            "the Transformer branch remains present in this hybrid prototype",
        ],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--n-heads", type=int, default=4)
    parser.add_argument("--n-layers", type=int, default=2)
    parser.add_argument("--classiang-slots", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.1)\n    parser.add_argument("--branch-mode", choices=["hybrid", "attention_only", "recurrent_only", "classiang_only"], default="hybrid")
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--composition-loss-weight", type=float, default=0.1)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--eval-batches", type=int, default=20)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default="artifacts/omega.pt")
    parser.add_argument("--report", default="artifacts/omega-report.json")
    return parser


if __name__ == "__main__":
    print(json.dumps(train(build_parser().parse_args()), ensure_ascii=False, indent=2))
