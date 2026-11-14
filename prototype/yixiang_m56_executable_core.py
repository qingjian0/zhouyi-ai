"""M56 executable core: evidence schemas and controlled yixiang tasks.

The generator deliberately separates agent-visible observations from evaluator truth.
It is a synthetic protocol harness, not a claim about classical-text interpretation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import random
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

SCHEMA_VERSION = "m56-case-v0.1"
TASKS = ("support_task", "flow_task", "containment_task")
TASK_FEATURES = {
    "support_task": ("capacity", "load"),
    "flow_task": ("rate", "pressure"),
    "containment_task": ("boundary_strength", "contents"),
}
TASK_RELATIONS = {
    "support_task": "supports",
    "flow_task": "flows_to",
    "containment_task": "contains",
}
SPLITS = ("train", "validation", "test")
TRANSFER_DISTANCES = ("within_domain", "near_domain", "far_domain")
ANALOGY_GRANULARITIES = ("lexical", "feature", "relational", "mechanism", "long_context")


@dataclass(frozen=True)
class EvidenceSpan:
    source_id: str
    start: int
    end: int
    quote: str

    def validate(self) -> None:
        if not self.source_id or self.start < 0 or self.end <= self.start:
            raise ValueError("invalid_evidence_span")
        if not self.quote:
            raise ValueError("empty_evidence_quote")


@dataclass(frozen=True)
class SourceProvenance:
    source_id: str
    source_type: str
    work: str
    chapter: str
    edition: str
    locator: str
    text_layer: str
    period: str

    def validate(self) -> None:
        required = (self.source_id, self.source_type, self.work, self.edition,
                    self.locator, self.text_layer, self.period)
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("incomplete_source_provenance")
        if self.text_layer not in {
            "primary_text", "variant_witness", "editorial_punctuation",
            "commentary", "modern_paraphrase", "model_interpretation",
            "synthetic_observation",
        }:
            raise ValueError("unknown_text_layer")


@dataclass(frozen=True)
class Relation:
    source_role: str
    predicate: str
    target_role: str

    def validate(self) -> None:
        if not self.source_role or not self.predicate or not self.target_role:
            raise ValueError("incomplete_relation")


@dataclass(frozen=True)
class Observation:
    observation_id: str
    domain: str
    features: Mapping[str, Any]
    relations: Tuple[Relation, ...]
    evidence: Tuple[EvidenceSpan, ...]
    provenance: SourceProvenance

    def validate(self) -> None:
        if not self.observation_id or not self.domain:
            raise ValueError("incomplete_observation")
        if not isinstance(self.features, Mapping) or not self.features:
            raise ValueError("observation_features_required")
        self.provenance.validate()
        if self.provenance.text_layer != "synthetic_observation":
            raise ValueError("synthetic_case_requires_synthetic_provenance")
        for relation in self.relations:
            relation.validate()
        for span in self.evidence:
            span.validate()


@dataclass(frozen=True)
class TaskContext:
    task_id: str
    purpose: str
    constraints: Tuple[str, ...]
    allowed_evidence: Tuple[str, ...]
    transfer_distance: str = "within_domain"
    analogy_granularity: str = "relational"

    def validate(self) -> None:
        if self.task_id not in TASK_FEATURES or not self.purpose.strip():
            raise ValueError("invalid_task_context")
        if not self.allowed_evidence:
            raise ValueError("allowed_evidence_required")
        if self.transfer_distance not in TRANSFER_DISTANCES:
            raise ValueError("invalid_transfer_distance")
        if self.analogy_granularity not in ANALOGY_GRANULARITIES:
            raise ValueError("invalid_analogy_granularity")


def validate_case(case: Mapping[str, Any]) -> None:
    """Validate the public case envelope; evaluator truth is forbidden here."""
    if case.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported_schema_version")
    if "evaluator_truth" in case or "gold" in case:
        raise ValueError("evaluator_truth_leakage")
    context = case.get("task_context")
    if not isinstance(context, Mapping):
        raise ValueError("task_context_required")
    TaskContext(**context).validate()
    observations = case.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations_required")
    for item in observations:
        provenance = SourceProvenance(**item["provenance"])
        relations = tuple(Relation(**edge) for edge in item.get("relations", []))
        evidence = tuple(EvidenceSpan(**span) for span in item.get("evidence", []))
        Observation(
            observation_id=item["observation_id"], domain=item["domain"],
            features=item["features"], relations=relations, evidence=evidence,
            provenance=provenance,
        ).validate()


def _split_for(index: int, count: int) -> str:
    if index < int(count * 0.70):
        return "train"
    if index < int(count * 0.85):
        return "validation"
    return "test"


def _make_observation(case_id: str, domain: str, features: Mapping[str, Any],
                      predicate: str) -> Dict[str, Any]:
    source_id = f"synthetic:{case_id}:{domain}"
    provenance = SourceProvenance(
        source_id=source_id, source_type="synthetic", work="M56 controlled generator",
        chapter="feature-selection", edition="generator-v0.1",
        locator=source_id, text_layer="synthetic_observation", period="synthetic",
    )
    observation = Observation(
        observation_id=f"{case_id}:{domain}", domain=domain, features=dict(features),
        relations=(Relation("agent", predicate, "object"),),
        evidence=(EvidenceSpan(source_id, 0, 1, "synthetic feature record"),),
        provenance=provenance,
    )
    observation.validate()
    return {
        "observation_id": observation.observation_id,
        "domain": observation.domain,
        "features": dict(observation.features),
        "relations": [asdict(edge) for edge in observation.relations],
        "evidence": [asdict(span) for span in observation.evidence],
        "provenance": asdict(observation.provenance),
    }


def generate_dataset(*, count: int = 240, seed: int = 5601,
                     nuisance_mode: str = "independent") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (agent-visible cases, evaluator-only truth) with independent RNG streams.

    nuisance_mode='train_spurious' creates a split-dependent nuisance shortcut:
    nuisance agrees with the hidden class in train, is independent in validation,
    and is reversed in test. The task-relevant features remain unchanged.
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 20:
        raise ValueError("count_must_be_integer_at_least_20")
    if nuisance_mode not in {"independent", "train_spurious"}:
        raise ValueError("unknown_nuisance_mode")
    class_rng = random.Random(seed ^ 0xC1A55E)
    transfer_rng = random.Random(seed ^ 0x7A4E5F)
    feature_rng = random.Random(seed ^ 0x56A11CE)
    nuisance_rng = random.Random(seed ^ 0xA3D19B7)
    cases: List[Dict[str, Any]] = []
    truth: Dict[str, Any] = {}
    for index in range(count):
        task_id = TASKS[index % len(TASKS)]
        split = _split_for(index, count)
        case_id = f"m56-{seed}-{index:05d}"
        positive = bool(class_rng.getrandbits(1))
        relevant = TASK_FEATURES[task_id]
        predicate = TASK_RELATIONS[task_id]
        values: Dict[str, Any] = {
            "capacity": round(feature_rng.uniform(0.2, 1.0), 4),
            "load": round(feature_rng.uniform(0.2, 1.0), 4),
            "rate": round(feature_rng.uniform(0.2, 1.0), 4),
            "pressure": round(feature_rng.uniform(0.2, 1.0), 4),
            "boundary_strength": round(feature_rng.uniform(0.2, 1.0), 4),
            "contents": round(feature_rng.uniform(0.2, 1.0), 4),
            "surface_color": feature_rng.choice(("red", "blue", "green")),
            "surface_shape": feature_rng.choice(("round", "angular", "flat")),
            "wording_variant": feature_rng.choice(("alpha", "beta", "gamma")),
        }
        # Hidden class signal is encoded in task-relevant features and the relation.
        signal = 0.85 if positive else 0.15
        for feature in relevant:
            values[feature] = round(max(0.0, min(1.0, signal + feature_rng.uniform(-0.08, 0.08))), 4)
        if nuisance_mode == "train_spurious" and split == "train":
            nuisance = positive
        elif nuisance_mode == "train_spurious" and split == "test":
            nuisance = not positive
        else:
            nuisance = bool(nuisance_rng.getrandbits(1))
        values["incidental_marker"] = "marked" if nuisance else "plain"
        # The second domain changes surface form but keeps or reverses the relation.
        valid_transfer = bool(transfer_rng.getrandbits(1))
        target_predicate = predicate if valid_transfer else f"not_{predicate}"
        transfer_distance = TRANSFER_DISTANCES[index % len(TRANSFER_DISTANCES)]
        analogy_granularity = ANALOGY_GRANULARITIES[index % len(ANALOGY_GRANULARITIES)]
        source_domain = "familiar-domain"
        target_domain = {
            "within_domain": "familiar-domain",
            "near_domain": "near-transfer-domain",
            "far_domain": "far-transfer-domain",
        }[transfer_distance]
        source = _make_observation(case_id, source_domain, values, predicate)
        target_values = dict(values)
        target_values["surface_color"] = feature_rng.choice(("red", "blue", "green"))
        target_values["surface_shape"] = feature_rng.choice(("round", "angular", "flat"))
        target = _make_observation(case_id, target_domain, target_values, target_predicate)
        context = TaskContext(
            task_id=task_id,
            purpose={
                "support_task": "identify load-bearing support",
                "flow_task": "identify directed flow",
                "containment_task": "identify containment",
            }[task_id],
            constraints=("use task-relevant evidence", "do not infer from incidental marker"),
            allowed_evidence=("features", "relations", "provenance"),
            transfer_distance=transfer_distance,
            analogy_granularity=analogy_granularity,
        )
        public_case = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "task_context": asdict(context),
            "observations": [source, target],
        }
        validate_case(public_case)
        cases.append(public_case)
        truth[case_id] = {
            "split": split,
            "selected_features": list(relevant),
            "class_member": positive,
            "relation_predicate": predicate,
            "transfer_valid": valid_transfer,
            "nuisance_value": nuisance,
        }
    return cases, truth


def task_shift_views(case: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Create alternate task views over the same observation, without gold labels."""
    views = []
    for task_id in TASKS:
        view = dict(case)
        view["task_context"] = asdict(TaskContext(
            task_id=task_id,
            purpose=f"task-shift:{task_id}",
            constraints=("same observation; changed purpose",),
            allowed_evidence=("features", "relations", "provenance"),
            transfer_distance=case["task_context"].get("transfer_distance", "within_domain"),
            analogy_granularity=case["task_context"].get("analogy_granularity", "relational"),
        ))
        views.append(view)
    return views


