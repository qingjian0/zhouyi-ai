"""Subprocess learner endpoint. It must never receive evaluator labels."""
from __future__ import annotations
import json, sys
from prototype.e02_rule_ood import consistent_rules, target_c
from prototype.e12a8_evaluator_firewall import _digest

def solve(public: dict) -> dict:
    support = tuple(sorted(tuple(int(v) for v in row) for row in public["support"]))
    query = tuple(int(v) for v in public["query"])
    if len(query) != 2 or any(v not in (0, 1, 2) for v in query):
        raise ValueError("query must contain two Z3 values")
    if any(len(row) != 3 or any(v not in (0, 1, 2) for v in row) for row in support):
        raise ValueError("support rows must be Z3 triples")
    hypotheses = tuple(sorted(consistent_rules(support)))
    predictions = sorted({target_c(rule, *query) for rule in hypotheses})
    identifiable = len(predictions) == 1
    body = {
        "episode_id": str(public["episode_id"]), "query": query,
        "prediction": predictions[0] if identifiable else None,
        "identifiable": identifiable, "consistent_hypotheses": len(hypotheses),
        "candidate_trace": hypotheses,
        "public_input_digest": _digest({"episode_id": str(public["episode_id"]),
            "support": [list(row) for row in support], "query": list(query)}),
    }
    return {**body, "commit_digest": _digest(body)}

def main() -> None:
    public = json.loads(sys.stdin.read())
    sys.stdout.write(json.dumps(solve(public), sort_keys=True, separators=(",", ":")))

if __name__ == "__main__":
    main()
