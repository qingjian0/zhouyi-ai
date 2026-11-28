"""Generate text from a ZhouyiAI Omega checkpoint and its saved vocabulary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from prototype.omega_model import generate, load_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint")
    parser.add_argument("prompt")
    parser.add_argument("--vocab", default=None, help="defaults to CHECKPOINT.vocab.json")
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint)
    vocab_path = Path(args.vocab) if args.vocab else checkpoint.with_suffix(checkpoint.suffix + ".vocab.json")
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    lookup = {char: index for index, char in enumerate(vocab)}
    unknown = sorted(set(args.prompt) - set(lookup))
    if unknown:
        raise SystemExit(f"Prompt contains characters absent from vocabulary: {unknown[:12]}")
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = load_checkpoint(str(checkpoint), map_location=str(device)).to(device)
    prompt_ids = torch.tensor([[lookup[char] for char in args.prompt]], dtype=torch.long, device=device)
    output = generate(
        model, prompt_ids, max_new_tokens=args.max_new_tokens,
        temperature=args.temperature, top_k=args.top_k,
    )
    print("".join(vocab[index] for index in output[0].tolist()))


if __name__ == "__main__":
    main()