def select_features_by_rule(case: Mapping[str, Any]) -> Tuple[str, ...]:
    """Transparent non-learning control: task contract only, not an agent result."""
    validate_case(case)
    return tuple(TASK_FEATURES[case["task_context"]["task_id"]])


def category_decision(features: Mapping[str, Any], required: Sequence[str],
                      *, threshold: float = 0.75) -> str:
    """Minimal open-set contract: member / non_member / unknown."""
    if not features or not required:
        return "unknown"
    observed = [features.get(key) for key in required]
    if any(value is None for value in observed):
        return "unknown"
    numeric = [value for value in observed if isinstance(value, (int, float))]
    if len(numeric) != len(required):
        return "unknown"
    return "member" if all(value >= threshold for value in numeric) else "non_member"


def relation_preservation(source: Sequence[Mapping[str, str]],
                          target: Sequence[Mapping[str, str]],
                          role_map: Mapping[str, str]) -> Dict[str, Any]:
    """Score directed relation preservation after an explicit role mapping."""
    mapped = {
        (role_map.get(edge["source_role"]), edge["predicate"],
         role_map.get(edge["target_role"]))
        for edge in source
    }
    observed = {
        (edge["source_role"], edge["predicate"], edge["target_role"])
        for edge in target
    }
    if any(None in edge for edge in mapped):
        return {"valid": False, "preserved": 0, "required": len(mapped), "rate": 0.0}
    preserved = len(mapped & observed)
    required = len(mapped)
    return {
        "valid": required > 0 and preserved == required,
        "preserved": preserved,
        "required": required,
        "rate": preserved / required if required else 0.0,
    }


