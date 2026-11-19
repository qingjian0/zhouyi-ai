import importlib.util
import tempfile
import unittest
from pathlib import Path

from prototype.hf_tokenizer_oracle import load_tokenizer_oracle, verify_chunk_boundary_parity
from prototype.streaming_token_count import count_token_stream


@unittest.skipUnless(importlib.util.find_spec("tokenizers"), "optional tokenizers extra is not installed")
class HuggingFaceRuntimeIntegrationTests(unittest.TestCase):
    def test_loads_real_tokenizer_json_and_matches_whole_text_ids(self):
        from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

        tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
        tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        tokenizer.decoder = decoders.ByteLevel()
        trainer = trainers.BpeTrainer(
            vocab_size=256,
            min_frequency=1,
            special_tokens=["[UNK]"],
        )
        corpus = [
            "中文测试，标点！",
            "emoji🙂与多字节字符 café",
            "  leading and trailing  ",
            "ab ab ab repeated boundary text",
        ]
        tokenizer.train_from_iterator(corpus * 4, trainer=trainer)

        text = "中文测试，标点！ emoji🙂 café  ab ab"
        with tempfile.TemporaryDirectory() as temp:
            asset = Path(temp) / "tokenizer.json"
            tokenizer.save(str(asset))
            oracle = load_tokenizer_oracle(
                str(asset),
                tokenizer_id="fixture-bpe@revision-1:asset-sha256-fixture",
            )
            canonical = tuple(Tokenizer.from_file(str(asset)).encode(text).ids)

            emitted = []
            cursor = 0
            chunks = [text[:1], text[1:7], text[7:13], text[13:]]
            for chunk in chunks:
                emitted.extend(oracle.feed(chunk, final=False))
                cursor += len(chunk)
            emitted.extend(oracle.feed("", final=True))
            self.assertEqual(cursor, len(text))
            self.assertEqual(tuple(emitted), canonical)

            parity = verify_chunk_boundary_parity(
                lambda value: Tokenizer.from_file(str(asset)).encode(value).ids,
                tokenizer_id=oracle.tokenizer_id,
                text=text,
                chunk_sizes=(1, 6, 6, len(text) - 13),
            )
            self.assertTrue(parity.token_ids_equal)
            self.assertEqual(parity.canonical_token_count, len(canonical))

            counted = count_token_stream(
                [text[:3], text[3:11], text[11:]],
                load_tokenizer_oracle(
                    str(asset),
                    tokenizer_id="fixture-bpe@revision-1:asset-sha256-fixture",
                ),
            )
            self.assertEqual(counted.token_count, len(canonical))


if __name__ == "__main__":
    unittest.main()
