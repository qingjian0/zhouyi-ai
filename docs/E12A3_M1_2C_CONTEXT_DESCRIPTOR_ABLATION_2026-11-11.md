# E12-A3-M1.2c Context Descriptor Aggregation Ablation

Date: 2026-11-11  
Status: TOP3_MEAN, TOP2_MEAN, and MAX variants implemented and benchmarked; MAX is the best context-router point estimate but does not establish a reliable advantage over EQUAL  
Motivation: M1.2b showed that grammar-stratified probes slightly improved PARITY but did not improve aggregate accuracy. The top-three mean may dilute a single highly informative candidate.

## 1. Research question

Given identical grammar-stratified probes, does the family descriptor aggregation rule affect task routing?

## 2. Compared descriptors

- TOP3_MEAN: mean accuracy of the three strongest of four probes.
- TOP2_MEAN: mean accuracy of the two strongest of four probes.
- MAX: maximum accuracy among the four probes.

The probe candidates, Context-Support rows, proposer pools, exploration floor, remaining-budget policy, and total budget are identical. Only the aggregation rule changes.

## 3. Controls

- Random-probe Support-context router.
- Grammar-stratified TOP3_MEAN router.
- Grammar-stratified TOP2_MEAN router.
- Grammar-stratified MAX router.
- EQUAL and ROUND_ROBIN.
- UCB1_MEAN.
- STAT, RELATIONAL, RANDOM, and BOUNDED_ENUM.

## 4. Data and budget

- 20 seeds × 3 task families: Threshold, Pairwise Difference, PARITY.
- Proposal-Support 48 / Context-Support 16 within the 64-row Support partition.
- Four probes per proposer family, 12 context evaluations total.
- 31 proposal slots per method.
- Gate-Final selects once; Locked Test scores the frozen candidate.

## 5. Acceptance criteria

An aggregation rule is promising only if it improves aggregate Locked-Test accuracy over both EQUAL and the random-probe router, retains task-family robustness, and survives paired seed-clustered uncertainty analysis.

No aggregation rule may inspect Gate-Dev, Gate-Final, or Locked-Test when constructing its context descriptor.

## 6. Result

MAX reached 78.49% mean Locked-Test accuracy and TOP2_MEAN reached 78.18%, compared with 77.60% for EQUAL. Their paired seed-clustered 95% intervals versus EQUAL both include zero. BOUNDED_ENUM remains best overall at 82.08%.

Full results: `E12A3_M1_2C_DESCRIPTOR_AGGREGATION_RESULTS_2026-11-11.md`.

The remaining weakness is task routing on Pairwise Difference. The next research step is a richer Support-derived descriptor that includes operator coverage, feature-role coverage, and top-candidate score gaps.

## 7. Limitations

- Context-Support remains small.
- Accuracy is a coarse score and is not calibrated probability.
- Four proposals may still miss the relevant feature/value combination.
- Proposal-slot matching does not match CPU or wall-clock cost.
- This is a static task router, not a learned contextual bandit.
