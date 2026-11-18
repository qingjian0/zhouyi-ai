# CPG-EI Mixed-Operator Semantic Identifiability Audit v1

## Purpose

The mixed-operator discovery baseline evaluates prediction, operator recovery, and exact rule recovery. These metrics can disagree when distinct symbolic rules implement the same Boolean function. This audit makes that ambiguity explicit without changing candidate selection.

## Known semantic aliases

For any support of arity k:

- AND is exactly threshold(k).
- OR is exactly threshold(1).

These are not merely similar rules. Their complete truth tables are identical. If the hypothesis space contains both representations, the original operator label cannot be recovered from input/output observations alone.

## Added measurements

- Candidate hypothesis count.
- Number of unique truth functions in the candidate space.
- Structural alias count: hypotheses minus unique truth functions.
- Per-output teacher function equivalence-class size.
- Whether the teacher's function is structurally identifiable in the declared hypothesis space.
- Per-output selected function equivalence-class size and identifiability.
- Operator recovery conditioned on teacher-function identifiability.
- Semantic function recovery reported separately from operator and exact-rule recovery.

The equivalence class is computed from complete truth-table bit masks over all input states, not from the sampled train/development/locked rows. This is a property of the declared hypothesis space, not a use of locked labels.

## Interpretation

A prediction can be semantically exact while its symbolic representation is non-identifiable. Operator recovery must not be interpreted as model failure when multiple declared operators have identical semantics. Conversely, high prediction accuracy does not prove structural recovery.

This audit does not canonicalize or remove aliases, change tie-breaking, alter the locked split, or use teacher manifests during selection. It is a measurement-only refinement.

## Next decision gate

After the audit, decide whether to:

1. Keep all aliases and report equivalence classes (best for studying symbolic representation ambiguity); or
2. Define a canonical operator vocabulary and quotient out exact semantic duplicates (best for a compact prediction benchmark).

Do not silently remove aliases: the chosen ontology changes what "operator recovery" means.

## Scope boundary

This remains a finite synthetic Boolean benchmark and exhaustive symbolic baseline. It is not a learned neural relation-discovery system, open-world induction, natural-language or Yi-Xue reasoning, causal discovery, or a Transformer comparison.
