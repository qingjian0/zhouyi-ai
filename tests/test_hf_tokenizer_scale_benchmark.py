import importlib.util
import tempfile
import unittest
from pathlib import Path

from prototype.hf_tokenizer_scale_benchmark import (
    TokenizerBenchmarkError,
    benchmark_whole_document,
)


@unittest.skipUnless(importlib.util.find_spec("tokenizers"), "optional tokenizers extra is not installed")
class HuggingFaceScaleBenchmarkTests(unittest.TestCase):
    def _fixture(self, root):
        from tokenizers import Tokenizer, models, pre_tokenizers
        tokenizer = Tokenizer(models.WordLevel(
            vocab={"[UNK]": 0, "hello": 1, "world": 2, "你好": 3},
            unk_token="[UNK]",
        ))
        tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
        asset = root / "tokenizer.json"
        tokenizer.save(str(asset))
        return asset

    def test_reports_canonical_whole_document_count_and_asset_digests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = self._fixture(root)
            source = root / "source.txt"
            source.write_text("hello world hello", encoding="utf-8")
            report = benchmark_whole_document(
                source, asset, tokenizer_id="fixture-wordlevel@v1", expected_tokens=3
            )
            self.assertEqual(report["token_count"], 3)
            self.assertTrue(report["expected_token_count_match"])
            self.assertEqual(len(report["tokenizer_asset_sha256"]), 64)
            self.assertEqual(len(report["source_sha256"]), 64)
            self.assertEqual(report["buffered_token_id_count"], 3)
            self.assertIn(report["process_rss_measurement"]["source"],
                          ("sampled_process_rss", "unavailable"))

    def test_count_mismatch_is_reported_not_silently_adjusted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = self._fixture(root)
            source = root / "source.txt"
            source.write_text("hello world", encoding="utf-8")
            report = benchmark_whole_document(
                source, asset, tokenizer_id="fixture-wordlevel@v1", expected_tokens=3
            )
            self.assertEqual(report["token_count"], 2)
            self.assertFalse(report["expected_token_count_match"])

    def test_rejects_invalid_utf8_and_missing_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = self._fixture(root)
            source = root / "source.txt"
            source.write_bytes(b"\\xff")
            with self.assertRaises(TokenizerBenchmarkError):
                benchmark_whole_document(source, asset, tokenizer_id="fixture@v1")
            source.write_text("hello", encoding="utf-8")
            with self.assertRaises(TokenizerBenchmarkError):
                benchmark_whole_document(source, asset, tokenizer_id=" ")


if __name__ == "__main__":
    unittest.main()
