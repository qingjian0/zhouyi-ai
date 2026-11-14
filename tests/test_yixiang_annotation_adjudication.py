import unittest
from prototype.yixiang_annotation_adjudication import *

def source(status="critical_edition"):
    return SourceVerification(status,"mozi-xiaoqu","critical-edition-1","witness-a","卷十一/小取/段3","白马，马也。",("scan:page-11",),("collator-1",),"影印页与转录逐字核对")
def annotation(reviewer="reviewer-a", decision="accept", **changes):
    values=dict(reviewer_id=reviewer,decision=decision,claim="白马属于马类。",text_layer="main_text",shared_basis=("category-membership",) if decision=="accept" else (),non_shared_basis=(),scope_conditions=(),required_invariants=("predicate-preservation",),known_counterexamples=(),causal_status="unknown",evidence_refs=("passage:3",),rationale="依据所引文本与上下文作出标注。")
    values.update(changes)
    return IndependentAnnotation(**values)
def adjudication(decision="accept", adjudicator="adjudicator-c", **changes):
    values=dict(decision=decision,adjudicator_id=adjudicator,rationale="经复核原文、异文与两份独立标注，形成最终裁决。",evidence_refs=("adjudication:record-1",),claim="白马属于马类。",text_layer="main_text",relation_families=("structural",),shared_basis=("category-membership",) if decision=="accept" else (),non_shared_basis=(),scope_conditions=("同一谓词适用范围",) if decision=="conditional" else (),required_invariants=("predicate-preservation",),known_counterexamples=(),causal_status="unknown")
    values.update(changes)
    return FinalAdjudication(**values)
def packet(**changes):
    values=dict(case_id="case-1",claim_kind="taxonomic_similarity",independence_group="work:mozi-xiaoqu",source=source(),annotations=(annotation(),annotation("reviewer-b")),adjudication=None)
    values.update(changes)
    return ReviewPacket(**values)

