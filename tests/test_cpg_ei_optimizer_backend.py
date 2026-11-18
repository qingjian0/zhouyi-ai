import unittest
from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example

class OptimizerBackendTests(unittest.TestCase):
    def test_adam_backend_trains_and_returns_finite_losses(self):
        examples = [
            Example(state=(0, 0, 0, 0, 0, 0), target=(0, 0, 0, 0, 0, 0)),
            Example(state=(1, 1, 1, 1, 1, 1), target=(1, 1, 1, 1, 1, 1)),
        ]
        losses = CpgEiTransitionModel.create().train(examples, epochs=3, learning_rate=0.01, optimizer="adam")
        self.assertEqual(len(losses), 3)
        self.assertTrue(all(loss >= 0.0 and loss < float("inf") for loss in losses))

    def test_unknown_optimizer_is_rejected(self):
        examples = [Example(state=(0, 0, 0, 0, 0, 0), target=(0, 0, 0, 0, 0, 0))]
        with self.assertRaises(ValueError):
            CpgEiTransitionModel.create().train(examples, epochs=1, optimizer="not-an-optimizer")

if __name__ == "__main__":
    unittest.main()
