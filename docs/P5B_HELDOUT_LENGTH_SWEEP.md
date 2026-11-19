# P5-B held-out length sweep

Run a deterministic evaluation curve over multiple held-out distractor lengths:

```bash
python -m prototype.recurrent_length_sweep --task delayed_copy \
  --train-examples 128 --eval-examples 128 --epochs 5 \
  --train-gap-length 16 --eval-gap-lengths 4,8,16,32,64,128
```

For every gap length, the runner retrains each architecture from the same
seed-specific initialization and the same training examples, changing only
the held-out evaluation gap. It reports per-seed raw metrics and per-model,
per-length mean accuracy, population standard deviation, mean BCE, parameter
counts, and state-carry parity.

The default three seeds are exploratory. Publish raw JSON, increase seeds for
statistical claims, and include longer lengths only when the compute budget
permits. The benchmark remains synthetic binary delayed-copy/distractor recall;
it does not establish natural-language long-context capability or 1M-token
performance.
