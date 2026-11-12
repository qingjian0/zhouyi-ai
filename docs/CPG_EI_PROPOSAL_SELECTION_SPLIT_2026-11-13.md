# CPG-EI proposal-selection split protocol — 2026-11-13

## Change

The bounded joint-motif proposal routine now accepts an optional
`proposal_examples` split. Candidate parameters are optimized on
`train_examples`, but candidate groups are ranked on the independent
proposal-selection split. The final `validation_examples` argument is used
only after candidate selection to report locked evaluation metrics.

For backward compatibility, omitting `proposal_examples` continues to rank on
the training set. Such runs are exploratory and must not be presented as
held-out candidate selection.

## Test protocol

The added unit test partitions the complete 64-state six-bit input universe
into disjoint train (40), proposal-selection (12), and locked-test (12) sets.
It asserts that the state sets do not overlap and instruments BCE evaluation
to verify that baseline/candidate ranking uses the proposal split, with the
locked test consulted only for the final diagnostic.

A second rule-family target is evaluated on the locked input states as a small
OOD diagnostic. This is a protocol smoke test, not a statistically powered
OOD result and not evidence of general relation induction.

## Interpretation boundary

- Proposal-selection data influences which candidate is retained; it is not
  the final unbiased performance estimate.
- The locked test must remain untouched until all candidate and hyperparameter
  choices are frozen.
- The small finite benchmark has only 64 possible inputs and 20 candidate
  motifs. It does not establish open-ended discovery, natural-language
  reasoning, or superiority to Transformer models.
- Structural support precision/recall, in-family prediction, and cross-family
  OOD performance must continue to be reported separately.
