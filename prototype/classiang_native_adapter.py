"""Evidence-preserving adapter from the class-formation engine to native graphs.

The adapter does not invent source metadata. Callers must provide reviewed
EvidenceRef records for every evidence ID carried by the observation/hypothesis.
"""
from __future__ import annotations

import hashlib
from typing import Mapping

from prototype.classiang_engine import ClassHypothesis, FeatureAtom, Observation
from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\\0".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:20]}"


def observation_to_symbol_graph(
    observation: Observation,
    evidence_catalog: Mapping[str, EvidenceRef],
    *,
    hypothesis: ClassHypothesis | None = None,
    contradiction_evidence: Mapping[FeatureAtom, tuple[str, ...]] | None = None,
) -> SymbolGraph:
    """Project one validated observation and optional class rule into a graph.

    The subject, observed aspects, and class-rule aspects become explicit
    symbols. Relations preserve role direction and evidence lineage. Explicit
    contradictions require a caller-supplied evidence mapping; they are never
    silently assigned all observation evidence.
    """
    if not isinstance(observation, Observation):
        raise ValueError("observation must be Observation")
    observation.validate()
    if hypothesis is not None and not isinstance(hypothesis, ClassHypothesis):
        raise ValueError("hypothesis must be ClassHypothesis")
    if observation.explicit_contradictions:
        if contradiction_evidence is None:
            raise ValueError("explicit contradictions require contradiction_evidence")
        if set(contradiction_evidence) != set(observation.explicit_contradictions):
            raise ValueError("contradiction_evidence must cover every explicit contradiction exactly")

    required_ids = set(observation.evidence_refs)
    for feature in observation.features:
        required_ids.update(feature.evidence_refs)
    if hypothesis is not None:
        required_ids.update(hypothesis.evidence_refs)
        required_ids.update(hypothesis.counterexample_refs)
    for atom, refs in (contradiction_evidence or {}).items():
        if atom not in observation.explicit_contradictions:
            raise ValueError("contradiction evidence references an undeclared contradiction")
        if not isinstance(refs, tuple) or not refs or len(refs) != len(set(refs)):
            raise ValueError("each contradiction needs unique, non-empty evidence IDs")
        if not set(refs) <= set(observation.evidence_refs):
            raise ValueError("contradiction evidence must belong to the observation")
        required_ids.update(refs)

    missing = required_ids - set(evidence_catalog)
    if missing:
        raise ValueError(f"evidence catalog is missing IDs: {sorted(missing)}")
    evidence = tuple(evidence_catalog[item] for item in sorted(required_ids))
    for item in evidence:
        if not isinstance(item, EvidenceRef):
            raise ValueError("evidence catalog values must be EvidenceRef")
        item.validate()
    if any(not item.reviewed for item in evidence):
        raise ValueError("unreviewed evidence cannot be adapted into the trusted graph")
    if any(key != value.evidence_id for key, value in evidence_catalog.items() if key in required_ids):
        raise ValueError("evidence catalog keys must match EvidenceRef.evidence_id")

    subject_id = _stable_id("subject", observation.observation_id)
    symbols = [
        Symbol(
            subject_id, observation.domain, "observed_subject",
            (("subject_id", observation.subject_id),),
            tuple(sorted(observation.evidence_refs)), observation.context,
        )
    ]
    relations = []
    for feature in observation.features:
        aspect_id = _stable_id(
            "aspect", observation.observation_id, feature.feature_id,
            feature.atom.dimension, feature.atom.value,
        )
        score_map = dict(feature.purpose_scores)
        attributes = (
            ("dimension", feature.atom.dimension),
            ("value", feature.atom.value),
        )
        symbols.append(Symbol(
            aspect_id, observation.domain, "observed_aspect",
            attributes, tuple(sorted(feature.evidence_refs)), observation.context,
        ))
        conditions = tuple(sorted(
            f"purpose_score:{purpose}:{score:.8g}"
            for purpose, score in score_map.items()
        ))
        relations.append(Relation(
            _stable_id("relation", observation.observation_id, feature.feature_id),
            "has_aspect",
            (("subject", subject_id), ("aspect", aspect_id)),
            tuple(sorted(feature.evidence_refs)),
            conditions=conditions,
            context=observation.context,
        ))

    for index, atom in enumerate(observation.explicit_contradictions):
        refs = contradiction_evidence[atom]
        aspect_id = _stable_id(
            "contradicted_aspect", observation.observation_id,
            atom.dimension, atom.value, str(index),
        )
        symbols.append(Symbol(
            aspect_id, observation.domain, "contradicted_aspect",
            (("dimension", atom.dimension), ("value", atom.value)),
            tuple(sorted(refs)), observation.context,
        ))
        relations.append(Relation(
            _stable_id("contradiction", observation.observation_id, str(index)),
            "contradicts_aspect",
            (("subject", subject_id), ("aspect", aspect_id)),
            tuple(sorted(refs)),
            context=observation.context,
        ))

    if hypothesis is not None:
        class_id = _stable_id(
            "class", hypothesis.class_id, str(hypothesis.version),
            hypothesis.purpose, hypothesis.validity_scope,
        )
        symbols.append(Symbol(
            class_id, hypothesis.validity_scope, "class_hypothesis",
            (("class_id", hypothesis.class_id),
             ("purpose", hypothesis.purpose),
             ("status", hypothesis.status.value),
             ("version", str(hypothesis.version))),
            tuple(sorted(hypothesis.evidence_refs)),
        ))
        for atom in hypothesis.required_features:
            aspect_id = _stable_id(
                "class_aspect", hypothesis.class_id, str(hypothesis.version),
                atom.dimension, atom.value,
            )
            symbols.append(Symbol(
                aspect_id, hypothesis.validity_scope, "required_aspect",
                (("dimension", atom.dimension), ("value", atom.value)),
                tuple(sorted(hypothesis.evidence_refs)),
            ))
            relations.append(Relation(
                _stable_id("class_requires", hypothesis.class_id,
                           str(hypothesis.version), atom.dimension, atom.value),
                "class_requires_aspect",
                (("class", class_id), ("aspect", aspect_id)),
                tuple(sorted(hypothesis.evidence_refs)),
                conditions=(f"purpose:{hypothesis.purpose}",
                            f"validity_scope:{hypothesis.validity_scope}"),
            ))
        if hypothesis.counterexample_refs:
            boundary_id = _stable_id(
                "class_boundary", hypothesis.class_id, str(hypothesis.version),
            )
            symbols.append(Symbol(
                boundary_id, hypothesis.validity_scope, "negative_boundary",
                (("class_id", hypothesis.class_id),),
                tuple(sorted(hypothesis.counterexample_refs)),
            ))
            relations.append(Relation(
                _stable_id("class_excludes", hypothesis.class_id,
                           str(hypothesis.version)),
                "class_excludes_boundary",
                (("class", class_id), ("boundary", boundary_id)),
                tuple(sorted(hypothesis.counterexample_refs)),
            ))

    graph = SymbolGraph(
        evidence=evidence,
        symbols=tuple(symbols),
        relations=tuple(relations),
    )
    graph.validate()
    return graph
