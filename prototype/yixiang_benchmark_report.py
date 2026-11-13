"""Command-line report runner for the M8 yixiang benchmark."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from prototype.yixiang_benchmark import evaluate_predictions, group_leakage

def build_report(cases, predictions, *, allow_fixture_expected=False):
    scores=evaluate_predictions(cases,predictions,allow_fixture_expected=allow_fixture_expected)
    return {
        "benchmark":"zhouyi-ai-m8-yixiang-validity-v0.1",
        "scores":scores,
        "leakage":{
            "source_lineage":group_leakage(cases,group_field="source_lineage"),
            "independence_group":group_leakage(cases,group_field="independence_group")
        }
    }

def main(argv=None):
    parser=argparse.ArgumentParser(description="Evaluate M8 yixiang benchmark predictions.")
    parser.add_argument("--cases",required=True,help="UTF-8 JSON file containing benchmark cases")
    parser.add_argument("--predictions",required=True,help="UTF-8 JSON file containing model predictions")
    parser.add_argument("--allow-fixture-expected",action="store_true",
                        help="allow synthetic expected labels for contract tests; never human gold")
    args=parser.parse_args(argv)
    try:
        cases=json.loads(Path(args.cases).read_text(encoding="utf-8"))
        predictions=json.loads(Path(args.predictions).read_text(encoding="utf-8"))
        if not isinstance(cases,list) or not isinstance(predictions,list):
            raise ValueError("cases and predictions files must each contain a JSON array")
        report=build_report(cases,predictions,allow_fixture_expected=args.allow_fixture_expected)
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"M8 benchmark error: {exc}",file=sys.stderr)
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
