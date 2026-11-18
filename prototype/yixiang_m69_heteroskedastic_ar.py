"""M69: heteroskedasticity-robust Anderson–Rubin Wald test.

This is an asymptotic HC0 robust test of the reduced-form restriction
E[Z' (Y - beta0 X - controls)] = 0. It does not rely on first-stage
strength, but finite-sample exact F calibration is not claimed.
"""
from __future__ import annotations

from math import exp, isfinite, lgamma, log
from typing import Any, Dict, Mapping, Sequence

from prototype.yixiang_m68_anderson_rubin_weak_iv import (
    _dot, _prepare, _residualize, _solve,
)


def _gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x)."""
    if a <= 0 or x < 0:
        raise ValueError("invalid_incomplete_gamma_arguments")
    if x == 0:
        return 1.0
    gln = lgamma(a)
    eps, tiny, limit = 3e-14, 1e-300, 500
    if x < a + 1.0:
        ap = a
        term = total = 1.0 / a
        for _ in range(limit):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * eps:
                p = total * exp(-x + a * log(x) - gln)
                return max(0.0, min(1.0, 1.0 - p))
        raise ArithmeticError("incomplete_gamma_series_did_not_converge")
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / max(abs(b), tiny)
    if b < 0:
        d = -d
    h = d
    for i in range(1, limit + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return max(0.0, min(1.0, exp(-x + a * log(x) - gln) * h))
    raise ArithmeticError("incomplete_gamma_fraction_did_not_converge")


def heteroskedastic_ar_test(
    data: Mapping[str, Any], beta_null: float, alpha: float = 0.05
) -> Dict[str, Any]:
    """HC0 Wald test of reduced-form instrument coefficients under beta_null.

    The chi-square reference distribution is asymptotic. Controls are partialled
    out first; instrument covariance must have full rank.
    """
    if not isinstance(beta_null, (int, float)) or not isfinite(float(beta_null)):
        raise ValueError("beta_null_must_be_finite")
    if not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha_must_be_between_zero_and_one")
    prepared = _prepare(data)
    x, y, _, _, _, _, zr, gram, df2 = prepared
    n = len(y)
    q = len(zr)
    y_null = [y[i] - float(beta_null) * x[i] for i in range(n)]
    controls = [*[[1.0] * n]]
    controls_rows = data.get("controls")
    if controls_rows is not None and len(controls_rows):
        k = len(controls_rows[0])
        controls.extend([[float(controls_rows[i][j]) for i in range(n)]
                         for j in range(k)])
    residual_y = _residualize(y_null, controls)
    moments = [_dot(z, residual_y) for z in zr]
    gamma = _solve(gram, moments)
    residuals = [
        residual_y[i] - sum(zr[j][i] * gamma[j] for j in range(q))
        for i in range(n)
    ]
    meat = [[
        sum(residuals[i] ** 2 * zr[a][i] * zr[b][i] for i in range(n))
        for b in range(q)
    ] for a in range(q)]
    inv_columns = []
    for j in range(q):
        unit = [1.0 if i == j else 0.0 for i in range(q)]
        inv_columns.append(_solve(gram, unit))
    inv_gram = [[inv_columns[j][i] for j in range(q)] for i in range(q)]
    temp = [[sum(inv_gram[i][k] * meat[k][j] for k in range(q))
             for j in range(q)] for i in range(q)]
    covariance = [[sum(temp[i][k] * inv_gram[j][k] for k in range(q))
                   for j in range(q)] for i in range(q)]
    try:
        weighted = _solve(covariance, gamma, tolerance=1e-14)
    except ValueError as exc:
        raise ValueError("singular_hc0_covariance_under_null") from exc
    statistic = max(0.0, _dot(gamma, weighted))
    p_value = _gamma_q(q / 2.0, statistic / 2.0)
    return {
        "status": "computed_asymptotically_under_heteroskedasticity_robust_model",
        "beta_null": float(beta_null),
        "ar_hc0_wald_statistic": statistic,
        "p_value": p_value,
        "reject": p_value < float(alpha),
        "alpha": float(alpha),
        "degrees_of_freedom": q,
        "covariance_estimator": "HC0",
        "reference_distribution": "asymptotic_chi_square",
        "weak_instrument_robust": True,
        "finite_sample_exact": False,
        "assumptions": [
            "valid_instrument_exogeneity_and_exclusion",
            "linear_single_endogenous_regressor_model",
            "heteroskedasticity_robust_asymptotic_moment_inference",
            "full_rank_instruments_after_controls",
        ],
        "warning": "HC0 asymptotic calibration is not an exact finite-sample F test; small-sample and many-instrument distortions may remain.",
    }
