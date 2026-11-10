import unittest

from prototype.e02i2_lineage import (
    IdentityStatus,
    LineageError,
    LineageKind,
    RelationLineageLedger,
)


def create(ledger, identity_id="r1", version_id="r1v1", window=0):
    return ledger.create(
        identity_id=identity_id,
        version_id=version_id,
        members=("a", "b"),
        roles=("source", "target"),
        operator="AND",
        rule_signature="a&b",
        context_signature="lab",
        window=window,
        evidence_refs=("ev1",),
    )


class E02I2LineageLedgerTests(unittest.TestCase):
    def test_create_and_keep_preserve_identity_and_version(self):
        ledger = RelationLineageLedger()
        identity = create(ledger)
        kept = ledger.keep("r1", window=1, evidence_refs=("ev2",))
        self.assertEqual(identity.identity_id, kept.identity_id)
        self.assertEqual(kept.status, IdentityStatus.ACTIVE)
        self.assertEqual(kept.version_ids, ("r1v1",))
        self.assertEqual(len(ledger.versions), 1)
        ledger.assert_consistent()

    def test_modify_adds_immutable_version_under_same_identity(self):
        ledger = RelationLineageLedger()
        create(ledger)
        new = ledger.modify(
            "r1", version_id="r1v2", members=("a", "c"),
            roles=("source", "target"), operator="AND",
            rule_signature="a&c", context_signature="lab",
            window=1, evidence_refs=("ev2",),
        )
        self.assertEqual(new.identity_id, "r1")
        self.assertEqual(new.version_index, 2)
        self.assertEqual(ledger.identities["r1"].version_ids, ("r1v1", "r1v2"))
        self.assertEqual(ledger.versions["r1v1"].members, ("a", "b"))
        self.assertEqual(ledger.version_transitions[0].from_version_id, "r1v1")
        ledger.assert_consistent()

    def test_modify_rejects_identical_structure(self):
        ledger = RelationLineageLedger()
        create(ledger)
        with self.assertRaises(LineageError):
            ledger.modify(
                "r1", version_id="r1v2", members=("a", "b"),
                roles=("source", "target"), operator="AND",
                rule_signature="a&b", context_signature="lab",
                window=1, evidence_refs=("ev2",),
            )
        self.assertEqual(ledger.identities["r1"].version_ids, ("r1v1",))
        self.assertNotIn("r1v2", ledger.versions)

    def test_split_preflight_prevents_partial_child_creation(self):
        ledger = RelationLineageLedger()
        create(ledger)
        with self.assertRaises((LineageError, ValueError, KeyError)):
            ledger.split(
                "r1",
                children=(
                    {"identity_id": "r2", "version_id": "r2v1",
                     "members": ("a", "b"), "roles": ("x", "y"),
                     "operator": "AND", "rule_signature": "a&b"},
                    {"identity_id": "r3", "version_id": "r3v1",
                     "members": ("c", "d"), "roles": ("only-one-role",),
                     "operator": "OR", "rule_signature": "c|d"},
                ),
                window=1,
            )
        self.assertEqual(ledger.identities["r1"].status, IdentityStatus.ACTIVE)
        self.assertNotIn("r2", ledger.identities)
        self.assertNotIn("r3", ledger.identities)
        self.assertEqual(len(ledger.events), 1)

    def test_suspend_then_reactivate_requires_fresh_evidence(self):
        ledger = RelationLineageLedger()
        create(ledger)
        ledger.suspend("r1", window=1)
        with self.assertRaises(LineageError):
            ledger.reactivate("r1", window=2, evidence_refs=())
        active = ledger.reactivate("r1", window=2, evidence_refs=("new-gate",))
        self.assertEqual(active.identity_id, "r1")
        self.assertEqual(active.status, IdentityStatus.ACTIVE)
        self.assertEqual(active.version_ids, ("r1v1",))
        ledger.assert_consistent()

    def test_split_creates_child_identities_and_terminal_parent(self):
        ledger = RelationLineageLedger()
        create(ledger)
        children = ledger.split(
            "r1",
            children=(
                {"identity_id": "r2", "version_id": "r2v1",
                 "members": ("a", "b"), "roles": ("x", "y"),
                 "operator": "AND", "rule_signature": "a&b-left"},
                {"identity_id": "r3", "version_id": "r3v1",
                 "members": ("c", "d"), "roles": ("x", "y"),
                 "operator": "OR", "rule_signature": "c|d"},
            ),
            window=1,
            evidence_refs=("split-audit",),
        )
        self.assertEqual(len(children), 2)
        self.assertEqual(ledger.identities["r1"].status, IdentityStatus.SPLIT)
        self.assertEqual(len(ledger.lineage_edges), 2)
        self.assertTrue(all(e.kind == LineageKind.SPLIT_FROM
                            for e in ledger.lineage_edges))
        ledger.assert_consistent()

    def test_merge_requires_two_active_parents_and_records_provenance(self):
        ledger = RelationLineageLedger()
        create(ledger, "r1", "r1v1", 0)
        create(ledger, "r2", "r2v1", 0)
        merged = ledger.merge(
            ("r1", "r2"), identity_id="r3", version_id="r3v1",
            members=("a", "b", "c"), roles=("x", "y", "z"),
            operator="COMPOSE", rule_signature="compose(r1,r2)",
            window=1, evidence_refs=("joint-confirmation",),
        )
        self.assertEqual(merged.identity_id, "r3")
        self.assertEqual(ledger.identities["r1"].status, IdentityStatus.MERGED)
        self.assertEqual(ledger.identities["r2"].status, IdentityStatus.MERGED)
        self.assertEqual(ledger.lineage_edges[0].source_identity_ids, ("r1", "r2"))
        ledger.assert_consistent()

    def test_replace_creates_new_identity_without_reusing_old_identity(self):
        ledger = RelationLineageLedger()
        create(ledger)
        new = ledger.replace(
            "r1", identity_id="r2", version_id="r2v1",
            members=("x", "y"), roles=("left", "right"),
            operator="XOR", rule_signature="x^y",
            window=1, evidence_refs=("replacement-proof",),
        )
        self.assertEqual(ledger.identities["r1"].status, IdentityStatus.REPLACED)
        self.assertEqual(new.identity_id, "r2")
        self.assertEqual(ledger.lineage_edges[0].kind, LineageKind.REPLACED_BY)
        self.assertEqual(new.version_ids, ("r2v1",))
        ledger.assert_consistent()

    def test_terminal_identity_cannot_be_reactivated_or_modified(self):
        ledger = RelationLineageLedger()
        create(ledger)
        ledger.retire("r1", window=1)
        with self.assertRaises(LineageError):
            ledger.reactivate("r1", window=2, evidence_refs=("fresh",))
        with self.assertRaises(LineageError):
            ledger.keep("r1", window=2)

    def test_windows_must_be_monotonic(self):
        ledger = RelationLineageLedger()
        create(ledger, window=3)
        with self.assertRaises(LineageError):
            ledger.keep("r1", window=2)

    def test_event_log_is_sequential_and_versions_are_unique(self):
        ledger = RelationLineageLedger()
        create(ledger)
        ledger.keep("r1", window=1)
        self.assertEqual([e.sequence for e in ledger.events], [1, 2])
        with self.assertRaises(LineageError):
            ledger.modify(
                "r1", version_id="r1v1", members=("a", "c"),
                roles=("source", "target"), operator="AND",
                rule_signature="a&c", window=2,
            )


if __name__ == "__main__":
    unittest.main()
