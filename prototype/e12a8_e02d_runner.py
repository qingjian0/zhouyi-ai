"""E12-A8 process-separated evaluation runner for the E02-D benchmark."""
from __future__ import annotations
import argparse, json
from typing import Any
from prototype.e02_rule_ood import make_episodes, target_c
from prototype.e12a8_evaluator_firewall import Evaluator, run_learner_process

def run_episode(episode: Any, index: int) -> dict[str, Any]:
    # The learner process receives only support and query.
    commit = run_learner_process(f"e02d-{index}", episode.support, episode.query)
    # Generator rule and gold label stay in this coordinator/evaluator path.
    a, b = episode.query
    hidden_gold = target_c(episode.rule, a, b)
    verdict = Evaluator({f"e02d-{index}": hidden_gold}).evaluate(commit)
    return {
        "episode_id": index,
        "prediction": commit.prediction,
        "prediction_identifiable": commit.identifiable,
        "consistent_hypotheses": commit.consistent_hypotheses,
        "commit_digest": commit.commit_digest,
        "gold": verdict.gold_label,
        "scored": verdict.scored,
        "correct": verdict.correct,
    }

def run(seed: int = 17, support_size: int = 6) -> dict[str, Any]:
    episodes = make_episodes(seed=seed, support_size=support_size)
    rows = [run_episode(ep, i) for i, ep in enumerate(episodes)]
    scored = [row for row in rows if row["scored"]]
    return {
        "task": "E12A8_process_separated_E02D",
        "seed": seed, "support_size": support_size, "episodes": len(rows),
        "prediction_coverage": len(scored) / len(rows),
        "accuracy_when_scored": (sum(row["correct"] for row in scored) / len(scored)
                                 if scored else None),
        "correct_all_episodes": sum(row["correct"] is True for row in rows),
        "abstention_count": len(rows) - len(scored),
        "episodes_detail": rows,
        "limitations": [
            "The learner is an exact symbolic enumerator over a declared 27-rule class.",
            "The coordinator still computes the hidden label; only the learner subprocess is label-blind.",
            "The subprocess is not an OS sandbox or hostile-code isolation boundary.",
        ],
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--support-size", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seed, args.support_size)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)

if __name__ == "__main__":
    main()
