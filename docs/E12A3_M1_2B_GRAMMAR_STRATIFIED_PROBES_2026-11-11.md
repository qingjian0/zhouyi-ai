# E12-A3-M1.2b Grammar-Stratified Context Probes

Date: 2026-11-11  
Status: implementation and CI validation pending  
Motivation: M1.2 random four-proposal probes failed to expose the PARITY operator reliably, causing the context descriptor to miss the STAT specialist.

## 1. Research question

Does operator-stratified probe selection improve Support-context routing when the probe budget is fixed at four proposals per proposer family?

This is a controlled correction to probe sampling, not a new increase in compute.

## 2. Compared strategies

A. RANDOM probe: first four proposals from the seeded shuffled family pool.  
B. GRAMMAR_STRATIFIED probe:
1. Select one candidate from each distinct operator family.
2. Fill remaining slots with candidates having distinct feature / relation roles.
3. If slots remain, fill deterministically from the remaining pool.

For STAT, this ensures the probe includes GE, EQ, and PARITY when all are available. For RELATIONAL, it prioritizes distinct feature-pair roles. RANDOM uses its available operator diversity.

Both strategies use exactly four proposals per family and the same 16-row Context-Support partition.

## 3. Shared protocol

- Outer split remains Support 64 / Gate-Dev 32 / Gate-Final 32 / Locked Test 32.
- Support is split into Proposal-Support 48 / Context-Support 16.
- Proposer pools are generated from Proposal-Support only.
- The four probes per family are also the mandatory exploration batch: 12 proposal slots total.
- The remaining 19 proposal slots go to the family with the highest top-three Context-Support accuracy.
- Both router variants use the same proposal pools and 31-slot budget.
- All methods are charged the same 12 context-probe evaluation cost.
- Gate-Final selects once; Locked Test scores only the frozen selection.

## 4. Controls

- STAT, RELATIONAL, RANDOM, BOUNDED_ENUM specialists/controls.
- EQUAL and ROUND_ROBIN.
- UCB1_MEAN.
- RANDOM-probe Support-context router.
- GRAMMAR_STRATIFIED-probe Support-context router.

## 5. Acceptance criteria

The stratified probe is promising only if it:
- improves PARITY without materially harming Threshold or Pairwise Difference;
- improves aggregate Locked-Test accuracy over the random-probe router and EQUAL;
- retains exact proposal and context-probe budgets;
- is robust across independent seeds;
- does not inspect Gate-Dev, Gate-Final, or Locked-Test to construct descriptors.

## 6. Limitations

- Context-Support remains only 16 rows.
- Operator coverage does not guarantee useful feature/threshold coverage.
- The router remains a static task-conditional heuristic, not a learned contextual bandit.
- Proposal-slot matching does not match CPU or wall-clock cost.
- No Yijing-inspired prior is included.
