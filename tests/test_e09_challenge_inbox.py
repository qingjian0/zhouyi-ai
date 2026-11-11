import unittest

from prototype.e09_challenge_inbox import E09ChallengeError, E09ChallengeInbox


class E09ChallengeInboxTests(unittest.TestCase):
    def setUp(self):
        self.inbox = E09ChallengeInbox({"obs-1", "obs-2"})

    def test_accepts_only_minimal_label_free_signal(self):
        payload = {
            "challenge_id": "c-1",
            "observation_id": "obs-1",
            "challenge_kind": "RECONSIDER",
        }
        self.assertTrue(self.inbox.accept(payload))
        self.assertFalse(self.inbox.accept(payload))
        self.assertEqual(len(self.inbox.pending()), 1)
        self.inbox.acknowledge("c-1")
        self.assertEqual(self.inbox.pending(), ())
        self.assertEqual(self.inbox.snapshot()["acknowledged_ids"], ["c-1"])

    def test_rejects_raw_label_or_extra_fields(self):
        with self.assertRaisesRegex(E09ChallengeError, "allowlisted fields"):
            self.inbox.accept({
                "challenge_id": "c-2",
                "observation_id": "obs-1",
                "challenge_kind": "RECONSIDER",
                "target": "secret-label",
            })

    def test_rejects_unknown_observation_and_unknown_kind(self):
        with self.assertRaisesRegex(E09ChallengeError, "already committed"):
            self.inbox.accept({
                "challenge_id": "c-3",
                "observation_id": "not-committed",
                "challenge_kind": "RECONSIDER",
            })
        with self.assertRaisesRegex(E09ChallengeError, "unsupported challenge_kind"):
            self.inbox.accept({
                "challenge_id": "c-4",
                "observation_id": "obs-1",
                "challenge_kind": "THE_ANSWER_IS_NO",
            })

    def test_rejects_challenge_id_content_conflict(self):
        self.inbox.accept({
            "challenge_id": "c-5",
            "observation_id": "obs-1",
            "challenge_kind": "RECONSIDER",
        })
        with self.assertRaisesRegex(E09ChallengeError, "reused with different content"):
            self.inbox.accept({
                "challenge_id": "c-5",
                "observation_id": "obs-2",
                "challenge_kind": "RECONSIDER",
            })


if __name__ == "__main__":
    unittest.main()
