import unittest

from prototype.yixiang_profile import (
    ProfileSet, SourceRef, SourcedClaim, TrigramProfile,
    TRIGRAM_LINES_BOTTOM_TO_TOP, validate_profile_set,
)


class YixiangProfileTests(unittest.TestCase):
    def source(self, source_id="zhouyi"):
        return SourceRef(source_id, "周易", "test-edition-1", "系辞上·某章")

    def profile(self, *, claims=(), trigram="乾", lines=None, profile_id="p1"):
        return TrigramProfile(
            profile_id, "test-tradition", "v1", trigram,
            TRIGRAM_LINES_BOTTOM_TO_TOP[trigram] if lines is None else lines,
            tuple(claims),
        )

    def test_all_eight_trigrams_have_unique_three_bit_encodings(self):
        values = tuple(TRIGRAM_LINES_BOTTOM_TO_TOP.values())
        self.assertEqual(len(values), 8)
        self.assertEqual(len(set(values)), 8)
        for name, bits in TRIGRAM_LINES_BOTTOM_TO_TOP.items():
            profile_set = ProfileSet("set", (self.source(),), (self.profile(trigram=name),))
            self.assertEqual(validate_profile_set(profile_set), ())

    def test_rejects_name_and_bit_encoding_mismatch(self):
        item = self.profile(trigram="乾", lines=(0, 0, 0))
        with self.assertRaises(ValueError):
            ProfileSet("set", (self.source(),), (item,)).validate()

    def test_rejects_boolean_or_non_integer_bits(self):
        for bits in ((True, 1, 1), (1.0, 1, 1), (1, 1)):
            with self.subTest(bits=bits):
                item = self.profile(lines=bits)
                with self.assertRaises(ValueError):
                    ProfileSet("set", (self.source(),), (item,)).validate()

    def test_rejects_claim_without_registered_source(self):
        claim = SourcedClaim("乾", "象", "甲", "missing", "scope-a", "c1", "系辞上·某章")
        with self.assertRaisesRegex(ValueError, "unknown source"):
            ProfileSet("set", (self.source(),), (self.profile(claims=(claim,)),)).validate()

    def test_rejects_duplicate_source_ids_and_profile_ids(self):
        with self.assertRaisesRegex(ValueError, "source_id"):
            ProfileSet("set", (self.source(), self.source()), ()).validate()
        with self.assertRaisesRegex(ValueError, "profile_id"):
            ProfileSet("set", (self.source(),), (
                self.profile(profile_id="same"),
                self.profile(profile_id="same", trigram="坤"),
            )).validate()

    def test_reports_conflicts_without_collapsing_sources(self):
        claims = (
            SourcedClaim("乾", "attribute", "A", "zhouyi", "scope-1", "c1", "说卦传·第七章"),
            SourcedClaim("乾", "attribute", "B", "zhouyi", "scope-1", "c2", "说卦传·第七章"),
        )
        profiles = (
            self.profile(claims=claims),
        )
        conflicts = validate_profile_set(ProfileSet("set", (self.source(),), profiles))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].object_values, ("A", "B"))
        self.assertEqual(conflicts[0].source_ids, ("zhouyi",))
        self.assertEqual(conflicts[0].claim_ids, ("c1", "c2"))


    def test_requires_claim_level_locator_and_unique_claim_ids(self):
        missing_locator = SourcedClaim("乾", "attribute", "A", "zhouyi", "scope", "c1")
        with self.assertRaisesRegex(ValueError, "exact locator"):
            ProfileSet("set", (self.source(),), (self.profile(claims=(missing_locator,)),)).validate()

        duplicate_ids = (
            SourcedClaim("乾", "attribute", "A", "zhouyi", "scope", "same", "说卦传·七"),
            SourcedClaim("乾", "attribute", "B", "zhouyi", "scope", "same", "说卦传·八"),
        )
        with self.assertRaisesRegex(ValueError, "claim_id"):
            ProfileSet("set", (self.source(),), (self.profile(claims=duplicate_ids),)).validate()

    def test_rejects_unknown_claim_kind_and_review_status(self):
        bad_kind = SourcedClaim(
            "乾", "attribute", "A", "zhouyi", "scope", "c1", "说卦传·七",
            claim_kind="canonical_truth",
        )
        with self.assertRaisesRegex(ValueError, "claim_kind"):
            ProfileSet("set", (self.source(),), (self.profile(claims=(bad_kind,)),)).validate()
        bad_status = SourcedClaim(
            "乾", "attribute", "A", "zhouyi", "scope", "c1", "说卦传·七",
            review_status="approved_by_model",
        )
        with self.assertRaisesRegex(ValueError, "review_status"):
            ProfileSet("set", (self.source(),), (self.profile(claims=(bad_status,)),)).validate()

    def test_same_claim_in_different_scopes_is_not_a_conflict(self):
        claims = (
            SourcedClaim("乾", "attribute", "A", "zhouyi", "scope-1", "c1", "说卦传·第七章"),
            SourcedClaim("乾", "attribute", "B", "zhouyi", "scope-2", "c2", "说卦传·第八章"),
        )
        profile_set = ProfileSet("set", (self.source(),), (self.profile(claims=claims),))
        self.assertEqual(validate_profile_set(profile_set), ())


if __name__ == "__main__":
    unittest.main()
