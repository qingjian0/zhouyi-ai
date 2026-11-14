"""Run the M56 synthetic protocol slice and write separated artifacts."""
import argparse
import json
import os

from prototype.yixiang_m56_executable_core import (
    audit_dataset, generate_dataset, write_dataset,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=240)
    parser.add_argument("--seed", type=int, default=5601)
    parser.add_argument("--nuisance-mode", choices=("independent", "train_spurious"),
                        default="independent")
    parser.add_argument("--output-dir", default="artifacts/m56")
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    cases, truth = generate_dataset(
        count=args.count, seed=args.seed, nuisance_mode=args.nuisance_mode
    )
    audit = audit_dataset(cases, truth)
    paths = write_dataset(cases, truth, os.path.join(args.output_dir, "m56"))
    report = {
        "protocol": "M56-executable-core-v0.1",
        "generator": {
            "count": args.count, "seed": args.seed,
            "nuisance_mode": args.nuisance_mode,
        },
        "audit": audit,
        "outputs": paths,
        "limitations": [
            "Synthetic controlled data only; no classical-text human annotation is included.",
            "Feature selection is a transparent task-rule control, not a learned yixiang model.",
            "Category, relation, and revision functions are minimal executable contracts.",
            "No Transformer, SCM learner, or production Zhouyi-AI agent comparison is included.",
        ],
    }
    with open(os.path.join(args.output_dir, "m56_audit.json"), "w",
              encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
