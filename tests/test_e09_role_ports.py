import unittest

from prototype.e09_authority_client import E09AuthorityRPCClient, E09LearnerMemorySource
from prototype.e09_role_ports import E09EvaluatorPort, E09LearnerPort, E09ObserverPort


class _FakeClient(E09AuthorityRPCClient):
    def __init__(self):
        self.calls = []

    def put_observation_input(self, **kwargs):
        self.calls.append(("put_observation_input", kwargs))
        return "sha256:input-digest"

    def append_observation(self, **kwargs):
        self.calls.append(("append_observation", kwargs))
        return {"event_id": kwargs["event_id"]}

    def read_observation_input(self, **kwargs):
        self.calls.append(("read_observation_input", kwargs))
        return {"input": "value"}

    def append_prediction_commit(self, **kwargs):
        self.calls.append(("append_prediction_commit", kwargs))
        return {"event_id": kwargs["event_id"]}

    def read_support_feedback(self, **kwargs):
        self.calls.append(("read_support_feedback", kwargs))
        return {"feedback": "support-only"}

    def append_structure_version(self, **kwargs):
        self.calls.append(("append_structure_version", kwargs))
        return {"event_id": kwargs["event_id"]}

    def append_revision(self, **kwargs):
        self.calls.append(("append_revision", kwargs))
        return {"event_id": kwargs["event_id"]}

    def read_learner_checkpoint(self, **kwargs):
        self.calls.append(("read_learner_checkpoint", kwargs))
        return {"payload": {}}

    def read_learner_episode(self, **kwargs):
        self.calls.append(("read_learner_episode", kwargs))
        return []

    def append_evidence_reveal(self, **kwargs):
        self.calls.append(("append_evidence_reveal", kwargs))
        return {"event_id": kwargs["event_id"]}


class E09RolePortTests(unittest.TestCase):
    def setUp(self):
        self.client = _FakeClient()

    def test_observer_port_writes_input_then_publishes_workload_bound_observation(self):
        observer = E09ObserverPort(self.client)
        result = observer.observe(
            episode_id="episode-1",
            observation_id="obs-1",
            query_id="query-1",
            scope="scope/a",
            split="SUPPORT",
            learner_track="track-a",
            input_payload={"features": [1, 2]},
            put_operation_id="put-1",
            observation_operation_id="observation-1",
        )
        self.assertEqual(result["payload_ref"], "sha256:input-digest")
        self.assertEqual(self.client.calls[0][0], "put_observation_input")
        self.assertEqual(self.client.calls[1][0], "append_observation")
        self.assertEqual(
            self.client.calls[1][1]["learner_track"], "track-a"
        )
        self.assertEqual(
            self.client.calls[1][1]["payload_ref"], "sha256:input-digest"
        )

    def test_learner_port_exposes_only_learner_operations_and_memory_source(self):
        learner = E09LearnerPort(self.client)
        self.assertEqual(
            learner.read_observation(
                episode_id="episode-1", observation_id="obs-1", scope="scope/a"
            ),
            {"input": "value"},
        )
        learner.commit_prediction(
            episode_id="episode-1", prediction_id="pred-1",
            payload={"prediction_id": "pred-1"},
            observation_event_id="episode-1:observation:obs-1",
            operation_id="commit-1",
        )
        self.assertEqual(
            learner.read_support_feedback(
                episode_id="episode-1", reveal_event_id="reveal-1", scope="scope/a"
            )["feedback"],
            "support-only",
        )
        self.assertIsInstance(
            learner.memory_source(scope="scope/a", learner_track="track-a"),
            E09LearnerMemorySource,
        )
        learner.checkpoint(
            episode_id="episode-1", scope="scope/a", learner_track="track-a"
        )
        self.assertIn(
            "append_prediction_commit", [name for name, _ in self.client.calls]
        )

    def test_evaluator_port_only_publishes_reveals(self):
        evaluator = E09EvaluatorPort(self.client)
        result = evaluator.reveal(
            episode_id="episode-1",
            prediction_id="pred-1",
            payload={"prediction_id": "pred-1", "split": "SUPPORT"},
            commit_event_id="episode-1:prediction:pred-1",
            operation_id="reveal-1",
        )
        self.assertEqual(result["event_id"], "episode-1:reveal:pred-1")
        self.assertEqual(self.client.calls[0][0], "append_evidence_reveal")


if __name__ == "__main__":
    unittest.main()
