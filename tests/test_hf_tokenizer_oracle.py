import unittest

from prototype.hf_tokenizer_oracle import verify_chunk_boundary_parity
from prototype.tokenizer_adapters import BufferedTokenizerOracle


def fixture_encode(text):
    """Tiny merge tokenizer with UTF-8 and whitespace-sensitive code points."""
    tokens = []
    index = 0
    while index < len(text):
        if text.startswith("ab", index):
            tokens.append(1000)
            index += 2
        elif text.startswith("  ", index):
            tokens.append(1001)
            index += 2
        else:
            tokens.append(ord(text[index]))
            index += 1
    return tokens


class HuggingFaceTokenizerOracleTests(unittest.TestCase):
    def test_parity_across_unicode_whitespace_punctuation_and_long_text(self):
        samples = [
            "中文测试，标点！",
            "emoji🙂与多字节字符 café",
            "  leading and trailing  ",
            "a" * 2048 + "b" * 2048,
            "ab, ab!  ab?",
        ]
        for text in samples:
            for split in (0, 1, len(text) // 2, max(0, len(text) - 1), len(text)):
                sizes = (split, len(text) - split)
                result = verify_chunk_boundary_parity(
                    fixture_encode,
                    tokenizer_id="fixture-tokenizer-v1",
                    text=text,
                    chunk_sizes=sizes,
                )
                self.assertTrue(result.token_ids_equal, (text[:20], sizes))

    def test_rejects_invalid_partition(self):
        with self.assertRaisesRegex(ValueError, "sum to the text length"):
            verify_chunk_boundary_parity(
                fixture_encode, tokenizer_id="fixture-v1", text="abc", chunk_sizes=(1, 1)
            )

    def test_rejects_negative_chunk_size(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            verify_chunk_boundary_parity(
                fixture_encode, tokenizer_id="fixture-v1", text="abc", chunk_sizes=(-1, 4)
            )

    def test_oracle_uses_canonical_ids_not_only_matching_count(self):
        oracle = BufferedTokenizerOracle("fixture-v1", fixture_encode)
        emitted = list(oracle.feed("a", final=False))
        emitted.extend(oracle.feed("b", final=True))
        self.assertEqual(tuple(emitted), tuple(fixture_encode("ab")))
        self.assertEqual(tuple(emitted), (1000,))


if __name__ == "__main__":
    unittest.main()
