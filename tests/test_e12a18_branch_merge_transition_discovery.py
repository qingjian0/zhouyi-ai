import unittest
from prototype.e12a18_branch_merge_transition_discovery import (
    Config, Edge, Node, Observation, discover,
)


def fork_rows():
    rows=[]
    for i in range(48):
        yes=i%2==0
        nodes=(Node("c","context"),Node("a","signal"),Node("b","resource"))
        edges=((Edge("c","activates","a","cold->warm"),
                Edge("c","recruits","b","idle->active")) if yes else
               (Edge("a","blocks","c"),))
        rows.append(Observation(f"fork-{i:03}",nodes,edges,"success" if yes else "fail"))
    return rows


def join_rows():
    rows=[]
    for i in range(48):
        yes=i%2==0
        nodes=(Node("a","signal"),Node("b","resource"),Node("c","decision"))
        edges=((Edge("a","supports","c"),Edge("b","confirms","c")) if yes else
               (Edge("c","rejects","a"),))
        rows.append(Observation(f"join-{i:03}",nodes,edges,"pass" if yes else "fail"))
    return rows


class BranchMergeTransitionTests(unittest.TestCase):
    def test_discovers_fork_with_transition_labels(self):
        result=discover(fork_rows(),config=Config(max_complexity_bits=40))
        motif=next(m for m in result.motifs if m.shape=="FORK" and
                   m.center_type=="context" and
                   ("activates","signal","cold->warm") in m.arms and
                   ("recruits","resource","idle->active") in m.arms)
        self.assertGreater(motif.mdl_gain_bits,0)

    def test_discovers_join_structure(self):
        result=discover(join_rows(),config=Config(max_complexity_bits=40))
        self.assertTrue(any(m.shape=="JOIN" and m.center_type=="decision"
            for m in result.motifs))

    def test_direction_is_preserved(self):
        result=discover(fork_rows(),config=Config(max_complexity_bits=40))
        self.assertFalse(any(m.shape=="JOIN" and m.center_type=="context"
            for m in result.motifs))

    def test_random_uninformative_structure_not_admitted(self):
        rows=[]
        for i in range(40):
            nodes=(Node("c","C"),Node("a","A"),Node("b","B"))
            edges=(Edge("c","r1","a"),Edge("c","r2","b"))
            rows.append(Observation(f"random-{i:03}",nodes,edges,
                "yes" if i%2 else "no"))
        self.assertEqual(discover(rows,config=Config(max_complexity_bits=40)).motifs,())

    def test_candidate_budget_is_deterministic(self):
        cfg=Config(max_candidates=1)
        a,b=discover(fork_rows(),config=cfg),discover(fork_rows(),config=cfg)
        self.assertEqual(a,b)
        self.assertEqual(a.generated_candidate_count,1)
        self.assertTrue(a.truncated)

    def test_invalid_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            Observation("bad",(Node("a","A"),),(Edge("a","r","missing"),),"x")

    def test_duplicate_observation_ids_rejected(self):
        rows=fork_rows()
        with self.assertRaises(ValueError):
            discover(rows+[rows[0]])

    def test_complexity_budget_blocks_discovery(self):
        self.assertEqual(discover(fork_rows(),
            config=Config(max_complexity_bits=1)).motifs,())


if __name__=="__main__":
    unittest.main()
