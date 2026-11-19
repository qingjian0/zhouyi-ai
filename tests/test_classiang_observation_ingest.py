import unittest

from prototype.classiang_engine import select_aspects, FeatureAtom
from prototype.classiang_observation_ingest import (
    RawFeatureClaim,
    RawObservationRecord,
    ingest_observation,
)


def record(*, scores=(), evidence_refs=("source:pump-1",)):
    source = "A pump transfers water."
    return RawObservationRecord(
        observation_id="obs-1",
        subject_id="pump-1",
        domain="mechanical",
        source_text=source,
        evidence_refs=evidence_refs,
        claims=(
            RawFeatureClaim(
                dimension="function",
                value="transfers-water",
                evidence_refs=("source:pump-1",),
                source_start=7,
                source_end=22,
                source_quote="transfers water",
                purpose_scores=scores,
            ),
        ),
    )


class ClassiangObservationIngestTests(unittest.TestCase):
    def test_ingests_claim_with_exact_source_span_and_provenance(self):
        result = ingest_observation(record())
        self.assertEqual(result.claim_count, 1)
        self.assertEqual(result.unscored_feature_count, 1)
        self.assertEqual(
            result.evidence_span_refs,
            ("source:pump-1#chars:7:22",),
        )
        feature = result.observation.features[0]
        self.assertEqual(feature.atom, FeatureAtom("function", "transfers-water"))
        self.assertEqual(feature.evidence_refs, result.evidence_span_refs)
        self.assertEqual(feature.purpose_scores, ())

    def test_explicit_relevance_is_preserved_but_never_invented(self):
        result = ingest_observation(record(scores=(("recognition", 0.8),)))
        self.assertEqual(result.unscored_feature_count, 0)
        selected = select_aspects(
            result.observation, purpose="recognition", min_relevance=0.5
        )
        self.assertEqual(
            selected.selected, (FeatureAtom("function", "transfers-water"),)
        )

    def test_unscored_claim_remains_unscored_for_task(self):
        result = ingest_observation(record())
        selected = select_aspects(result.observation, purpose="recognition")
        self.assertEqual(selected.selected, ())
        self.assertEqual(
            selected.unscored,
            (FeatureAtom("function", "transfers-water"),),
        )

    def test_rejects_quote_that_does_not_match_source_span(self):
        invalid = record()
        claim = invalid.claims[0]
        changed = RawFeatureClaim(
            dimension=claim.dimension,
            value=claim.value,
            evidence_refs=claim.evidence_refs,
            source_start=claim.source_start,
            source_end=claim.source_end,
            source_quote="moves water",
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            ingest_observation(RawObservationRecord(
                invalid.observation_id, invalid.subject_id, invalid.domain,
                invalid.source_text, invalid.evidence_refs, (changed,),
            ))

    def test_rejects_claim_without_source_evidence(self):
        invalid = record(evidence_refs=("different-source",))
        with self.assertRaisesRegex(ValueError, "unknown source evidence"):
            ingest_observation(invalid)

    def test_rejects_boolean_offsets(self):
        invalid = record()
        claim = invalid.claims[0]
        changed = RawFeatureClaim(
            claim.dimension, claim.value, claim.evidence_refs, True,
            claim.source_end, claim.source_quote,
        )
        with self.assertRaisesRegex(ValueError, "source_start must be an integer"):
            ingest_observation(RawObservationRecord(
                invalid.observation_id, invalid.subject_id, invalid.domain,
                invalid.source_text, invalid.evidence_refs, (changed,),
            ))


if __name__ == "__main__":
    unittest.main()
