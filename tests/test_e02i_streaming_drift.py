import unittest

from prototype.e02i_streaming_drift import run_episode


class E02IStreamingDriftTests(unittest.TestCase):
    def test_transient_noise_does_not_trigger_permanent_forgetting(self):
        result = run_episode(1201)
        self.assertTrue(result["transient_noise_did_not_prune"])
        self.assertTrue(result["initial_concept_created"])

    def test_persistent_structural_shift_replaces_old_relation(self):
        result = run_episode(1202)
        self.assertTrue(result["persistent_shift_pruned_old"])
        self.assertTrue(result["new_concept_active"])

    def test_stream_records_each_window_and_lifecycle_event(self):
        result = run_episode(1203)
        self.assertEqual(len(result["windows"]), 9)
        self.assertTrue(any(e["op"] == "CREATE" for e in result["events"]))
        self.assertTrue(any(e["op"] == "PRUNE" for e in result["events"]))


if __name__ == "__main__":
    unittest.main()
