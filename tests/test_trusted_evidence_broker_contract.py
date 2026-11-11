import unittest

from prototype.trusted_evidence_broker_contract import (
    BrokerContractError,
    ChallengeSignalDTO,
    LearnerSnapshotDTO,
)


class TrustedEvidenceBrokerContractTests(unittest.TestCase):
    def projection(self):
        return {
            "episode_id": "ep-1",
            "learner_track": "track-a",
            "last_sequence": 987,  # must never become a public cursor
            "observations": {"obs-1": {"observation_id": "obs-1", "sequence_no": 4}},
            "predictions": {"p-1": {"observation_id": "obs-1", "model_version": "m1"}},
            "evidence": {"e-1": {"evidence_id": "e-1", "outcome": "visible-support"}},
            "structures": {"s-1": {"version_id": "s-1@1"}},
            "candidates": {"s-1@1": {"candidate_id": "s-1", "state": "train_supported"}},
            "actions": [{"action_id": "a-1", "event_id": "private-event", "sequence_no": 9, "to_state": "proposed"}],
            "released_challenges": [{
                "challenge_id": "c-1",
                "observation_id": "obs-1",
                "challenge_kind": "RECONSIDER",
            }],
            "track_candidate_objects": {},
            "track_action_objects": {},
        }

    def test_snapshot_uses_opaque_cursor_and_does_not_export_global_sequence(self):
        dto = LearnerSnapshotDTO.from_projection(self.projection(), opaque_cursor="opaque:track-a:1")
        payload = dto.to_dict()
        self.assertEqual(payload["cursor"], "opaque:track-a:1")
        self.assertNotIn("last_sequence", payload)
        self.assertNotIn("sequence_no", str(payload))
        self.assertEqual(payload["released_challenges"][0]["challenge_id"], "c-1")
        self.assertEqual(payload["actions"][0], {"action_id": "a-1", "to_state": "proposed"})

    def test_snapshot_fails_closed_on_nested_evaluator_fields(self):
        projection = self.projection()
        projection["evidence"]["bad"] = {"evidence_id": "bad", "target": "hidden"}
        with self.assertRaisesRegex(BrokerContractError, "private field"):
            LearnerSnapshotDTO.from_projection(projection, opaque_cursor="opaque:1")

    def test_snapshot_rejects_non_allowlisted_projection_shapes(self):
        projection = self.projection()
        projection["released_challenges"][0]["source_evaluation_id"] = "eval-secret"
        with self.assertRaisesRegex(BrokerContractError, "exactly three"):
            LearnerSnapshotDTO.from_projection(projection, opaque_cursor="opaque:1")

    def test_challenge_dto_rejects_extra_fields_and_empty_values(self):
        with self.assertRaises(BrokerContractError):
            ChallengeSignalDTO.from_mapping({
                "challenge_id": "c", "observation_id": "o",
                "challenge_kind": "RECONSIDER", "target": "secret",
            })
        with self.assertRaises(BrokerContractError):
            ChallengeSignalDTO.from_mapping({
                "challenge_id": " ", "observation_id": "o",
                "challenge_kind": "RECONSIDER",
            })


if __name__ == "__main__":
    unittest.main()