def revise_category(hypothesis: Mapping[str, Any],
                    counterexample: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply a local, auditable revision; never silently erase unaffected scope."""
    current = dict(hypothesis)
    history = list(current.get("revision_history", []))
    scope = list(current.get("scope", []))
    family = counterexample.get("family")
    violated = list(counterexample.get("violated_features", []))
    if not family or not violated:
        action = "request_more_evidence"
    elif family in scope:
        scope = [item for item in scope if item != family]
        action = "narrow"
    else:
        action = "retain"
    event = {
        "action": action,
        "counterexample_id": counterexample.get("case_id", "unknown"),
        "violated_features": violated,
        "scope_before": list(current.get("scope", [])),
        "scope_after": list(scope),
    }
    history.append(event)
    current["scope"] = scope
    current["revision_history"] = history
    current["version"] = int(current.get("version", 0)) + 1
    return current


def audit_dataset(cases: Sequence[Mapping[str, Any]],
                  truth: Mapping[str, Any]) -> Dict[str, Any]:
    """Check public/evaluator separation, split integrity, and task-shift diversity."""
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)) or set(ids) != set(truth):
        raise ValueError("case_truth_id_mismatch")
    for case in cases:
        validate_case(case)
    splits = {name: 0 for name in SPLITS}
    nuisance_by_split: Dict[str, List[Tuple[bool, bool]]] = {name: [] for name in SPLITS}
    for case_id, record in truth.items():
        split = record["split"]
        if split not in splits:
            raise ValueError("unknown_split")
        splits[split] += 1
        nuisance_by_split[split].append(
            (bool(record["nuisance_value"]), bool(record["class_member"]))
        )
    return {
        "cases": len(cases),
        "splits": splits,
        "public_truth_leaks": sum(
            1 for case in cases
            if "evaluator_truth" in case or "gold" in case
        ),
        "task_count": len({case["task_context"]["task_id"] for case in cases}),
        "nuisance_class_agreement": {
            split: (
                sum(left == right for left, right in pairs) / len(pairs)
                if pairs else None
            )
            for split, pairs in nuisance_by_split.items()
        },
    }


def write_dataset(cases: Sequence[Mapping[str, Any]], truth: Mapping[str, Any],
                  output_prefix: str) -> Dict[str, str]:
    public_path = output_prefix + ".agent.jsonl"
    truth_path = output_prefix + ".evaluator.json"
    with open(public_path, "w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    with open(truth_path, "w", encoding="utf-8") as handle:
        json.dump(truth, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return {"agent": public_path, "evaluator": truth_path}