class M19Tests(unittest.TestCase):
    def test_two_agreeing_reviews_need_explicit_adjudication(self):
        self.assertEqual(assess_review_packet(packet()).status,ReviewStatus.READY_FOR_ADJUDICATION)
    def test_disagreement_is_preserved(self):
        p=packet(annotations=(annotation(),annotation("reviewer-b",decision="reject",shared_basis=())))
        result=assess_review_packet(p)
        self.assertEqual(result.status,ReviewStatus.REVIEWER_CONFLICT)
        self.assertIn("decision",result.disagreement_fields)
    def test_source_unverified_blocks_gold(self):
        result=assess_review_packet(packet(source=source("unverified_transcription"),adjudication=adjudication()))
        self.assertEqual(result.status,ReviewStatus.SOURCE_UNVERIFIED)
        self.assertFalse(result.gold_eligible)
    def test_two_reviewers_and_final_adjudicator_enable_export(self):
        p=packet(adjudication=adjudication())
        case=to_benchmark_case(p,split_group="test")
        self.assertEqual(case["label_status"],"adjudicated")
        self.assertEqual(len(case["reviewers"]),2)
        self.assertEqual(case["gold_decision"],"accept")
    def test_export_rejects_missing_adjudication(self):
        with self.assertRaises(ValueError): to_benchmark_case(packet(),split_group="test")
    def test_export_rejects_exploratory_split(self):
        with self.assertRaises(ValueError): to_benchmark_case(packet(adjudication=adjudication()),split_group="exploratory")
    def test_adjudicator_must_be_distinct(self):
        p=packet(adjudication=adjudication(adjudicator="reviewer-a"))
        with self.assertRaises(ValueError): assess_review_packet(p)
    def test_duplicate_reviewer_ids_rejected(self):
        with self.assertRaises(ValueError): assess_review_packet(packet(annotations=(annotation(),annotation("reviewer-a"))))
    def test_fewer_than_two_reviewers_is_insufficient(self):
        result=assess_review_packet(packet(annotations=(annotation(),)))
        self.assertEqual(result.status,ReviewStatus.INSUFFICIENT_REVIEWS)
    def test_verified_source_requires_verification_evidence(self):
        bad=source()
        bad=SourceVerification(bad.source_status,bad.work_id,bad.edition_id,bad.witness_id,bad.locator,bad.transcription,(),bad.verified_by,bad.verification_note)
        with self.assertRaises(ValueError): assess_review_packet(packet(source=bad))
    def test_source_verifier_cannot_be_reviewer(self):
        s=source()
        s=SourceVerification(s.source_status,s.work_id,s.edition_id,s.witness_id,s.locator,s.transcription,s.verification_refs,("reviewer-a",),s.verification_note)
        result=assess_review_packet(packet(source=s))
        self.assertIn("source_verifier_overlaps_reviewer",result.blockers)
    def test_accept_requires_shared_basis(self):
        with self.assertRaises(ValueError): assess_review_packet(packet(annotations=(annotation(shared_basis=()),annotation("reviewer-b"))))
    def test_conditional_requires_scope(self):
        with self.assertRaises(ValueError): assess_review_packet(packet(annotations=(annotation(decision="conditional",scope_conditions=()),annotation("reviewer-b"))))
    def test_final_abstain_can_be_adjudicated(self):
        p=packet(adjudication=adjudication(decision="abstain"))
        case=to_benchmark_case(p,split_group="holdout")
        self.assertEqual(case["gold_decision"],"abstain")
    def test_reviewer_disagreement_can_be_resolved_by_separate_adjudicator(self):
        p=packet(annotations=(annotation(),annotation("reviewer-b",decision="reject",shared_basis=())),adjudication=adjudication(decision="conditional"))
        self.assertTrue(assess_review_packet(p).gold_eligible)
    def test_no_auto_gold_from_unanimity(self):
        result=assess_review_packet(packet())
        self.assertFalse(result.gold_eligible)
    def test_evidence_references_are_combined_in_export(self):
        case=to_benchmark_case(packet(adjudication=adjudication()),split_group="dev")
        self.assertIn("scan:page-11",case["evidence_refs"])
        self.assertIn("adjudication:record-1",case["evidence_refs"])
        self.assertEqual(case["target_claim"],"白马属于马类。")
        self.assertEqual(case["relation_families"],["structural"])
    def test_missing_source_locator_rejected(self):
        s=source()
        bad=SourceVerification(s.source_status,s.work_id,s.edition_id,s.witness_id,"",s.transcription,s.verification_refs,s.verified_by,s.verification_note)
        with self.assertRaises(ValueError): assess_review_packet(packet(source=bad))
    def test_duplicate_evidence_refs_rejected(self):
        a=annotation(evidence_refs=("same","same"))
        with self.assertRaises(ValueError): assess_review_packet(packet(annotations=(a,annotation("reviewer-b"))))

    def test_disagreement_export_uses_final_adjudicator_content(self):
        p=packet(annotations=(annotation(),annotation("reviewer-b",decision="reject",shared_basis=())),adjudication=adjudication(decision="conditional",shared_basis=(),scope_conditions=("仅在类别谓词保持时",),claim="仅在限定条件下可作类推。",relation_families=("structural","functional")))
        case=to_benchmark_case(p,split_group="test")
        self.assertEqual(case["target_claim"],"仅在限定条件下可作类推。")
        self.assertEqual(case["gold_decision"],"conditional")
        self.assertEqual(case["scope_conditions"],["仅在类别谓词保持时"])
        self.assertEqual(case["relation_families"],["structural","functional"])

    def test_export_runs_m8_validation(self):
        p=packet(adjudication=adjudication())
        case=to_benchmark_case(p,split_group="test")
        self.assertEqual(case["source_status"],"critical_edition")
        bad=packet(claim_kind="not-an-m8-claim-kind",adjudication=adjudication())
        with self.assertRaises(ValueError): to_benchmark_case(bad,split_group="test")

if __name__=="__main__": unittest.main()
