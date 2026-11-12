# M2 semantic extraction evaluation contract v1

Status: executable evaluation harness; no extractor or trained model is included.

## Why this slice exists

The Observation → SemanticUnitCandidate pipeline now enforces persistence provenance and epistemic boundaries. That does not establish extraction quality. Before connecting a model, the project needs a repeatable way to score candidate extraction, abstention, confidence calibration, and domain-specific regressions.

## Exact-match unit scoring

`evaluate_extraction_cases` compares each predicted candidate with annotated gold units using the exact tuple:

- `UnitKind`
- `canonical_key`
- ordered `role_bindings` as (role name, target reference) pairs

Role order is preserved because relation roles are not an unordered bag. Surface-form overlap alone is not accepted as semantic correctness. Missing canonical keys count as invalid false-positive predictions. Duplicate outputs are counted with multiset semantics rather than silently deduplicated.

The harness reports micro precision, recall and F1, TP/FP/FN, invalid predictions, and per-domain metrics.

## Abstention and selective coverage

A gold case with no expected units is an abstention-required case. The prediction explicitly states whether it abstained. The report separates abstention precision/recall/F1, abstention rate, and coverage. This prevents a system that emits nothing from appearing accurate merely because it avoids false positives.

## Confidence calibration

For emitted candidates with `extractor_confidence`, the harness treats exact-match correctness as a binary outcome and reports Brier score plus fixed-width expected calibration error (ECE). Missing confidence is counted and never imputed. Calibration statistics are descriptive; small sample counts and bin occupancy must be inspected. Confidence is not truth probability, source reliability, grounding confidence, or SROK ranking score.

## Evaluation protocol

1. Freeze gold annotations and split by document/source lineage, not random candidate rows, to prevent near-duplicate leakage.
2. Keep in-domain validation and held-out domain/OOD test sets separate.
3. Report micro and per-domain precision/recall/F1, abstention behavior, calibration, invalid output rate, and provenance-contract rejection rate.
4. Include adversarial, ambiguous, contradictory, partial-parse, and no-answer cases.
5. Compare deterministic baseline, model extractor, and model-plus-abstention policy on identical cases and fixed prompts/model versions.
6. Run multiple seeds where decoding or sampling is stochastic; publish confidence intervals or per-seed distributions.
7. Do not tune thresholds on the held-out test set.

## Limits

This harness does not establish correctness beyond the exact annotation schema. It does not implement semantic parsing, entity resolution, grounding, truth adjudication, E09 authorization, or lifecycle promotion. It does not measure model latency, token cost, memory, or KV cache. Those require separate benchmarks.
