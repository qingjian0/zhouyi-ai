"""Tests for the optional ZhouyiAI Omega PyTorch model."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

if importlib.util.find_spec("torch") is None:
    raise unittest.SkipTest("PyTorch is an optional dependency; install the model extra")

import torch

from prototype.omega_model import (
    OmegaConfig,
    OmegaModel,
    causal_language_loss,
    load_checkpoint,
    save_checkpoint,
)


class OmegaModelTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(11)
        self.config = OmegaConfig(
            vocab_size=31, d_model=32, n_heads=4, n_layers=2,
            num_classiang_slots=5, max_seq_len=16, dropout=0.0,
        )
        self.model = OmegaModel(self.config)

    def test_forward_shapes_and_parameter_count(self):
        tokens = torch.randint(0, self.config.vocab_size, (2, 9))
        result = self.model(tokens)
        self.assertEqual(tuple(result["logits"].shape), (2, 9, 31))
        self.assertEqual(tuple(result["hidden_states"].shape), (2, 9, 32))
        self.assertEqual(tuple(result["relation_logits"].shape), (2, 2, 5, 5))
        self.assertEqual(tuple(result["composition_logits"].shape), (2, 2, 5, 5))
        self.assertGreater(self.model.parameter_count(), 0)

    def test_language_loss_backpropagates(self):
        tokens = torch.randint(0, self.config.vocab_size, (2, 9))
        loss = causal_language_loss(self.model(tokens)["logits"], tokens)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertIsNotNone(self.model.token_embedding.weight.grad)

    def test_future_tokens_do_not_change_prefix_logits(self):
        self.model.eval()
        prefix = torch.tensor([[1, 2, 3, 4]])
        left = torch.cat((prefix, torch.tensor([[5, 6, 7]])), dim=1)
        right = torch.cat((prefix, torch.tensor([[8, 9, 10]])), dim=1)
        with torch.no_grad():
            left_logits = self.model(left)["logits"][:, :4]
            right_logits = self.model(right)["logits"][:, :4]
        self.assertTrue(torch.allclose(left_logits, right_logits, atol=1e-6, rtol=1e-6))

    def test_checkpoint_round_trip(self):
        tokens = torch.randint(0, self.config.vocab_size, (1, 7))
        self.model.eval()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "omega.pt")
            save_checkpoint(self.model, path)
            restored = load_checkpoint(path)
            restored.eval()
            with torch.no_grad():
                expected = self.model(tokens)["logits"]
                actual = restored(tokens)["logits"]
            self.assertTrue(torch.allclose(expected, actual, atol=1e-6, rtol=1e-6))


if __name__ == "__main__":
    unittest.main()
