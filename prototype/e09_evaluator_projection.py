"""Evaluator-only metrics projected from the durable E09 event ledger.

This module intentionally has no learner or revision API. It is still a
trusted-process projection over the same SQLite store, not a security boundary.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from prototype.shared_evidence_protocol import SQLiteEvidenceStore


class E09EvaluatorProjection:
    """Compute split-aware metrics without exposing labels to learner APIs."""

    def __init__(self, store: SQLiteEvidenceStore, episode_id: str) -> None:
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ValueError("episode_id must be a non-empty string")
        self._store = store
        self._episode_id = episode_id

    def score(self) -> dict[str, Any]:
        events = self._store.replay_episode(self._episode_id)
        commits: dict[tuple[str, str], dict[str, Any]] = {}
        reveals: dict[tuple[str, str], dict[str, Any]] = {}
        for event in events:
            payload = event["payload"]
            if event["event_type"] == "prediction_commit":
                key = (payload["learner_track"], payload["prediction_id"])
                if key in commits:
                    raise ValueError("duplicate prediction commit in evaluator projection")
                commits[key] = payload
            elif event["event_type"] == "evidence_reveal":
                key = (payload["learner_track"], payload["prediction_id"])
                if key in reveals:
                    raise ValueError("duplicate evidence reveal in evaluator projection")
                reveals[key] = payload

        unknown = set(reveals) - set(commits)
        if unknown:
            raise ValueError("evidence reveal has no matching prediction commit")

        by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for key, commit in commits.items():
            reveal = reveals.get(key)
            if reveal is not None:
                for field in ("query_id", "scope", "split"):
                    if reveal.get(field) != commit.get(field):
                        raise ValueError(f"evaluator projection {field} mismatch")
            by_split[commit["split"]].append({
                "commit": commit,
                "reveal": reveal,
            })

        def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
            total = len(rows)
            revealed = [row for row in rows if row["reveal"] is not None]
            predicted = [
                row for row in revealed
                if row["commit"].get("decision_status") == "PREDICT"
                and row["commit"].get("prediction") is not None
            ]
            correct = sum(
                row["commit"]["prediction"] == row["reveal"]["target_or_feedback"]
                for row in predicted
            )
            abstentions = sum(
                row["commit"].get("decision_status") != "PREDICT"
                or row["commit"].get("prediction") is None
                for row in rows
            )
            return {
                "prediction_commits": total,
                "revealed_observations": len(revealed),
                "unrevealed_observations": total - len(revealed),
                "abstentions": abstentions,
                "coverage": (total - abstentions) / total if total else None,
                "scored_predictions": len(predicted),
                "correct_predictions": correct,
                "selective_accuracy": correct / len(predicted) if predicted else None,
            }

        return {
            "episode_id": self._episode_id,
            "by_split": {
                split: summarize(rows)
                for split, rows in sorted(by_split.items())
            },
            "overall": summarize([row for rows in by_split.values() for row in rows]),
        }
