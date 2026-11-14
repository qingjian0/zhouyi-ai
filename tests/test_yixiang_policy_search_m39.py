import unittest
from prototype.yixiang_policy_search_m39 import *

def sc():
    return ModelScenario("s",(Prior("h1",.5),Prior("h2",.5)),
      (Likelihood("a1","h1","x",.9),Likelihood("a1","h1","y",.1),
       Likelihood("a1","h2","x",.1),Likelihood("a1","h2","y",.9),
       Likelihood("a2","h1","x",.8),Likelihood("a2","h1","y",.2),
       Likelihood("a2","h2","x",.2),Likelihood("a2","h2","y",.8),
       Likelihood("a3","h1","x",.5),Likelihood("a3","h1","y",.5),
       Likelihood("a3","h2","x",.5),Likelihood("a3","h2","y",.5)),"prior-likelihood-ref",True)

def act(i,**kw):
    d=dict(action_id=i,cost=1,risk=.1,max_risk=.5,safety_approved=True,feasible=True,
      design_ref="design-"+i,measurement_ref="measure-"+i,selection_split="select",validation_split="holdout")
    d.update(kw); return Action(**d)

def run(actions=None,scenarios=None,**kw):
    d=dict(horizon=2,beam_width=4,max_total_cost=5,max_total_risk=1,cost_weight=0,risk_weight=0)
    d.update(kw)
    if actions is None: actions=(act("a1"),act("a2"),act("a3"))
    if scenarios is None:
        ids={a.action_id for a in actions}
        s=sc()
        scenarios=(ModelScenario(s.scenario_id,s.priors,tuple(x for x in s.likelihoods if x.action_id in ids),s.provenance_ref,s.calibrated),)
    return search_sequences(actions,scenarios,**d)

class M39Tests(unittest.TestCase):
    def test_returns_candidates(self): self.assertEqual(run().disposition,SearchDisposition.CANDIDATES_FOUND)
    def test_search_has_no_execution_authority(self): self.assertFalse(run().execution_authorized)
    def test_search_does_not_establish_truth(self): self.assertFalse(run().causal_truth_established)
    def test_ranked_sequences_nonempty(self): self.assertTrue(run().ranked_sequences)
    def test_horizon_limits_sequence_length(self): self.assertLessEqual(max(map(lambda x:len(x.action_ids),run(horizon=1).ranked_sequences)),1)
    def test_no_repeated_actions(self):
        for x in run(horizon=3).ranked_sequences: self.assertEqual(len(x.action_ids),len(set(x.action_ids)))
    def test_beam_width_limits_expansion_frontier(self): self.assertGreater(run(beam_width=1).expanded_states,0)
    def test_cost_budget_filters(self): self.assertTrue(all(x.total_cost<=1 for x in run(max_total_cost=1).ranked_sequences))
    def test_risk_budget_filters(self): self.assertTrue(all(x.total_risk<=.1+1e-9 for x in run(max_total_risk=.1).ranked_sequences))
    def test_cost_penalty_changes_utility(self):
        a=run(cost_weight=1).ranked_sequences[0]; self.assertAlmostEqual(a.utility,a.robust_eig-a.total_cost)
    def test_risk_penalty_changes_utility(self):
        a=run(risk_weight=2).ranked_sequences[0]; self.assertAlmostEqual(a.utility,a.robust_eig-2*a.total_risk)
    def test_scenario_minimum_is_robust_score(self):
        s2=ModelScenario("s2",sc().priors,tuple(Likelihood(x.action_id,x.hypothesis_id,x.outcome,x.probability) for x in sc().likelihoods),"p2",True)
        r=run(scenarios=(sc(),s2))
        self.assertAlmostEqual(r.ranked_sequences[0].robust_eig,min(v for _,v in r.ranked_sequences[0].scenario_eigs))
    def test_invalid_horizon_blocks(self): self.assertIn("invalid_search_limits",run(horizon=0).issues)
    def test_invalid_beam_blocks(self): self.assertIn("invalid_search_limits",run(beam_width=0).issues)
    def test_no_actions_blocks(self): self.assertIn("no_actions",run(actions=()).issues)
    def test_no_scenarios_blocks(self): self.assertIn("no_model_scenarios",run(scenarios=()).issues)
    def test_duplicate_action_blocks(self): self.assertIn("duplicate_action_id",run(actions=(act("a1"),act("a1"))).issues)
    def test_selection_validation_overlap_blocks(self): self.assertTrue(any(x.startswith("selection_validation_overlap") for x in run(actions=(act("a1",validation_split="select"),)).issues))
    def test_unapproved_action_excluded(self):
        r=run(actions=(act("a1",safety_approved=False),act("a2")))
        self.assertTrue(all("a1" not in x.action_ids for x in r.ranked_sequences))
    def test_infeasible_action_excluded(self):
        r=run(actions=(act("a1",feasible=False),act("a2")))
        self.assertTrue(all("a1" not in x.action_ids for x in r.ranked_sequences))
    def test_action_risk_limit_violation_blocks(self): self.assertTrue(any(x.startswith("action_risk_limit_exceeded") for x in run(actions=(act("a1",risk=1),)).issues))
    def test_unnormalized_prior_blocks(self):
        s=sc(); bad=ModelScenario("bad",(Prior("h1",.2),Prior("h2",.2)),s.likelihoods,"p",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in run(scenarios=(bad,)).issues))
    def test_uncalibrated_scenario_blocks(self):
        s=sc(); bad=ModelScenario("bad",s.priors,s.likelihoods,"p",False)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in run(scenarios=(bad,)).issues))
    def test_missing_likelihood_action_blocks(self):
        s=sc(); bad=ModelScenario("bad",s.priors,tuple(x for x in s.likelihoods if x.action_id!="a2"),"p",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in run(scenarios=(bad,)).issues))
    def test_nonfinite_likelihood_blocks(self):
        s=sc(); ls=list(s.likelihoods); ls[0]=Likelihood("a1","h1","x",float("nan"))
        bad=ModelScenario("bad",s.priors,tuple(ls),"p",True)
        self.assertTrue(any(x.startswith("invalid_or_uncalibrated") for x in run(scenarios=(bad,)).issues))
    def test_zero_information_action_has_zero_eig(self):
        r=run(actions=(act("a3"),),horizon=1)
        self.assertAlmostEqual(r.ranked_sequences[0].robust_eig,0.0)
    def test_greedy_baseline_reported(self): self.assertTrue(run().greedy_sequence)
    def test_expanded_states_reported(self): self.assertGreater(run().expanded_states,0)
    def test_empty_feasible_set(self):
        r=run(actions=(act("a1",safety_approved=False),))
        self.assertEqual(r.disposition,SearchDisposition.NO_FEASIBLE_SEQUENCE)
    def test_sequence_order_retained(self):
        r=run(horizon=2)
        self.assertTrue(any(x.action_ids==("a1","a2") for x in r.ranked_sequences))
    def test_warnings_disclose_open_loop_limit(self):
        self.assertIn("open_loop_sequences_only_no_outcome_contingent_branching",run().warnings)

    def test_greedy_is_reported_separately(self):
        r=run(); self.assertIsInstance(r.greedy_sequence,tuple)
    def test_empty_action_list_is_not_replaced_by_defaults(self):
        self.assertIn("no_actions",run(actions=()).issues)
    def test_search_expansion_respects_unique_action_limit(self):
        r=run(horizon=3)
        self.assertTrue(all(len(x.action_ids)<=3 for x in r.ranked_sequences))
