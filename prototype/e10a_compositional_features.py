"""Bounded induction of composite object features for E10-A.

A feature is a conjunction of observed categorical attributes on one object.
The learner proposes role signatures over those conjunctions from Support and
revealed Query evidence only. This is finite symbolic composition, not raw
perception or open-world feature invention.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any

from prototype.e10a_mechanism_learner import E10AMechanismLearner


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True, order=True)
class CompositeFeatureMechanism:
    relation_symbol: str
    feature_keys: tuple[str, ...]
    role_signatures: tuple[tuple[tuple[str, str], ...], ...]
    required_contexts: tuple[tuple[str, str], ...]

    def predict(self, row: dict[str, Any], objects: dict[str, dict[str, str]]) -> bool:
        if row.get("relation_symbol") != self.relation_symbol:
            return False
        ids = row.get("participants", [])
        if (not isinstance(ids, list) or len(ids) != len(self.role_signatures)
                or len(set(ids)) != len(ids)):
            return False
        observed = []
        for oid in ids:
            attrs = objects.get(oid)
            if attrs is None or any(key not in attrs for key in self.feature_keys):
                return False
            observed.append(tuple((key, attrs[key]) for key in self.feature_keys))
        if tuple(sorted(observed)) != self.role_signatures:
            return False
        context = dict(row.get("context", []))
        return all(context.get(k) == v for k, v in self.required_contexts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "relation_symbol": self.relation_symbol,
            "feature_keys": list(self.feature_keys),
            "role_signatures": [
                [[key, value] for key, value in signature]
                for signature in self.role_signatures
            ],
            "required_contexts": [list(pair) for pair in self.required_contexts],
        }


class CompositionalFeatureLearner:
    """Prequential learner that composes existing object attributes into features."""

    def __init__(
        self,
        support_payload: dict[str, Any],
        *,
        proposal_budget: int = 256,
        max_feature_terms: int = 3,
        max_context_terms: int = 4,
    ):
        for name, value, minimum in (
            ("proposal_budget", proposal_budget, 1),
            ("max_feature_terms", max_feature_terms, 1),
            ("max_context_terms", max_context_terms, 0),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        self._base = E10AMechanismLearner(support_payload)
        self._objects = self._base._objects
        self._evidence = list(self._base._evidence)
        self._seen_observation_ids = {
            item["row"]["observation_id"] for item in self._evidence
            if item["row"].get("observation_id") is not None
        }
        self._proposal_budget = proposal_budget
        self._max_feature_terms = max_feature_terms
        self._max_context_terms = max_context_terms
        self._candidates: set[CompositeFeatureMechanism] = set()
        self._version = 1
        self._last_proposal_count = 0
        self._budget_exceeded = False
        self._contrastive_relations: set[str] = set()
        self._propose_and_set_initial()

    def _propose_and_set_initial(self) -> None:
        candidates, attempted, exceeded = self._propose()
        if exceeded:
            raise ValueError("Support feature proposal budget exceeded")
        self._candidates = candidates
        self._last_proposal_count = attempted
        self._refresh_contrastive_state()

    def add_query_objects(self, rows: list[dict[str, Any]]) -> None:
        self._base.add_query_objects(rows)
        self._objects = self._base._objects

    def _refresh_contrastive_state(self) -> None:
        labels: dict[str, set[bool]] = {}
        for item in self._evidence:
            labels.setdefault(item["row"]["relation_symbol"], set()).add(item["target"])
        self._contrastive_relations = {
            relation for relation, values in labels.items() if values == {True, False}
        }

    def _propose(self) -> tuple[set[CompositeFeatureMechanism], int, bool]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self._evidence:
            grouped.setdefault(item["row"]["relation_symbol"], []).append(item)
        proposed: set[CompositeFeatureMechanism] = set()
        attempted = 0
        for relation, items in sorted(grouped.items()):
            positives = [item["row"] for item in items if item["target"] is True]
            negatives = [item["row"] for item in items if item["target"] is False]
            if not positives:
                continue
            arity = len(positives[0]["participants"])
            if arity < 2 or any(len(row["participants"]) != arity for row in positives):
                continue

            common_keys: set[str] | None = None
            for row in positives:
                for oid in row["participants"]:
                    keys = set(self._objects[oid])
                    common_keys = keys if common_keys is None else common_keys & keys
            if not common_keys:
                continue

            common_contexts: set[tuple[str, str]] | None = None
            for row in positives:
                pairs = {tuple(pair) for pair in row["context"]}
                common_contexts = pairs if common_contexts is None else common_contexts & pairs
            contexts = tuple(sorted(common_contexts or set()))
            if len(contexts) > self._max_context_terms:
                continue

            for width in range(1, min(self._max_feature_terms, len(common_keys)) + 1):
                for keys in itertools.combinations(sorted(common_keys), width):
                    attempted += 1
                    if attempted > self._proposal_budget:
                        return set(), attempted, True
                    positive_signatures = []
                    valid = True
                    for row in positives:
                        signatures = [
                            tuple((key, self._objects[oid][key]) for key in keys)
                            for oid in row["participants"]
                        ]
                        if len(set(signatures)) != arity:
                            valid = False
                            break
                        positive_signatures.append(tuple(sorted(signatures)))
                    if not valid or len(set(positive_signatures)) != 1:
                        continue
                    candidate = CompositeFeatureMechanism(
                        relation, tuple(keys), positive_signatures[0], contexts
                    )
                    if (all(candidate.predict(row, self._objects) for row in positives)
                            and all(not candidate.predict(row, self._objects) for row in negatives)):
                        proposed.add(candidate)
        return proposed, attempted, False

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def candidate_hash(self) -> str:
        return _hash([candidate.as_dict() for candidate in sorted(self._candidates)])

    @property
    def version_id(self) -> str:
        return f"e10a-composite-v{self._version}-{self.candidate_hash[:12]}"

    @property
    def status(self) -> str:
        if self._budget_exceeded:
            return "BUDGET_EXCEEDED"
        if not self._candidates:
            return "INCONSISTENT"
        relations = {candidate.relation_symbol for candidate in self._candidates}
        if any(relation not in self._contrastive_relations for relation in relations):
            return "PROVISIONAL"
        per_relation: dict[str, int] = {}
        for candidate in self._candidates:
            per_relation[candidate.relation_symbol] = per_relation.get(candidate.relation_symbol, 0) + 1
        return "IDENTIFIED" if all(count == 1 for count in per_relation.values()) else "AMBIGUOUS"

    def predict(self, row: dict[str, Any]) -> dict[str, Any]:
        self._base._validate_row(row)
        relevant = [c for c in self._candidates if c.relation_symbol == row["relation_symbol"]]
        if self._budget_exceeded:
            status, prediction = "ABSTAIN_BUDGET", None
        elif not relevant:
            status, prediction = "ABSTAIN_INCONSISTENT", None
        elif row["relation_symbol"] not in self._contrastive_relations:
            status, prediction = "ABSTAIN_AMBIGUOUS", None
        else:
            outputs = {c.predict(row, self._objects) for c in relevant}
            if len(outputs) != 1:
                status, prediction = "ABSTAIN_AMBIGUOUS", None
            else:
                status, prediction = "PREDICT", next(iter(outputs))
        return {
            "decision_status": status,
            "prediction": prediction,
            "candidate_count": len(self._candidates),
            "candidate_set_hash": self.candidate_hash,
            "model_version": self.version_id,
            "proposal_count": self._last_proposal_count,
        }

    def revise(self, row: dict[str, Any], target: bool) -> dict[str, Any]:
        self._base._validate_row(row)
        if not isinstance(target, bool):
            raise ValueError("revealed target must be boolean")
        observation_id = row.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError("revealed observation requires a non-empty observation_id")
        if observation_id in self._seen_observation_ids:
            raise ValueError("observation has already been revised")
        before = self.candidate_hash
        old_candidates = set(self._candidates)
        self._evidence.append({"row": self._base._public(row), "target": target})
        self._seen_observation_ids.add(observation_id)
        candidates, attempted, exceeded = self._propose()
        self._last_proposal_count = attempted
        self._budget_exceeded = exceeded
        if not exceeded:
            self._candidates = candidates
        self._refresh_contrastive_state()
        self._version += 1
        operation = (
            "abstain" if exceeded else
            "expand" if self._candidates - old_candidates else
            "modify" if old_candidates - self._candidates else "keep"
        )
        return {
            "operation": operation,
            "before_candidate_hash": before,
            "after_candidate_hash": self.candidate_hash,
            "candidate_count": self.candidate_count,
            "status": self.status,
            "model_version": self.version_id,
            "proposal_count": attempted,
            "budget_exceeded": exceeded,
        }
