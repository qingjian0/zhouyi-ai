import unittest
from prototype.yixiang_situated import SituatedRelation, YixiangSituation
from prototype.yixiang_trajectory import align_trajectories

def snap(sid, step, names, *, value="active", position="middle", stage="growth"):
    a, b = names
    return YixiangSituation(sid, "example", step, position, stage,
        {a: value, b: "resource"},
        (SituatedRelation("supports", (("agent", a), ("object", b))),),
        {"season": "spring"}, (f"source:{sid}",))

class TrajectoryAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {"a": "x", "b": "y"}
        self.source = (snap("s1",1,("a","b")),
            snap("s2",2,("a","b"),value="resting"),
            snap("s3",3,("a","b"),value="active",stage="mature"))
        self.target = (snap("t1",10,("x","y")),
            snap("t2",20,("x","y"),value="unmatched"),
            snap("t3",30,("x","y"),value="resting"),
            snap("t4",40,("x","y"),value="active",stage="mature"))

    def test_ordered_alignment_allows_gaps(self):
        r=align_trajectories(self.source,self.target,entity_mapping=self.mapping,
            required_context=("season",),min_source_coverage=1.0,min_target_coverage=.75)
        self.assertTrue(r.accepted)
        self.assertEqual(r.matched_pairs,((0,0),(1,2),(2,3)))
        self.assertEqual(r.skipped_target,(1,))

    def test_rejects_reversal(self):
        # Reverse the semantic sequence while keeping timestamps increasing.
        target=(snap("r1",10,("x","y"),value="active",stage="mature"),
            snap("r2",20,("x","y"),value="resting"),
            snap("r3",30,("x","y"),value="active"))
        r=align_trajectories(self.source,target,entity_mapping=self.mapping,
            required_context=("season",),min_source_coverage=1.0,min_target_coverage=1.0,require_same_stage=True)
        self.assertFalse(r.accepted)
        self.assertIn("SOURCE_COVERAGE_BELOW_THRESHOLD",r.reason_codes)

    def test_coverage_threshold_explicit(self):
        r=align_trajectories(self.source,self.target,entity_mapping=self.mapping,
            required_context=("season",),min_source_coverage=1.0,min_target_coverage=1.0)
        self.assertFalse(r.accepted)
        self.assertIn("TARGET_COVERAGE_BELOW_THRESHOLD",r.reason_codes)

    def test_steps_must_increase(self):
        invalid=(self.source[0],snap("s2",1,("a","b")))
        with self.assertRaises(ValueError):
            align_trajectories(invalid,self.target,entity_mapping=self.mapping,
                required_context=("season",))

if __name__ == "__main__":
    unittest.main()
