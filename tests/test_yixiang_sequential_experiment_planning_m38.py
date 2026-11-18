import unittest
from prototype.yixiang_sequential_experiment_planning_m38 import *

def scenario():
    priors=(Prior("h1",.5),Prior("h2",.5))
    likes=(Likelihood("a1","h1","a",.9),Likelihood("a1","h1","b",.1),
           Likelihood("a1","h2","a",.1),Likelihood("a1","h2","b",.9))
    return ModelScenario("s1",priors,likes,"model-ref",True)

def action(aid="a1",**kw):
    d=dict(action_id=aid,cost=1,risk=.1,max_risk=.5,safety_review=Review.APPROVED,
           feasible=True,design_ref="d",measurement_ref="m",selection_split="select",
           validation_split="holdout")
    d.update(kw); return ExperimentAction(**d)

def policy(**kw):
    d=dict(policy_id="p1",root_node_id="n1",max_steps=2,max_total_cost=5,max_total_risk=1,
           min_robust_eig=.01,nodes=(PlanNode("n1","a1",(OutcomeBranch("a",stop=True),
           OutcomeBranch("b",stop=True))),))
    d.update(kw); return SequentialPolicy(**d)

def audit(p=None,acts=None,scens=None):
    return audit_policy(policy() if p is None else p,
                        (action(),) if acts is None else acts,
                        (scenario(),) if scens is None else scens)

