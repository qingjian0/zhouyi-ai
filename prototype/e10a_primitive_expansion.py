"""Bounded primitive/feature proposal for E10-A.

The learner may propose a new relation-feature mechanism only from revealed
positive evidence, then validate it against all revealed positives/negatives.
This is an explicit finite attribute-key search, not open-world feature invention.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from prototype.e10a_mechanism_learner import CandidateMechanism, E10AMechanismLearner


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class PrimitiveExpansionLearner:
    """Prequential learner that can add hypotheses from revealed evidence.

    Proposal grammar: (observed relation symbol, observed object attribute key,
    unordered distinct role-value tuple, conjunction of context pairs).
    The grammar is finite and bounded by proposal_budget and max_context_terms.
    """

    def __init__(
        self,
        support_payload: dict[str, Any],
        *,
        proposal_budget: int = 128,
        max_context_terms: int = 4,
    ):
        if (not isinstance(proposal_budget, int) or isinstance(proposal_budget, bool)
                or proposal_budget < 1):
            raise ValueError("proposal_budget must be a positive integer")
        if (not isinstance(max_context_terms, int) or isinstance(max_context_terms, bool)
                or max_context_terms < 0):
            raise ValueError("max_context_terms must be a non-negative integer")
        self._base = E10AMechanismLearner(support_payload)
        self._objects = self._base._objects
        self._evidence = list(self._base._evidence)
        self._candidates = set(self._base._candidates)
        self._proposal_budget = proposal_budget
        self._max_context_terms = max_context_terms
        self._version = 1
        self._last_proposal_count = 0
        self._budget_exceeded = False
        self._contrastive_relations: set[str] = set()
        self._refresh_contrastive_state()

    def add_query_objects(self, rows: list[dict[str, Any]]) -> None:
        self._base.add_query_objects(rows)
        self._objects = self._base._objects

    def _refresh_contrastive_state(self) -> None:
        grouped: dict[str, set[bool]] = {}
        for item in self._evidence:
            grouped.setdefault(item["row"]["relation_symbol"], set()).add(item["target"])
        self._contrastive_relations = {
            relation for relation, labels in grouped.items() if labels == {True, False}
        }

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def status(self) -> str:
        if self._budget_exceeded:
            return "BUDGET_EXCEEDED"
        if not self._candidates:
            return "INCONSISTENT"
        relations = {c.relation_symbol for c in self._candidates}
        if any(r not in self._contrastive_relations for r in relations):
            return "PROVISIONAL"
        return "IDENTIFIED" if len(self._candidates) == 1 else "AMBIGUOUS"

    @property
    def candidate_hash(self) -> str:
        return _hash([c.as_dict() for c in sorted(self._candidates)])

    @property
    def version_id(self) -> str:
        return f"e10a-expand-v{self._version}-{self.candidate_hash[:12]}"

    @property
    def last_proposal_count(self) -> int:
        return self._last_proposal_count

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

    def _propose(self) -> tuple[set[CandidateMechanism], int, bool]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self._evidence:
            grouped.setdefault(item["row"]["relation_symbol"], []).append(item)
        proposals: set[CandidateMechanism] = set()
        attempted = 0
        for relation in sorted(grouped):
            items = grouped[relation]
            positives = [x["row"] for x in items if x["target"] is True]
            negatives = [x["row"] for x in items if x["target"] is False]
            if not positives:
                continue
            arity = len(positives[0]["participants"])
            if arity < 2 or any(len(x["participants"]) != arity for x in positives):
                continue
            common_features: set[str] | None = None
            for row in positives:
                row_features = [
                    set(self._objects[oid]) for oid in row["participants"]
                ]
                shared = set.intersection(*row_features)
                common_features = shared if common_features is None else common_features & shared
            common_contexts: set[tuple[str, str]] | None = None
            for row in positives:
                pairs = {tuple(pair) for pair in row["context"]}
                common_contexts = pairs if common_contexts is None else common_contexts & pairs
            contexts = tuple(sorted(common_contexts or set()))
            if len(contexts) > self._max_context_terms:
                continue
            for feature in sorted(common_features or set()):
                first_values = [self._objects[oid][feature] for oid in positives[0]["participants"]]
                if len(set(first_values)) != arity:
                    continue
                role_values = tuple(sorted(first_values))
                if any(
                    tuple(sorted(self._objects[oid].get(feature, "") for oid in row["participants"])) != role_values
                    for row in positives
                ):
                    continue
                attempted += 1
                if attempted > self._proposal_budget:
                    return set(), attempted, True
                candidate = CandidateMechanism(relation, feature, role_values, contexts)
                if (all(candidate.predict(row, self._objects) for row in positives)
                        and all(not candidate.predict(row, self._objects) for row in negatives)):
                    proposals.add(candidate)
        return proposals, attempted, False

    def revise(self, row: dict[str, Any], target: bool) -> dict[str, Any]:
        self._base._validate_row(row)
        if not isinstance(target, bool):
            raise ValueError("revealed target must be boolean")
        before = self.candidate_hash
        old_candidates = set(self._candidates)
        self._evidence.append({"row": self._base._public(row), "target": target})
        proposed, attempted, exceeded = self._propose()
        self._last_proposal_count = attempted
        self._budget_exceeded = exceeded
        if exceeded:
            # Fail closed: retain the prior candidate set, but do not claim a revision.
            operation = "abstain"
        else:
            self._candidates = proposed
            operation = "expand" if proposed - old_candidates else (
                "keep" if before == self.candidate_hash else "modify"
            )
        self._refresh_contrastive_state()
        self._version += 1
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
