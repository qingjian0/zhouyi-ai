# CPG-EI proximal group-L1 calibration

The mean-over-six-heads gradient correction reduces the data-gradient scale by
six relative to the prior implementation. The SGD learning-rate default was
therefore rescaled from 0.35 to 2.1. The proximal group-L1 operation also
contains the learning rate directly in its shrink factor, so its coefficient
must be calibrated independently rather than assumed to be invariant.

This sweep holds learning rate at 2.1 and tests group-L1 values
0.001, 0.0025, 0.005, 0.0075, 0.01, 0.015 and 0.03 in two paths:

- Direct sparse-teacher fitting with all relation features enabled.
- Residual structure discovery starting with no active relation features.

Five seeds are used. No validation result selects a configuration; all
configurations are reported. The synthetic teacher has six known active
relation groups. This is a finite calibration diagnostic, not a general
relation-induction or language-reasoning claim.
