"""Finite relational-mechanism induction baseline for E10-A."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any

def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True, order=True)
class CandidateMechanism:
    relation_symbol: str
    feature_key: str
    role_values: tuple[str, ...]
    required_contexts: tuple[tuple[str, str], ...]

    def predict(self, row: dict[str, Any], objects: dict[str, dict[str, str]]) -> bool:
        if row.get("relation_symbol") != self.relation_symbol:
            return False
        ids = row.get("participants", [])
        if not isinstance(ids, list) or len(ids) != len(self.role_values) or len(set(ids)) != len(ids):
            return False
        try:
            values = sorted(objects[x][self.feature_key] for x in ids)
        except KeyError:
            return False
        context = dict(row.get("context", []))
        return values == list(self.role_values) and all(context.get(key) == value for key, value in self.required_contexts)

    def as_dict(self) -> dict[str, Any]:
        return {"relation_symbol": self.relation_symbol, "feature_key": self.feature_key, "role_values": list(self.role_values), "required_contexts": [list(pair) for pair in self.required_contexts]}

class E10AMechanismLearner:
    """Exact finite candidate-set learner; no evaluator truth or mechanism hash is accepted."""
    def __init__(self, support_payload: dict[str, Any]):
        if not isinstance(support_payload, dict) or support_payload.get("phase") != "support":
            raise ValueError("learner requires Support payload")
        self._objects = self._parse_objects(support_payload.get("objects"))
        rows = support_payload.get("observations")
        if not isinstance(rows, list): raise ValueError("Support observations must be a list")
        self._evidence = []
        for row in rows:
            if not isinstance(row.get("outcome"), bool): raise ValueError("Support outcome must be boolean")
            self._validate_row(row)
            if {"valid", "violation", "template_id", "role_objects", "source_group_id"} & set(row):
                raise ValueError("evaluator-only fields are forbidden in learner input")
            self._evidence.append({"row": self._public(row), "target": row["outcome"]})
        self._candidates = self._induce()
        self._version = 1

    @staticmethod
    def _parse_objects(rows: Any) -> dict[str, dict[str, str]]:
        if not isinstance(rows, list): raise ValueError("objects must be a list")
        out = {}
        for row in rows:
            oid, attrs = row.get("object_id"), row.get("attributes")
            if not isinstance(oid, str) or not oid or oid in out or not isinstance(attrs, list): raise ValueError("invalid object row")
            parsed = {}
            for pair in attrs:
                if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(v, str) and v for v in pair) or pair[0] in parsed: raise ValueError("invalid attribute pair")
                parsed[pair[0]] = pair[1]
            out[oid] = parsed
        return out

    def add_query_objects(self, rows: list[dict[str, Any]]) -> None:
        """Accept the one-time Query object table released by the phase gate."""
        parsed = self._parse_objects(rows)
        overlap = set(parsed) & set(self._objects)
        if overlap: raise ValueError("Support/Query object identity overlap")
        self._objects.update(parsed)

    def _validate_row(self, row: dict[str, Any]) -> None:
        ids = row.get("participants")
        if not isinstance(ids, list) or len(ids) < 2 or len(ids) != len(set(ids)) or any(x not in self._objects for x in ids): raise ValueError("invalid participants")
        if not isinstance(row.get("relation_symbol"), str) or not row["relation_symbol"] or not isinstance(row.get("context"), list): raise ValueError("invalid relation/context")

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {"observation_id": row.get("observation_id"), "relation_symbol": row["relation_symbol"], "participants": list(row["participants"]), "context": [list(x) for x in row["context"]]}

    def _induce(self) -> set[CandidateMechanism]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self._evidence: grouped.setdefault(item["row"]["relation_symbol"], []).append(item)
        candidates = set()
        for relation, items in grouped.items():
            positives = [x["row"] for x in items if x["target"] is True]
            negatives = [x["row"] for x in items if x["target"] is False]
            if not positives: continue
            arity = len(positives[0]["participants"])
            if any(len(x["participants"]) != arity for x in positives): continue
            feature_sets = []
            for row in positives:
                sets = [set(self._objects[oid]) for oid in row["participants"]]
                feature_sets.append(set.intersection(*sets))
            features = set.intersection(*feature_sets) if feature_sets else set()
            context_sets = [set(tuple(pair) for pair in row["context"]) for row in positives]
            contexts = set.intersection(*context_sets) if context_sets else set()
            for feature in features:
                first = [self._objects[oid][feature] for oid in positives[0]["participants"]]
                if len(set(first)) != arity: continue
                role_values = tuple(sorted(first))
                if any(tuple(sorted(self._objects[oid].get(feature, "") for oid in row["participants"])) != role_values for row in positives): continue
                # Treat the common context as a conjunction, not as unrelated
                # alternative single-key rules. Negative Support rows test each
                # conjunct independently.
                required_contexts = tuple(sorted(contexts))
                c = CandidateMechanism(relation, feature, role_values, required_contexts)
                if all(c.predict(row, self._objects) for row in positives) and all(not c.predict(row, self._objects) for row in negatives): candidates.add(c)
        return candidates

    @property
    def candidate_count(self) -> int: return len(self._candidates)
    @property
    def status(self) -> str: return "INCONSISTENT" if not self._candidates else ("IDENTIFIED" if len(self._candidates) == 1 else "AMBIGUOUS")
    @property
    def candidate_hash(self) -> str: return _hash([x.as_dict() for x in sorted(self._candidates)])
    @property
    def version_id(self) -> str: return f"e10a-mech-v{self._version}-{self.candidate_hash[:12]}"

    def predict(self, row: dict[str, Any]) -> dict[str, Any]:
        self._validate_row(row)
        relevant = [c for c in self._candidates if c.relation_symbol == row["relation_symbol"]]
        outputs = {c.predict(row, self._objects) for c in relevant}
        if not outputs: status, prediction = "ABSTAIN_INCONSISTENT", None
        elif len(outputs) > 1: status, prediction = "ABSTAIN_AMBIGUOUS", None
        else: status, prediction = "PREDICT", next(iter(outputs))
        return {"decision_status": status, "prediction": prediction, "candidate_count": len(self._candidates), "candidate_set_hash": self.candidate_hash, "model_version": self.version_id}

    def revise(self, row: dict[str, Any], target: bool) -> dict[str, Any]:
        self._validate_row(row)
        if not isinstance(target, bool): raise ValueError("revealed target must be boolean")
        before = self.candidate_hash
        self._evidence.append({"row": self._public(row), "target": target})
        # Online candidate elimination: filter only on the newly revealed row.
        self._candidates = {
            candidate for candidate in self._candidates
            if candidate.predict(row, self._objects) is target
        }
        self._version += 1
        return {"operation": "keep" if before == self.candidate_hash else "modify", "before_candidate_hash": before, "after_candidate_hash": self.candidate_hash, "candidate_count": self.candidate_count, "status": self.status, "model_version": self.version_id}