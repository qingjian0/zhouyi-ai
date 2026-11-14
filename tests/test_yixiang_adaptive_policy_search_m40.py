import unittest
from prototype.yixiang_adaptive_policy_search_m40 import *

def fixture():
    ps=(Prior("h1",.5),Prior("h2",.5))
    ls=[]
    for a,q in (("a1",.9),("a2",.8),("a3",.5)):
        ls.extend((Likelihood(a,"h1","x",q),Likelihood(a,"h1","y",1-q),
                   Likelihood(a,"h2","x",1-q),Likelihood(a,"h2","y",q)))
    s=Scenario("s1",ps,tuple(ls),"source")
    acts=tuple(Action(a,0.01,0.01,.5,True,True,"d-"+a,"m-"+a) for a in ("a1","a2","a3"))
    return acts,(s,)

class M40Tests(unittest.TestCase):
    def test_returns_policy(self):
        a,s=fixture(); self.assertIn(search_policy(a,s).disposition,("candidate_policy","stop_policy"))
    def test_outcome_contingent_root(self):
        a,s=fixture(); r=search_policy(a,s,horizon=2)
        if r.root.action_id: self.assertEqual({x for x,_ in r.root.branches},{"x","y"})
    def test_branch_children_are_policy_nodes(self):
        a,s=fixture(); r=search_policy(a,s,horizon=2)
        if r.root.action_id: self.assertTrue(all(isinstance(n,PolicyNode) for _,n in r.root.branches))
    def test_horizon_zero_stops(self):
        a,s=fixture(); self.assertIsNone(search_policy(a,s,horizon=0).root.action_id)
    def test_no_execution_authority(self):
        a,s=fixture(); self.assertFalse(search_policy(a,s).execution_authorized)
    def test_no_truth_claim(self):
        a,s=fixture(); self.assertFalse(search_policy(a,s).causal_truth_established)
    def test_node_budget_warning(self):
        a,s=fixture(); r=search_policy(a,s,horizon=5,max_nodes=1)
        self.assertIn("node_budget_exhausted_search_is_incomplete",r.warnings)
    def test_unapproved_action_excluded(self):
        a,s=fixture(); a=(Action("bad",0,0,1,False,True,"d","m"),)+a
        r=search_policy(a,s)
        self.assertIn("unapproved_or_infeasible_actions_excluded",r.warnings)
        self.assertNotEqual(r.root.action_id,"bad")
    def test_no_actions_blocked(self):
        _,s=fixture(); self.assertEqual(search_policy((),s).disposition,"blocked")
    def test_no_scenarios_blocked(self):
        a,_=fixture(); self.assertEqual(search_policy(a,()).disposition,"blocked")
    def test_duplicate_action_blocked(self):
        a,s=fixture(); self.assertIn("duplicate_action_id",search_policy(a+(a[0],),s).issues)
    def test_unnormalized_prior_blocked(self):
        a,s=fixture(); bad=Scenario("bad",(Prior("h1",.2),Prior("h2",.2)),s[0].likelihoods,"p")
        self.assertTrue(any(x.startswith("invalid_prior") for x in search_policy(a,(bad,)).issues))
    def test_missing_likelihood_blocked(self):
        a,s=fixture(); bad=Scenario("bad",s[0].priors,tuple(x for x in s[0].likelihoods if x.action!="a2"),"p")
        self.assertTrue(any(x.startswith("invalid_likelihood") for x in search_policy(a,(bad,)).issues))
    def test_uncalibrated_scenario_blocked(self):
        a,s=fixture(); bad=Scenario("bad",s[0].priors,s[0].likelihoods,"p",False)
        self.assertIn("invalid_scenario:bad",search_policy(a,(bad,)).issues)
    def test_bad_action_risk_blocked(self):
        a,s=fixture(); bad=(Action("bad",0,2,1,True,True,"d","m"),)
        self.assertTrue(any(x.startswith("action_risk_limit") for x in search_policy(bad,s).issues))
    def test_cost_budget_blocks_expensive(self):
        a,s=fixture(); expensive=(Action("exp",10,0,20,True,True,"d","m"),)
        r=search_policy(expensive,s,max_total_cost=1)
        self.assertIsNone(r.root.action_id)
    def test_terminal_values_bounded(self):
        a,s=fixture(); r=search_policy(a,s)
        self.assertTrue(all(0<=v<=1 for _,v in r.scenario_values))
    def test_scenario_robust_value_is_minimum(self):
        a,s=fixture(); r=search_policy(a,s)
        self.assertAlmostEqual(r.robust_value,min(v for _,v in r.scenario_values))
    def test_actions_not_repeated_on_path(self):
        a,s=fixture(); r=search_policy(a,s,horizon=3)
        def walk(n,path=()):
            if n.action_id:
                self.assertNotIn(n.action_id,path)
                for _,child in n.branches: walk(child,path+(n.action_id,))
        walk(r.root)
    def test_shared_policy_warning(self):
        a,s=fixture(); self.assertIn("shared_policy_uses_observable_outcomes_not_hidden_scenario_identity",search_policy(a,s).warnings)
