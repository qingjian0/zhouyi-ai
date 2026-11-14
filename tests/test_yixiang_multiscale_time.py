import unittest
from prototype.yixiang_multiscale_time import (
    MultiScaleTimeline, TemporalEvent, TimeScale, compare_intervals,
)

def event(eid, scale="micro", clock="clock-A", start=0, end=1, parent=None):
    return TemporalEvent(eid, scale, clock, start, end, end,
        (f"evidence:{eid}",), parent)

class MultiScaleTimeTests(unittest.TestCase):
    def setUp(self):
        self.scales = {
            "macro": TimeScale("macro"),
            "meso": TimeScale("meso", "macro"),
            "micro": TimeScale("micro", "meso"),
        }

    def test_nested_events_require_ancestor_scale_and_containment(self):
        timeline = MultiScaleTimeline(self.scales, (
            event("whole", "macro", start=0, end=10),
            event("part", "meso", start=2, end=8, parent="whole"),
            event("detail", "micro", start=3, end=4, parent="part"),
        ))
        timeline.validate()

    def test_rejects_non_contained_child(self):
        timeline = MultiScaleTimeline(self.scales, (
            event("whole", "macro", start=0, end=5),
            event("part", "meso", start=2, end=8, parent="whole"),
        ))
        with self.assertRaises(ValueError):
            timeline.validate()

    def test_rejects_cross_clock_parent_without_calibration(self):
        timeline = MultiScaleTimeline(self.scales, (
            event("whole", "macro", "clock-A", 0, 10),
            event("part", "meso", "clock-B", 2, 8, "whole"),
        ))
        with self.assertRaises(ValueError):
            timeline.validate()

    def test_rejects_scale_cycle(self):
        scales = {"a": TimeScale("a", "b"), "b": TimeScale("b", "a")}
        with self.assertRaises(ValueError):
            MultiScaleTimeline(scales, ()).validate()

    def test_interval_relations(self):
        a = event("a", start=0, end=2)
        b = event("b", start=2, end=4)
        c = event("c", start=1, end=3)
        self.assertEqual(compare_intervals(a,b).relation, "MEETS")
        self.assertEqual(compare_intervals(a,c).relation, "OVERLAPS")

    def test_different_clocks_are_not_compared(self):
        a = event("a", clock="seconds", start=0, end=2)
        b = event("b", clock="frames", start=0, end=2)
        result = compare_intervals(a,b)
        self.assertFalse(result.comparable)
        self.assertEqual(result.relation, "INCOMPARABLE")

if __name__ == "__main__":
    unittest.main()
