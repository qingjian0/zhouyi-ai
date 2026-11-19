# Classiang evidence-bound observation ingestion v1

## Purpose

`prototype/classiang_observation_ingest.py` provides a strict adapter from
structured feature claims to the existing classiang `Observation` contract.
It is the first input-boundary slice for the observation-to-class pipeline.

## Contract

Each claim must provide:

- a supported feature dimension and non-empty value;
- one or more source evidence references declared by the observation;
- an exact source-text quote and its half-open character span;
- optional task-purpose relevance scores supplied by an upstream reviewer or
  model.

The adapter creates deterministic feature IDs and span-qualified evidence
references. It preserves the original source references on the observation.
Offsets are Python Unicode code-point offsets, not UTF-8 byte offsets.

## Fail-closed behavior

The adapter rejects unknown evidence references, duplicate references,
out-of-range or boolean offsets, quote/span mismatches, malformed claims, and
invalid feature dimensions. It does not silently repair or infer missing data.

## Claim boundary

This is not an NLP parser, OCR engine, vision encoder, speech recognizer, or
autonomous semantic feature extractor. It does not derive claims from raw
unstructured text and does not invent task relevance scores. Empty relevance
scores remain unscored, so the existing aspect selector cannot silently treat
them as selected. The upstream observation/perception component must propose
claims and a separate evidence/relevance gate must review them.

## Next integration gates

1. Connect approved text/image/event adapters that emit the same source-span
   and evidence-reference contract.
2. Add provenance-preserving adapters for image regions, timestamps, and
   structured relations without conflating their coordinate systems.
3. Evaluate extraction precision/recall and unsupported-claim rate on
   independently annotated, source-licensed multi-domain data.
4. Persist accepted feature proposals and class revisions through the
   authoritative lifecycle/event store; keep unreviewed proposals separate.
5. Run clean-checkout end-to-end tests across ingest, aspect selection,
   class induction, analogy mapping, verification, and counterexample revision.

Passing unit tests validate this adapter contract only. They do not establish
semantic understanding or general-purpose classiang capability.
