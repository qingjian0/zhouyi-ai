# M2 semantic extraction evaluation contract v1

Status: executable evaluation harness; no extractor or trained model is included.

## Exact-match unit scoring

`evaluate_extraction_cases` compares predicted candidates with adjudicated gold units using the exact tuple: `UnitKind`, `canonical_key`, and ordered `role_bindings`. Role order is semantic and is not normalized away. Surface-form overlap is not treated as semantic correctness. Missing canonical keys count as invalid false-positive predictions; duplicate outputs use multiset semantics.

The report includes micro precision/recall/F1, TP/FP/FN, invalid predictions, and per-domain metrics.

## Abstention and selective coverage

A gold case with no expected units is an abstention-required case. Predictions explicitly declare abstention. The report separates abstention precision/recall/F1, abstention rate, and coverage, preventing an always-empty extractor from appearing accurate.

## Confidence calibration

For candidates with `extractor_confidence`, exact-match correctness is the binary outcome. The harness reports Brier score and fixed-width expected calibration error (ECE). Missing confidence is counted, never imputed. Calibration statistics are descriptive; sample counts and bin occupancy must be inspected. Extractor confidence is not truth probability, source reliability, grounding confidence, or ranking score.

## Evaluation protocol

1. Freeze gold annotations and split by source document/lineage before candidate expansion.
2. Keep in-domain validation and held-out domain/OOD test sets separate.
3. Report micro and per-domain metrics, abstention, calibration, invalid output rate, and provenance rejection rate.
4. Include adversarial, ambiguous, contradictory, partial-parse, and no-answer cases.
5. Compare deterministic baselines, model extractors, and abstention policies on identical cases and fixed model versions.
6. Report per-seed distributions or confidence intervals for stochastic systems.
7. Never tune thresholds on the held-out test set.

## Limits

This harness does not implement semantic parsing, entity resolution, grounding, truth adjudication, authorization, or model training. It does not establish correctness beyond the annotation schema and does not measure latency, token cost, memory, or KV cache. Those require separate tests and benchmarks.
