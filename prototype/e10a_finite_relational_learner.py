"""Finite relational version-space learner for the E10-A object-disjoint task.

The learner searches a declared, deliberately narrow hypothesis language:
one categorical feature, an unordered set of distinct role values, and one
context equality. It does not receive generator truth or template metadata.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Any


SCHEMA = "e10a-finite-relational-dsl-v1"
DECISIONS = {"PREDICT", "ABSTAIN_AMBIGUOUS", "ABSTAIN_INCONSISTENT", "ABSTAIN_BUDGET"}


class RelationalLearnerError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class RelationRule:
    relation_symbol: str
    feature_key: str
    role_values: tuple[str, ...]
    context_key: str
    context_value: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "relation_symbol": self.relation_symbol,
            "feature_key": self.feature_key,
            "role_values": list(self.role_values),
            "context_key": self.context_key,
            "context_value": self.context_value,
            "role_order": "permutation_invariant",
        }


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _pairs(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, list):
        raise RelationalLearnerError(f"{field} must be a list of key/value pairs")
    result: dict[str, str] = {}
    for pair in value:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(item, str) and item for item in pair)):
            raise RelationalLearnerError(f"{field} contains a malformed pair")
        if pair[0] in result:
            raise RelationalLearnerError(f"{field} contains duplicate keys")
        result[pair[0]] = pair[1]
    return result


class FiniteRelationalVersionSpace:
    """Exact version-space learner over a finite, explicit relational DSL."""

    def __init__(self, *, max_candidates: int = 50_000) -> None:
        if not isinstance(max_candidates, int) or isinstance(max_candidates, bool) or max_candidates < 1:
            raise RelationalLearnerError("max_candidates must be a positive integer")
        self.max_candidates = max_candidates
        self._objects: dict[str, dict[str, str]] = {}
        self._support_feature_values: dict[str, set[str]] = {}
        self._support_context_values: dict[str, set[str]] = {}
        self._support_rows: list[dict[str, Any]] = []
        self._evidence_rows: list[dict[str, Any]] = []
        self._universe: dict[str, tuple[RelationRule, ...]] = {}
        self._versions: dict[str, tuple[RelationRule, ...]] = {}
        self._report: dict[str, Any] = {"fitted": False}

    @staticmethod
    def _validate_objects(rows: Any) -> dict[str, dict[str, str]]:
        if not isinstance(rows, list) or not rows:
            raise RelationalLearnerError("object table must be a non-empty list")
        result: dict[str, dict[str, str]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise RelationalLearnerError("object record must be an object")
            object_id = row.get("object_id")
            if not isinstance(object_id, str) or not object_id:
                raise RelationalLearnerError("object_id must be non-empty")
            if object_id in result:
                raise RelationalLearnerError("duplicate object_id")
            result[object_id] = _pairs(row.get("attributes"), "attributes")
        return result

    @staticmethod
    def _validate_observations(rows: Any, *, labelled: bool) -> list[dict[str, Any]]:
        if not isinstance(rows, list) or not rows:
            raise RelationalLearnerError("observations must be a non-empty list")
        result = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise RelationalLearnerError("observation must be an object")
            observation_id = row.get("observation_id")
            relation_symbol = row.get("relation_symbol")
            participants = row.get("participants")
            if not isinstance(observation_id, str) or not observation_id or observation_id in seen:
                raise RelationalLearnerError("observation IDs must be non-empty and unique")
            seen.add(observation_id)
            if not isinstance(relation_symbol, str) or not relation_symbol:
                raise RelationalLearnerError("relation_symbol must be non-empty")
            if (not isinstance(participants, list) or len(participants) not in (2, 3)
                    or any(not isinstance(item, str) or not item for item in participants)
                    or len(set(participants)) != len(participants)):
                raise RelationalLearnerError("participants must contain 2 or 3 distinct object IDs")
            context = _pairs(row.get("context"), "context")
            if labelled:
                if type(row.get("outcome")) is not bool:
                    raise RelationalLearnerError("labelled outcome must be an exact boolean")
            elif "outcome" in row or any(key in row for key in
                    ("valid", "violation", "template_id", "role_objects", "source_group_id")):
                raise RelationalLearnerError("query observation contains evaluator-only fields")
            result.append({
                "observation_id": observation_id,
                "relation_symbol": relation_symbol,
                "participants": list(participants),
                "context": context,
                **({"outcome": row["outcome"]} if labelled else {}),
            })
        return result

    @staticmethod
    def _matches(rule: RelationRule, row: dict[str, Any],
                 objects: dict[str, dict[str, str]]) -> bool:
        if row["relation_symbol"] != rule.relation_symbol:
            return False
        context = row["context"]
        if context.get(rule.context_key) != rule.context_value:
            return False
        values = []
        for object_id in row["participants"]:
            attributes = objects.get(object_id)
            if attributes is None or rule.feature_key not in attributes:
                return False
            values.append(attributes[rule.feature_key])
        return len(set(values)) == len(values) and tuple(sorted(values)) == rule.role_values

    def _enumerate_universe(
        self, rows: list[dict[str, Any]], objects: dict[str, dict[str, str]]
    ) -> tuple[dict[str, tuple[RelationRule, ...]], int]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["relation_symbol"], []).append(row)
        feature_keys = sorted({key for attrs in objects.values() for key in attrs})
        context_pairs = {
            (key, value)
            for row in rows for key, value in row["context"].items()
        }
        universe: dict[str, tuple[RelationRule, ...]] = {}
        evaluated = 0
        for relation_symbol, examples in sorted(grouped.items()):
            arities = {len(row["participants"]) for row in examples}
            if len(arities) != 1:
                raise RelationalLearnerError("one relation symbol cannot mix arities")
            arity = next(iter(arities))
            candidates = []
            for feature_key in feature_keys:
                values = sorted({
                    attrs[feature_key] for attrs in objects.values()
                    if feature_key in attrs
                })
                for role_values in itertools.combinations(values, arity):
                    for context_key, context_value in sorted(context_pairs):
                        evaluated += 1
                        if evaluated > self.max_candidates:
                            raise RelationalLearnerError("candidate generation budget exceeded")
                        candidates.append(RelationRule(
                            relation_symbol, feature_key, tuple(role_values),
                            context_key, context_value,
                        ))
            universe[relation_symbol] = tuple(candidates)
        return universe, evaluated

    def fit(self, support_payload: dict[str, Any]) -> "FiniteRelationalVersionSpace":
        if not isinstance(support_payload, dict) or support_payload.get("phase") != "support":
            raise RelationalLearnerError("fit accepts only a Support payload")
        if support_payload.get("schema_version") != "e10a-object-disjoint-task-v1":
            raise RelationalLearnerError("unsupported Support schema")
        objects = self._validate_objects(support_payload.get("objects"))
        rows = self._validate_observations(support_payload.get("observations"), labelled=True)
        for row in rows:
            if any(object_id not in objects for object_id in row["participants"]):
                raise RelationalLearnerError("Support observation references unknown object")
        universe, generated = self._enumerate_universe(rows, objects)
        self._objects = objects
        self._support_feature_values = {}
        for attributes in objects.values():
            for key, value in attributes.items():
                self._support_feature_values.setdefault(key, set()).add(value)
        self._support_context_values = {}
        for row in rows:
            for key, value in row["context"].items():
                self._support_context_values.setdefault(key, set()).add(value)
        self._support_rows = rows
        self._evidence_rows = list(rows)
        self._universe = universe
        self._versions = {
            relation: tuple(rule for rule in candidates
                            if all(self._matches(rule, row, objects) == row["outcome"]
                                   for row in rows if row["relation_symbol"] == relation))
            for relation, candidates in universe.items()
        }
        retained = sum(len(items) for items in self._versions.values())
        self._report = {
            "fitted": True,
            "dsl_schema": SCHEMA,
            "support_observations": len(rows),
            "relation_count": len(universe),
            "candidate_generation_evaluations": generated,
            "candidate_universe_size": sum(len(items) for items in universe.values()),
            "consistent_candidate_count": retained,
            "max_candidates": self.max_candidates,
            "target_template_labels_received": False,
            "role_order_identified": False,
            "role_semantics": "unordered_role_value_set; permutation invariant",
            "gradient_updates": 0,
        }
        return self

    def predict(self, observation: dict[str, Any],
                query_objects: list[dict[str, Any]]) -> dict[str, Any]:
        if not self._report.get("fitted"):
            raise RelationalLearnerError("fit Support before prediction")
        objects = self._validate_objects(query_objects)
        row = self._validate_observations([observation], labelled=False)[0]
        if any(object_id not in objects for object_id in row["participants"]):
            raise RelationalLearnerError("Query observation references unknown Query object")
        candidates = self._versions.get(row["relation_symbol"], ())
        candidate_payload = [item.as_dict() for item in candidates]
        candidate_hash = _hash(candidate_payload)
        participant_attributes = [objects[object_id] for object_id in row["participants"]]
        query_feature_keys = {key for attrs in participant_attributes for key in attrs}
        support_feature_keys = set(self._support_feature_values)
        query_context_keys = set(row["context"])
        support_context_keys = set(self._support_context_values)
        if row["relation_symbol"] not in self._versions:
            status, prediction, confidence, agreement = (
                "ABSTAIN_OOD_RELATION", None, None, None
            )
        elif query_feature_keys - support_feature_keys or query_context_keys - support_context_keys:
            status, prediction, confidence, agreement = (
                "ABSTAIN_OOD_SCHEMA", None, None, None
            )
        elif any(
            not (set(attrs) & support_feature_keys)
            for attrs in participant_attributes
        ):
            status, prediction, confidence, agreement = (
                "ABSTAIN_OOD_SCHEMA", None, None, None
            )
        elif any(
            value not in self._support_feature_values.get(key, set())
            for attrs in participant_attributes for key, value in attrs.items()
            if key in support_feature_keys
        ) or any(
            value not in self._support_context_values.get(key, set())
            for key, value in row["context"].items()
        ):
            status, prediction, confidence, agreement = (
                "ABSTAIN_OOD_VALUE", None, None, None
            )
        elif not candidates:
            status, prediction, confidence, agreement = (
                "ABSTAIN_INCONSISTENT", None, None, None
            )
        else:
            votes = [self._matches(rule, row, objects) for rule in candidates]
            positives = sum(votes)
            negatives = len(votes) - positives
            agreement = max(positives, negatives) / len(votes)
            if positives and negatives:
                status, prediction, confidence = "ABSTAIN_AMBIGUOUS", None, None
            else:
                status = "PREDICT"
                prediction = positives == len(votes)
                # Version-space unanimity is not a calibrated probability.
                confidence = None
        return {
            "observation_id": row["observation_id"],
            "decision_status": status,
            "prediction": prediction,
            "confidence": confidence,
            "agreement_score": agreement,
            "candidate_set_hash": candidate_hash,
            "compute_cost": {
                "candidate_count": len(candidates),
                "candidate_evaluations": len(candidates),
                "rule_match_evaluations": len(candidates),
                "candidate_generation_evaluations": 0,
            },
        }

    def update(self, observation: dict[str, Any], label: bool,
               query_objects: list[dict[str, Any]], *,
               mode: str = "INCREMENTAL_FILTER") -> dict[str, Any]:
        if mode not in {"FROZEN", "BATCH_REFIT", "INCREMENTAL_FILTER"}:
            raise RelationalLearnerError("unsupported update mode")
        if type(label) is not bool:
            raise RelationalLearnerError("revealed label must be an exact boolean")
        objects = self._validate_objects(query_objects)
        row = self._validate_observations([observation], labelled=False)[0]
        if any(object_id not in objects for object_id in row["participants"]):
            raise RelationalLearnerError("revealed observation references unknown Query object")
        for object_id, attributes in objects.items():
            if object_id in self._objects and self._objects[object_id] != attributes:
                raise RelationalLearnerError("object identity cannot change attributes")
        before = self._versions.get(row["relation_symbol"], ())
        self._objects.update(objects)
        labelled_row = {**row, "outcome": label}
        self._evidence_rows.append(labelled_row)

        if mode == "FROZEN":
            after = before
            operations = 0
        elif mode == "INCREMENTAL_FILTER":
            after = tuple(rule for rule in before
                          if self._matches(rule, labelled_row, self._objects) == label)
            operations = len(before)
        else:
            relation = row["relation_symbol"]
            all_evidence = [item for item in self._evidence_rows
                            if item["relation_symbol"] == relation]
            retained = []
            operations = 0
            for rule in self._universe.get(relation, ()):
                consistent = True
                for item in all_evidence:
                    operations += 1
                    if self._matches(rule, item, self._objects) != item["outcome"]:
                        consistent = False
                        break
                if consistent:
                    retained.append(rule)
            after = tuple(retained)

        self._versions[row["relation_symbol"]] = after
        changed = set(before) != set(after)
        self._report.update({
            "revealed_observations": len(self._evidence_rows) - len(self._support_rows),
            "consistent_candidate_count": sum(len(items) for items in self._versions.values()),
            "last_update_mode": mode,
            "last_update_candidate_operations": operations,
            "last_update_changed_version_space": changed,
        })
        return {
            "operation": "keep" if not changed else ("suspend" if not after else "modify"),
            "before_candidate_count": len(before),
            "after_candidate_count": len(after),
            "candidate_operations": operations,
            "changed": changed,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "report": dict(self._report),
            "version_spaces": {
                relation: [rule.as_dict() for rule in candidates]
                for relation, candidates in sorted(self._versions.items())
            },
            "evidence_digest": _hash(self._evidence_rows),
        }
