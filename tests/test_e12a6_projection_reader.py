import tempfile
import unittest
from pathlib import Path

from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, Candidate, CandidateState, Evidence, SplitRole,
)
from prototype.e12a6_projection_reader import LifecycleProjectionReader
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.zpcm_memory import ZPCMMemory


def _candidate():
    return Candidate(
        candidate_id="rel:lazy-reader", version=1, canonical_expression="x > y",
        proposer_family="relational", supporting_families=("relational",),
        input_types=("number", "number"), operator="GT",
    )


def _evidence():
    return Evidence(
        evidence_id="lazy-train-1", episode_id="ep-lazy",
        world_family="finite-rule-world", split_role=SplitRole.TRAIN,
        observation_id="obs-lazy-1", outcome="true", model_version="model-0",
        prediction_commit_step=1, label_visibility_step=2,
    )


def _propose():
    return Action(
        action_id="lazy-propose-1", action_type=ActionType.PROPOSE,
        candidate_id="rel:lazy-reader", candidate_version=1,
        from_state=CandidateState.OBSERVED, to_state=CandidateState.PROPOSED,
    )


class LifecycleProjectionReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "zpcm.db"
        self.memory = ZPCMMemory(self.path)
        self.writer = PersistentLifecycleLedger(self.memory, scope="lazy-scope")

    def tearDown(self):
        self.memory.close()
        self.tmp.cleanup()

    def test_point_reads_and_keyset_iterators_are_scoped_and_ordered(self):
        self.writer.register_candidate(_candidate())
        self.writer.register_evidence(_evidence())
        self.writer.apply(_propose())
        reader = LifecycleProjectionReader(self.memory, scope="lazy-scope")

        self.assertEqual(reader.counts(), {"candidates": 1, "evidence": 1, "actions": 1})
        self.assertEqual(reader.get_candidate("rel:lazy-reader", 1).state, CandidateState.PROPOSED)
        self.assertEqual(reader.get_evidence("lazy-train-1").outcome,
                         "opaque-evidence-ref:lazy-train-1")
        self.assertEqual(reader.get_action("lazy-propose-1").to_state, CandidateState.PROPOSED)
        self.assertEqual(len(list(reader.iter_candidates(page_size=1))), 1)
        self.assertEqual(len(list(reader.iter_evidence(page_size=1))), 1)
        self.assertEqual(len(list(reader.iter_actions(page_size=1))), 1)
        self.assertIsNone(LifecycleProjectionReader(
            self.memory, scope="different-scope",
        ).get_candidate("rel:lazy-reader", 1))

    def test_reader_verifies_projection_and_materializes_only_on_explicit_request(self):
        self.writer.register_candidate(_candidate())
        self.writer.register_evidence(_evidence())
        self.writer.apply(_propose())
        reader = LifecycleProjectionReader(self.memory, scope="lazy-scope")

        self.assertTrue(reader.verify()["ok"])
        ledger = reader.materialize_ledger()
        self.assertEqual(ledger.candidates[("rel:lazy-reader", 1)].state,
                         CandidateState.PROPOSED)
        self.assertEqual(len(ledger.evidence), 1)
        self.assertEqual(len(ledger.actions), 1)
        self.assertIn("lazy-propose-1", ledger._action_ids)

    def test_action_projection_keyset_scan_uses_scope_sequence_index(self):
        self.writer.register_candidate(_candidate())
        self.writer.register_evidence(_evidence())
        self.writer.apply(_propose())
        plan = self.memory.db.execute(
            "EXPLAIN QUERY PLAN SELECT action_json,source_seq "
            "FROM e12a6_action_state_projection "
            "WHERE scope=? AND source_seq>? ORDER BY source_seq LIMIT ?",
            ("lazy-scope", 0, 256),
        ).fetchall()
        details = " ".join(row["detail"] for row in plan)
        self.assertIn("e12a6_action_state_by_scope_seq", details)

    def test_projection_iterator_rejects_unbounded_page_sizes(self):
        reader = LifecycleProjectionReader(self.memory, scope="lazy-scope")
        with self.assertRaises(Exception):
            list(reader.iter_candidates(page_size=0))

    def test_projection_iterator_is_bounded_by_start_high_water(self):
        self.writer.register_candidate(_candidate())
        second = Candidate(
            candidate_id="rel:lazy-reader-2", version=1, canonical_expression="x < y",
            proposer_family="relational", supporting_families=("relational",),
            input_types=("number", "number"), operator="LT",
        )
        third = Candidate(
            candidate_id="rel:lazy-reader-3", version=1, canonical_expression="x == y",
            proposer_family="relational", supporting_families=("relational",),
            input_types=("number", "number"), operator="EQ",
        )
        self.writer.register_candidate(second)
        reader = LifecycleProjectionReader(self.memory, scope="lazy-scope")

        iterator = reader.iter_candidates(page_size=1)
        first = next(iterator)
        self.assertEqual(first.candidate_id, "rel:lazy-reader")

        # Updating an already-yielded row moves its projection source_seq
        # beyond the iterator's captured high-water mark. A new candidate is
        # also appended after iterator creation. Neither may be revisited.
        self.writer.apply(_propose())
        self.writer.register_candidate(third)

        remaining = list(iterator)
        self.assertEqual(
            [candidate.candidate_id for candidate in remaining],
            ["rel:lazy-reader-2"],
        )


if __name__ == "__main__":
    unittest.main()
