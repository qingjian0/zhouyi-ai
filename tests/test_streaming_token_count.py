import unittest

from prototype.streaming_token_count import (
    TokenStreamContractError,
    count_token_stream,
)


class PairMergeTokenizer:
    """Tiny test tokenizer whose merge pair deliberately crosses chunk edges."""

    tokenizer_id = "test-pair-merge-v1"

    def __init__(self):
        self.pending = ""
        self.closed = False

    @staticmethod
    def _encode_complete(text):
        output = []
        index = 0
        while index < len(text):
            if text[index:index + 2] == "ab":
                output.append(1000)
                index += 2
            else:
                output.append(ord(text[index]))
                index += 1
        return output

    def feed(self, text, *, final=False):
        if self.closed:
            raise RuntimeError("tokenizer already finalized")
        combined = self.pending + text
        if final:
            self.pending = ""
            self.closed = True
            return self._encode_complete(combined)
        # In this toy vocabulary only a trailing "a" can begin a cross-boundary
        # merge. Retain that suffix; all other suffixes are stable.
        if combined.endswith("a"):
            stable, self.pending = combined[:-1], "a"
        else:
            stable, self.pending = combined, ""
        return self._encode_complete(stable)


class InvalidTokenizer:
    tokenizer_id = "invalid"

    def feed(self, text, *, final=False):
        return [-1]


class StreamingTokenCountTests(unittest.TestCase):
    def test_cross_chunk_merge_matches_whole_document_encoding(self):
        source = "zabcaabab"
        expected = PairMergeTokenizer._encode_complete(source)
        result = count_token_stream(
            ["z", "a", "b", "c", "aa", "b", "ab"], PairMergeTokenizer()
        )
        self.assertEqual(result.token_count, len(expected))
        self.assertEqual(result.tokenizer_id, "test-pair-merge-v1")
        self.assertEqual(result.characters, len(source))
        self.assertEqual(result.chunks, 7)

    def test_empty_and_single_chunk_documents_flush_correctly(self):
        empty = count_token_stream([], PairMergeTokenizer())
        one = count_token_stream(["ab"], PairMergeTokenizer())
        self.assertEqual(empty.token_count, 0)
        self.assertEqual(one.token_count, 1)

    def test_rejects_invalid_token_ids(self):
        with self.assertRaisesRegex(TokenStreamContractError, "non-negative integers"):
            count_token_stream(["x"], InvalidTokenizer())

    def test_rejects_non_string_chunks(self):
        with self.assertRaisesRegex(TokenStreamContractError, "must be strings"):
            count_token_stream([b"bytes"], PairMergeTokenizer())

    def test_rejects_missing_tokenizer_identity(self):
        class NoIdentity:
            def feed(self, text, *, final=False):
                return []
        with self.assertRaisesRegex(TokenStreamContractError, "tokenizer_id"):
            count_token_stream(["x"], NoIdentity())


if __name__ == "__main__":
    unittest.main()
