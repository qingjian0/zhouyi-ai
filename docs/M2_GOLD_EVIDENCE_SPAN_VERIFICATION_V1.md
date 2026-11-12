# M2 gold evidence span verification v1

Status: executable verification adapter using the existing read-only M1 SQLite EvidenceRef resolver.

## Verification path

1. Resolve every EvidenceRef through `SQLiteEvidenceRefResolver`.
2. Require the resolver to return the exact requested reference.
3. Validate the resolved UTF-8 byte length and full-chunk SHA-256 against EvidenceRef.
4. Convert each absolute gold span offset into chunk-local byte offsets.
5. Hash the exact byte slice and compare it with the gold span SHA-256.
6. Require verified spans to cover every positive gold unit.
7. Emit a deterministic local verification receipt containing the record digest, resolved references, span count, unit count, and verification digest. The receipt contains no source text.

No-answer cases have zero gold spans, but their EvidenceRefs are still resolved and integrity-checked. This prevents an empty annotation from bypassing source integrity checks.

## Memory behavior

The verifier processes one EvidenceRef at a time and discards the resolved chunk bytes before moving to the next reference. Working memory is therefore bounded by the largest referenced chunk plus the record's span metadata; it does not retain all source chunks in parallel.

## Trust boundary

This verifies that the annotation's claimed byte spans match the exact immutable M1 bytes addressed by their EvidenceRefs. It does not prove that the semantic label is correct, that the annotator interpreted the span correctly, or that the source itself is truthful. Annotation adjudication and E09 authorization remain separate.

The verification receipt is a local deterministic integrity result, not a cryptographic signature or remote attestation. A caller must not treat it as an E09 authorization receipt.
