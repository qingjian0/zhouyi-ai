# E10-C.3: autonomous error-rate change alarms (2026-11-11)

## Question

Can a sequential detector raise an alarm when the observed prequential error
rate changes, without receiving an evaluator-declared epoch boundary?

## Method

`prototype/e10c_drift_detector.py` implements a one-sided Bernoulli
likelihood-ratio CUSUM. It consumes only a boolean error stream. The null
baseline is 5% errors and the design alternative is 40%; the default threshold
is 8. On threshold crossing it emits an indexed alarm and resets its statistic.

`prototype/e10c_drift_detection_experiment.py` evaluates 30 deterministic
seeds per scenario, each with 300 observations:

- stationary: 5% error throughout;
- abrupt: 5% until index 120, then 55%;
- gradual: 5% until index 100, then a linear increase to 55% over 80 samples;
- transient noise burst: 30% for 12 samples, then return to 5%.

The evaluator retains the change index for scoring. The detector receives only
the ordered boolean error values.

## Metrics

For each scenario, report alarm-run rate, mean alarm count, and, for persistent
change scenarios, detection rate plus mean/median delay from the known change
index. Stationary and transient-noise alarm rates are false-alarm diagnostics.

## Interpretation boundary

An alarm means the observed error stream is less compatible with the configured
baseline than with the configured higher-error alternative. It does **not**
prove concept drift, identify a new rule, or distinguish drift from label noise,
distribution shift, evaluator defects, or implementation regressions.

This module deliberately does not:
- assign observations to epochs;
- delete or deactivate historical evidence;
- adjudicate contradictory labels;
- expand or regenerate the hypothesis universe;
- modify the production E10 learner.

A subsequent experiment must add abstention/OOD and version-space inconsistency
as separate signals, calibrate thresholds on stationary controls, and test
correlated/heteroskedastic noise. Only after alarm calibration should bounded
epoch creation and candidate expansion be considered.

## Reproduction

```bash
python -m prototype.e10c_drift_detection_experiment --seeds 30 --start-seed 3100
python -m unittest tests.test_e10c_drift_detector -v
```

Results must be recorded from the actual CI output before making performance
claims. This is a synthetic detector audit, not evidence of general autonomous
concept-drift learning.
