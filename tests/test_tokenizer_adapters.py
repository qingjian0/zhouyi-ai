import unittest

from prototype.streaming_token_count import count_token_stream
from prototype.tokenizer_adapters import BufferedTokenizerOracle


def whole_document_encoder(text):
    # Tiny deterministic oracle: "ab" is one token; all other characters
    # are emitted individually. This models a merge that crosses chunk edges.
    ids = []
    index = 0
    while index < len(text):
        if text.startswith("ab", index):
            ids.append(100)
            index += 2
        else:
            ids.append(ord(text[index]))
            index += 1
    return ids


class BufferedTokenizerOracleTests(unittest.TestCase):
    def test_whole_document_encoding_is_independent_of_chunk_boundaries(self):
        tokenizer = BufferedTokenizerOracle("fixture-bpe-v1", whole_document_encoder)
        result = count_token_stream(["a", "", "b", "c"], tokenizer)
        self.assertEqual(result.tokenizer_id, "fixture-bpe-v1")
        self.assertEqual(result.token_count, 2)
        self.assertEqual(result.chunks, 4)
        self.assertEqual(result.characters, 3)

    def test_emits_no_ids_until_final_flush(self):
        tokenizer = BufferedTokenizerOracle("fixture-v1", whole_document_encoder)
        self.assertEqual(tokenizer.feed("a"), ())
        self.assertEqual(tokenizer.feed("b"), ())
        self.assertEqual(tokenizer.feed("", final=True), (100,))
        self.assertEqual(tokenizer.buffered_characters, 0)

    def test_rejects_feed_after_finalization(self):
        tokenizer = BufferedTokenizerOracle("fixture-v1", whole_document_encoder)
        tokenizer.feed("a", final=True)
        with self.assertRaisesRegex(RuntimeError, "already been finalized"):
            tokenizer.feed("b")

    def test_rejects_invalid_encoder_output(self):
        tokenizer = BufferedTokenizerOracle("fixture-v1", lambda _: [1, True])
        with self.assertRaisesRegex(ValueError, "invalid token ID"):
            tokenizer.feed("x", final=True)

    def test_requires_stable_tokenizer_identity_and_callable(self):
        with self.assertRaises(ValueError):
            BufferedTokenizerOracle(" ", whole_document_encoder)
        with self.assertRaises(TypeError):
            BufferedTokenizerOracle("fixture-v1", None)


if __name__ == "__main__":
    unittest.main()
