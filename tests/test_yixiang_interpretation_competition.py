import unittest
from prototype.yixiang_interpretation_competition import *

def pos(pid, author, year, layer, framework, text_refs=("mozi-xiaoqu",), scholarship_refs=("scholarship",)):
    return InterpretationPosition(pid,author,"work",year,layer,framework,("效","辟","侔","援","推"),
        "Interpretive account of the seven terms.","Only the stated chapter and argumentative context.",
        text_refs,scholarship_refs,("This is an interpretation, not the base text.",))

class M16Tests(unittest.TestCase):
    def test_hu_shih_logical_taxonomy_and_tang_process_compete(self):
        case=InterpretationCase("M16","Seven dialectical terms",("mozi-xiaoqu",),(
            pos("hu","Hu Shih",1919,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.LOGICAL_TAXONOMY),
            pos("tang","Tang Chun-I",2004,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.DIALECTICAL_PROCESS)))
        result=assess_interpretation_competition(case)
        self.assertEqual(result.status,CompetitionStatus.COMPETING_FRAMEWORKS)
        self.assertIsNone(result.winner_position_id)
        self.assertFalse(result.interpretive_truth_established)
    def test_general_inference_framework_is_distinct_from_analogy_only(self):
        case=InterpretationCase("M16","What is tuilei?",("mozi-xiaoqu","mozi-jingxia"),(
            pos("analogy","Analogy-only scholar",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.UNIFIED_ANALOGY,("mozi-xiaoqu",)),
            pos("jin","Jin Rongdong",None,InterpretationSourceLayer.CONTEMPORARY_RESEARCH,InterpretiveFramework.GENERAL_INFERENCE,("mozi-jingxia",))))
        result=assess_interpretation_competition(case)
        self.assertEqual(result.status,CompetitionStatus.COMPETING_FRAMEWORKS)
        self.assertEqual(result.unique_textual_basis_refs,("mozi-jingxia","mozi-xiaoqu"))

    def test_ethical_practice_is_a_separate_interpretive_axis(self):
        case=InterpretationCase("M16","Tuilei in practice",("mozi-xiaoqu",),(
            pos("ethics","Li Wei",2016,InterpretationSourceLayer.CONTEMPORARY_RESEARCH,InterpretiveFramework.ETHICAL_PRACTICE),))
        self.assertEqual(assess_interpretation_competition(case).frameworks,(InterpretiveFramework.ETHICAL_PRACTICE,))

    def test_2024_unified_analogy_framework_is_preserved(self):
        case=InterpretationCase("M16","Seven dialectical terms",("mozi-xiaoqu",),(
            pos("zhou","Zhou Boqun",2024,InterpretationSourceLayer.CONTEMPORARY_RESEARCH,InterpretiveFramework.UNIFIED_ANALOGY),))
        self.assertEqual(assess_interpretation_competition(case).status,CompetitionStatus.SINGLE_POSITION)
    def test_multiple_positions_same_framework_not_false_competition(self):
        case=InterpretationCase("M16","case",("mozi-xiaoqu",),(
            pos("a","Author A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.LOGICAL_TAXONOMY),
            pos("b","Author B",2010,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.LOGICAL_TAXONOMY)))
        self.assertEqual(assess_interpretation_competition(case).status,CompetitionStatus.MULTIPLE_POSITIONS_SAME_FRAMEWORK)
    def test_empty_registry_is_explicit(self):
        case=InterpretationCase("M16","case",("mozi-xiaoqu",),())
        self.assertEqual(assess_interpretation_competition(case).status,CompetitionStatus.NO_RECORDED_POSITION)
    def test_primary_text_anchor_required(self):
        bad=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.OTHER,("wrong-ref",))
        with self.assertRaises(ValueError): assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(bad,)))
    def test_duplicate_position_rejected(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.OTHER)
        with self.assertRaises(ValueError): assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(a,a)))
    def test_missing_caveats_rejected(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.OTHER)
        bad=InterpretationPosition(a.position_id,a.author,a.work,a.publication_year,a.source_layer,a.framework,a.target_terms,a.interpretation,a.scope,a.textual_basis_refs,a.scholarship_refs,())
        with self.assertRaises(ValueError): assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(bad,)))
    def test_shared_textual_basis_is_not_independence(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.LOGICAL_TAXONOMY)
        b=pos("b","B",2010,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.DIALECTICAL_PROCESS)
        result=assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(a,b)))
        self.assertEqual(result.shared_textual_basis_refs,("mozi-xiaoqu",))
        self.assertFalse(result.independence_established)
    def test_unique_basis_refs_are_reported(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.LOGICAL_TAXONOMY,("mozi-xiaoqu","variant-a"))
        b=pos("b","B",2010,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.DIALECTICAL_PROCESS,("mozi-xiaoqu","variant-b"))
        result=assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu","variant-a","variant-b"),(a,b)))
        self.assertEqual(result.unique_textual_basis_refs,("variant-a","variant-b"))
    def test_unverified_preprint_year_can_remain_unknown(self):
        a=pos("preprint","Jin Rongdong",None,InterpretationSourceLayer.CONTEMPORARY_RESEARCH,InterpretiveFramework.GENERAL_INFERENCE)
        result=assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(a,)))
        self.assertEqual(result.status,CompetitionStatus.SINGLE_POSITION)

    def test_year_and_framework_types_validated(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.OTHER)
        bad=InterpretationPosition(a.position_id,a.author,a.work,True,a.source_layer,a.framework,a.target_terms,a.interpretation,a.scope,a.textual_basis_refs,a.scholarship_refs,a.caveats)
        with self.assertRaises(ValueError): assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(bad,)))
    def test_never_selects_winner_or_truth(self):
        a=pos("a","A",2000,InterpretationSourceLayer.POST_QING_SCHOLARSHIP,InterpretiveFramework.OTHER)
        result=assess_interpretation_competition(InterpretationCase("M16","case",("mozi-xiaoqu",),(a,)))
        self.assertIsNone(result.winner_position_id)
        self.assertFalse(result.interpretive_truth_established)
        self.assertEqual(result.adjudication,"not_performed")

if __name__=="__main__": unittest.main()
