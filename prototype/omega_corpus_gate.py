"""Export only reviewed, source-verified and rights-cleared classical-xiang records.

The exporter is intentionally fail-closed. It preserves provenance in a manifest
and emits a plain-text corpus only from records that pass every gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ALLOWED_LICENSES = {
    "public_domain", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0",
}
ALLOWED_SOURCE_TYPES = {"classical_text", "historical_commentary"}


def assess_record(record: dict) -> list[str]:
    failures = []
    if record.get("review_status") != "reviewed":
        failures.append("record_not_reviewed")
    if record.get("text_status") != "verified_against_witness":
        failures.append("text_not_verified_against_witness")
    if record.get("source_type") not in ALLOWED_SOURCE_TYPES:
        failures.append("source_type_not_eligible")
    claims = record.get("claims")
    if not isinstance(claims, list) or not claims:
        failures.append("claims_missing")
    elif any(c.get("review_status") != "reviewed" for c in claims):
        failures.append("claims_not_all_reviewed")
    rights = record.get("rights") or {}
    if rights.get("text_license") not in ALLOWED_LICENSES:
        failures.append("text_license_not_allowlisted")
    if rights.get("database_license") not in ALLOWED_LICENSES:
        failures.append("database_license_not_allowlisted")
    witness = record.get("witness") or {}
    if not witness.get("url") or not witness.get("witness_id"):
        failures.append("source_witness_incomplete")
    if not (record.get("text") or "").strip():
        failures.append("text_empty")
    return failures


def export_corpus(records: list[dict]) -> tuple[str, dict]:
    accepted = []
    rejected = []
    seen = set()
    for record in records:
        failures = assess_record(record)
        if failures:
            rejected.append({"record_id": record.get("record_id"), "reasons": failures})
            continue
        normalized = " ".join(record["text"].split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest in seen:
            rejected.append({"record_id": record["record_id"], "reasons": ["duplicate_text"]})
            continue
        seen.add(digest)
        accepted.append({
            "record_id": record["record_id"],
            "record_version": record.get("record_version"),
            "work": record.get("work", {}).get("title"),
            "period": record.get("period"),
            "source_type": record.get("source_type"),
            "witness_id": record["witness"]["witness_id"],
            "witness_url": record["witness"]["url"],
            "locator": record.get("locator"),
            "text": normalized,
            "claim_ids": [c["claim_id"] for c in record["claims"]],
            "text_license": record["rights"]["text_license"],
            "database_license": record["rights"]["database_license"],
            "text_sha256": digest,
        })
    corpus = "\n\n".join(item["text"] for item in accepted)
    manifest = {
        "format": "zhouyi-ai-reviewed-corpus-manifest-v1",
        "policy": {
            "record_review": "reviewed",
            "text_status": "verified_against_witness",
            "claim_review": "all claims reviewed",
            "source_types": sorted(ALLOWED_SOURCE_TYPES),
            "allowed_licenses": sorted(ALLOWED_LICENSES),
            "deduplication": "normalized exact-text SHA-256",
        },
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted,
        "rejected": rejected,
    }
    return corpus, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="classical-xiang corpus JSON array")
    parser.add_argument("--output", required=True, help="UTF-8 text corpus path")
    parser.add_argument("--manifest", required=True, help="provenance manifest JSON path")
    parser.add_argument("--require-nonempty", action="store_true")
    args = parser.parse_args()
    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("input must be a JSON array of records")
    corpus, manifest = export_corpus(records)
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(args.manifest).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if manifest["accepted_count"]:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(corpus + "\n", encoding="utf-8")
    elif args.require_nonempty:
        raise SystemExit(
            "No records passed review, witness, source-type and license gates; "
            "refusing to produce a training corpus."
        )
    print(json.dumps({
        "accepted_count": manifest["accepted_count"],
        "rejected_count": manifest["rejected_count"],
        "manifest": args.manifest,
        "corpus_written": bool(manifest["accepted_count"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