class M38Tests(unittest.TestCase):
    def test_valid_policy_review(self): self.assertEqual(audit().disposition,Disposition.ROBUST_POLICY_REVIEW)
    def test_eig_positive(self): self.assertGreater(audit().robust_min_eig,0)
    def test_no_execution_authorized(self): self.assertFalse(audit().execution_authorized)
    def test_no_truth_claim(self): self.assertFalse(audit().causal_truth_established)
    def test_missing_policy_id_blocks(self): self.assertIn("missing_policy_identity",audit(policy(policy_id="")).issues)
    def test_missing_root_blocks(self): self.assertIn("missing_root_node",audit(policy(root_node_id="x")).issues)
    def test_empty_scenarios_blocks(self): self.assertIn("no_model_scenarios",audit(scens=()).issues)
    def test_uncalibrated_scenario_blocks(self): self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(ModelScenario("s",scenario().priors,scenario().likelihoods,"r",False),)).issues))
    def test_missing_provenance_blocks(self): self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(ModelScenario("s",scenario().priors,scenario().likelihoods,"",True),)).issues))
    def test_prior_not_normalized_blocks(self):
        s=scenario(); bad=ModelScenario("s",(Prior("h1",.2),Prior("h2",.2)),s.likelihoods,"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_negative_prior_blocks(self):
        s=scenario(); bad=ModelScenario("s",(Prior("h1",-1),Prior("h2",2)),s.likelihoods,"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_single_hypothesis_blocks(self):
        s=scenario(); bad=ModelScenario("s",(Prior("h1",1),),(), "r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_duplicate_prior_blocks(self):
        s=scenario(); bad=ModelScenario("s",(Prior("h1",.5),Prior("h1",.5)),s.likelihoods,"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_likelihood_out_of_range_blocks(self):
        s=scenario(); bad=ModelScenario("s",s.priors,(Likelihood("a1","h1","a",2),), "r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_likelihoods_must_sum_to_one(self):
        s=scenario(); bad=ModelScenario("s",s.priors,(Likelihood("a1","h1","a",.5),Likelihood("a1","h2","a",1)), "r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_unknown_hypothesis_likelihood_blocks(self):
        s=scenario(); bad=ModelScenario("s",s.priors,s.likelihoods+(Likelihood("a1","h3","a",1),),"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_duplicate_likelihood_blocks(self):
        s=scenario(); bad=ModelScenario("s",s.priors,s.likelihoods+(Likelihood("a1","h1","a",.1),),"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_duplicate_action_blocks(self): self.assertIn("duplicate_action_id",audit(acts=(action(),action())).issues)
    def test_duplicate_node_blocks(self):
        p=policy(nodes=(policy().nodes[0],policy().nodes[0]))
        self.assertIn("duplicate_node_id",audit(p).issues)
    def test_unknown_action_blocks(self):
        p=policy(nodes=(PlanNode("n1","missing",(OutcomeBranch("a",stop=True),)),))
        self.assertTrue(any(x.startswith("unknown_action") for x in audit(p).issues))
    def test_empty_branches_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",()),))
        self.assertTrue(any(x.startswith("node_without_branches") for x in audit(p).issues))
    def test_duplicate_outcome_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a",stop=True),OutcomeBranch("a",stop=True))),))
        self.assertTrue(any(x.startswith("duplicate_outcome_branch") for x in audit(p).issues))
    def test_invalid_branch_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a","missing"),)),))
        self.assertTrue(any(x.startswith("invalid_branch") for x in audit(p).issues))
    def test_stop_with_child_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a","n2",True),)),PlanNode("n2","a1",(OutcomeBranch("x",stop=True),))))
        self.assertTrue(any(x.startswith("invalid_branch") for x in audit(p).issues))
    def test_cycle_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a","n1"),)),))
        self.assertTrue(any(x.startswith("policy_cycle") for x in audit(p).issues))
    def test_max_steps_blocks(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a","n2"),)),PlanNode("n2","a1",(OutcomeBranch("a",stop=True),))),max_steps=1)
        self.assertTrue(any(x.startswith("policy_exceeds_max_steps") for x in audit(p).issues))
    def test_negative_limits_block(self): self.assertTrue(any(x.startswith("invalid_policy_limits") for x in audit(policy(max_total_cost=-1)).issues))
    def test_selection_validation_overlap_blocks(self): self.assertTrue(any(x.startswith("selection_validation_overlap") for x in audit(acts=(action(validation_split="select"),)).issues))
    def test_negative_action_cost_blocks(self): self.assertTrue(any(x.startswith("negative_cost_or_risk") for x in audit(acts=(action(cost=-1),)).issues))
    def test_unapproved_action_blocks(self): self.assertTrue(any(x.startswith("policy_uses_unapproved_action") for x in audit(acts=(action(safety_review=Review.PENDING),)).issues))
    def test_infeasible_action_blocks(self): self.assertTrue(any(x.startswith("policy_uses_unapproved_action") for x in audit(acts=(action(feasible=False),)).issues))
    def test_action_risk_limit_blocks(self): self.assertTrue(any(x.startswith("policy_uses_unapproved_action") for x in audit(acts=(action(risk=.8),)).issues))
    def test_cost_budget_blocks(self): self.assertTrue(any(x.startswith("total_cost_exceeded") for x in audit(policy(max_total_cost=.5)).issues))
    def test_risk_budget_blocks(self): self.assertTrue(any(x.startswith("path_risk_exceeded") for x in audit(policy(max_total_risk=.05)).issues))
    def test_min_robust_eig_marks_fragile(self): self.assertEqual(audit(policy(min_robust_eig=2)).disposition,Disposition.FRAGILE_POLICY)
    def test_uninformative_policy_flagged(self):
        s=ModelScenario("s",(Prior("h1",.5),Prior("h2",.5)),
          (Likelihood("a1","h1","a",.5),Likelihood("a1","h1","b",.5),Likelihood("a1","h2","a",.5),Likelihood("a1","h2","b",.5)),"r",True)
        self.assertEqual(audit(scens=(s,)).disposition,Disposition.NO_INFORMATION_GAIN)
    def test_robust_minimum_across_scenarios(self):
        s2=ModelScenario("s2",(Prior("h1",.5),Prior("h2",.5)),
          (Likelihood("a1","h1","a",.6),Likelihood("a1","h1","b",.4),Likelihood("a1","h2","a",.4),Likelihood("a1","h2","b",.6)),"r2",True)
        r=audit(scens=(scenario(),s2)); self.assertAlmostEqual(r.robust_min_eig,min(x.expected_information_gain for x in r.scenario_scores))
    def test_scenario_scores_are_per_model(self): self.assertEqual(len(audit(scens=(scenario(),scenario())) .scenario_scores),2)
    def test_validation_holdout_warning(self): self.assertIn("validation_split_must_remain_unseen_until_final_evaluation",audit().warnings)

    def test_action_specific_likelihoods_required(self):
        s=scenario()
        bad=ModelScenario("s",s.priors,tuple(Likelihood("other",x.hypothesis_id,x.outcome,x.probability) for x in s.likelihoods),"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_branch_must_cover_all_declared_outcomes(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a",stop=True),)),))
        self.assertTrue(any(x.startswith("branch_outcome_coverage_mismatch") for x in audit(p).issues))
    def test_two_step_conditional_policy_evaluates(self):
        s=scenario()
        likes=s.likelihoods+(
          Likelihood("a2","h1","c",.9),Likelihood("a2","h1","d",.1),
          Likelihood("a2","h2","c",.2),Likelihood("a2","h2","d",.8))
        s2=ModelScenario("s2",s.priors,likes,"model-ref",True)
        p=policy(nodes=(
          PlanNode("n1","a1",(OutcomeBranch("a","n2"),OutcomeBranch("b",stop=True))),
          PlanNode("n2","a2",(OutcomeBranch("c",stop=True),OutcomeBranch("d",stop=True)))))
        r=audit(p,acts=(action("a1"),action("a2")),scens=(s2,))
        self.assertEqual(r.disposition,Disposition.ROBUST_POLICY_REVIEW)
        self.assertGreater(r.scenario_scores[0].terminal_paths,2)

    def test_unknown_branch_outcome_blocks_without_crashing(self):
        p=policy(nodes=(PlanNode("n1","a1",(OutcomeBranch("a",stop=True),OutcomeBranch("z",stop=True))),))
        self.assertTrue(any(x.startswith("branch_has_no_likelihood") for x in audit(p).issues))

    def test_nan_prior_probability_blocks(self):
        s=scenario(); bad=ModelScenario("s",(Prior("h1",float("nan")),Prior("h2",.5)),s.likelihoods,"r",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in audit(scens=(bad,)).issues))
    def test_nan_action_cost_blocks(self):
        self.assertTrue(any(x.startswith("negative_cost_or_risk") for x in audit(acts=(action(cost=float("nan")),)).issues))
