"""M68: classical Anderson–Rubin inference robust to weak first stages.

Finite-sample exact F calibration is limited to the declared iid Gaussian,
homoskedastic linear model. The AR test does not divide by the estimated
first stage and remains size-valid under arbitrarily weak instruments.
"""
from __future__ import annotations

from math import exp, isfinite, lgamma, log, sqrt
from typing import Any, Dict, List, Mapping, Sequence


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return sqrt(max(0.0, _dot(a, a)))


def _residualize(vector: Sequence[float], controls: Sequence[Sequence[float]],
                 tolerance: float = 1e-10) -> List[float]:
    basis = []
    for column in controls:
        residual = list(map(float, column))
        for q in basis:
            projection = _dot(residual, q)
            residual = [value - projection * qv for value, qv in zip(residual, q)]
        norm = _norm(residual)
        if norm <= tolerance:
            raise ValueError("rank_deficient_controls")
        basis.append([value / norm for value in residual])
    result = list(map(float, vector))
    for q in basis:
        projection = _dot(result, q)
        result = [value - projection * qv for value, qv in zip(result, q)]
    return result


def _solve(matrix: Sequence[Sequence[float]], vector: Sequence[float],
           tolerance: float = 1e-12) -> List[float]:
    n = len(vector)
    aug = [list(map(float, matrix[i])) + [float(vector[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(aug[row][col]))
        if abs(aug[pivot][col]) <= tolerance:
            raise ValueError("rank_deficient_instruments_after_controls")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [aug[row][j] - factor * aug[col][j]
                        for j in range(n + 1)]
    return [aug[i][-1] for i in range(n)]


def _prepare(data: Mapping[str, Any]):
    x = list(map(float, data["x"]))
    y = list(map(float, data["y"]))
    z_rows = data["z"]
    n = len(y)
    if n < 4 or len(x) != n or len(z_rows) != n:
        raise ValueError("x_y_z_sample_sizes_must_match_and_n_be_at_least_4")
    q = len(z_rows[0]) if z_rows else 0
    if q < 1 or any(len(row) != q for row in z_rows):
        raise ValueError("z_must_be_nonempty_rectangular_n_by_q_matrix")
    controls_rows = data.get("controls")
    if controls_rows is None:
        controls_rows = [[] for _ in range(n)]
    if len(controls_rows) != n:
        raise ValueError("control_sample_size_mismatch")
    k_extra = len(controls_rows[0]) if controls_rows else 0
    if any(len(row) != k_extra for row in controls_rows):
        raise ValueError("controls_must_be_rectangular")
    z = [[float(z_rows[i][j]) for i in range(n)] for j in range(q)]
    controls = [[1.0] * n] + [
        [float(controls_rows[i][j]) for i in range(n)]
        for j in range(k_extra)
    ]
    values = [*x, *y, *[v for col in z for v in col],
              *[v for col in controls for v in col]]
    if any(not isfinite(v) for v in values):
        raise ValueError("sample_values_must_be_finite")
    df2 = n - len(controls) - q
    if df2 <= 0:
        raise ValueError("nonpositive_residual_degrees_of_freedom")
    xr = _residualize(x, controls)
    yr = _residualize(y, controls)
    zr = [_residualize(column, controls) for column in z]
    gram = [[_dot(left, right) for right in zr] for left in zr]
    # Fail early if the instrument matrix is rank deficient after controls.
    _solve(gram, [1.0] + [0.0] * (q - 1))
    return x, y, z, controls, xr, yr, zr, gram, df2


def _betacf(a: float, b: float, x: float) -> float:
    max_iter, eps, tiny = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ArithmeticError("incomplete_beta_continued_fraction_did_not_converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = exp(lgamma(a + b) - lgamma(a) - lgamma(b)
             + a * log(x) + b * log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _f_cdf(value: float, df1: int, df2: int) -> float:
    if value <= 0:
        return 0.0
    x = (df1 * value) / (df1 * value + df2)
    return _regularized_beta(x, df1 / 2.0, df2 / 2.0)


def _f_quantile(probability: float, df1: int, df2: int) -> float:
    low, high = 0.0, 1.0
    while _f_cdf(high, df1, df2) < probability:
        high *= 2.0
        if high > 1e16:
            raise ArithmeticError("F_quantile_search_overflow")
    for _ in range(180):
        mid = (low + high) / 2.0
        if _f_cdf(mid, df1, df2) < probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _projection_terms(prepared):
    _, _, _, _, xr, yr, zr, gram, df2 = prepared
    by = [_dot(z, yr) for z in zr]
    bx = [_dot(z, xr) for z in zr]
    inv_by = _solve(gram, by)
    inv_bx = _solve(gram, bx)
    q0 = _dot(by, inv_by)
    q1 = -2.0 * _dot(by, inv_bx)
    q2 = _dot(bx, inv_bx)
    r0 = _dot(yr, yr)
    r1 = -2.0 * _dot(yr, xr)
    r2 = _dot(xr, xr)
    return (q2, q1, q0), (r2, r1, r0), df2


def _evaluate_ar(prepared, beta: float, alpha: float):
    qcoef, rcoef, df2 = _projection_terms(prepared)
    q2, q1, q0 = qcoef
    r2, r1, r0 = rcoef
    qstat = max(0.0, q2 * beta * beta + q1 * beta + q0)
    restricted = max(0.0, r2 * beta * beta + r1 * beta + r0)
    unrestricted = restricted - qstat
    if unrestricted <= 1e-12:
        raise ValueError("zero_unrestricted_residual_variance")
    q = len(prepared[2][0])
    statistic = (qstat / q) / (unrestricted / df2)
    p_value = max(0.0, min(1.0, 1.0 - _f_cdf(statistic, q, df2)))
    critical = _f_quantile(1.0 - alpha, q, df2)
    return statistic, p_value, statistic > critical, critical, df2


def anderson_rubin_test(data: Mapping[str, Any], beta_null: float,
                        alpha: float = 0.05) -> Dict[str, Any]:
    if not isinstance(beta_null, (int, float)) or not isfinite(float(beta_null)):
        raise ValueError("beta_null_must_be_finite")
    if not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha_must_be_between_zero_and_one")
    prepared = _prepare(data)
    statistic, p_value, reject, critical, df2 = _evaluate_ar(
        prepared, float(beta_null), float(alpha)
    )
    q = len(prepared[2][0])
    return {
        "status": "computed_under_iid_gaussian_homoskedastic_linear_model",
        "beta_null": float(beta_null),
        "ar_f_statistic": statistic,
        "p_value": p_value,
        "reject": reject,
        "alpha": float(alpha),
        "critical_value": critical,
        "degrees_of_freedom": [q, df2],
        "weak_instrument_robust": True,
        "assumptions": [
            "iid_errors",
            "homoskedastic_errors",
            "Gaussian_errors_for_exact_finite_sample_calibration",
            "valid_instrument_exogeneity_and_exclusion",
            "linear_single_endogenous_regressor_model",
        ],
    }


def anderson_rubin_confidence_set(data: Mapping[str, Any],
                                  alpha: float = 0.05) -> Dict[str, Any]:
    """Invert the AR F test analytically; preserve unbounded/disconnected sets."""
    if not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha_must_be_between_zero_and_one")
    prepared = _prepare(data)
    qcoef, rcoef, df2 = _projection_terms(prepared)
    q2, q1, q0 = qcoef
    r2, r1, r0 = rcoef
    q = len(prepared[2][0])
    critical = _f_quantile(1.0 - alpha, q, df2)
    # F(beta) <= critical iff this quadratic is non-positive.
    factor = df2 + critical * q
    a = factor * q2 - critical * q * r2
    b = factor * q1 - critical * q * r1
    c = factor * q0 - critical * q * r0
    scale = max(1.0, abs(a), abs(b), abs(c))
    tol = 1e-10 * scale
    if abs(a) <= tol:
        if abs(b) <= tol:
            components = [{"lower": None, "upper": None}] if c <= tol else []
            shape = "all_real" if components else "empty"
        else:
            root = -c / b
            components = ([{"lower": root, "upper": None}] if b < 0
                          else [{"lower": None, "upper": root}])
            shape = "unbounded_ray"
    else:
        discriminant = b * b - 4.0 * a * c
        if discriminant < -tol:
            components = ([{"lower": None, "upper": None}] if a < 0 else [])
            shape = "all_real" if a < 0 else "empty"
        elif abs(discriminant) <= tol:
            root = -b / (2.0 * a)
            components = ([{"lower": None, "upper": None}] if a < 0
                          else [{"lower": root, "upper": root}])
            shape = "all_real" if a < 0 else "singleton"
        else:
            root_delta = sqrt(discriminant)
            roots = sorted(((-b - root_delta) / (2.0 * a),
                            (-b + root_delta) / (2.0 * a)))
            if a > 0:
                components = [{"lower": roots[0], "upper": roots[1]}]
                shape = "bounded_interval"
            else:
                components = [
                    {"lower": None, "upper": roots[0]},
                    {"lower": roots[1], "upper": None},
                ]
                shape = "two_unbounded_rays"
    return {
        "status": "computed_under_iid_gaussian_homoskedastic_linear_model",
        "confidence_level": 1.0 - float(alpha),
        "alpha": float(alpha),
        "critical_value": critical,
        "degrees_of_freedom": [q, df2],
        "set_shape": shape,
        "components": components,
        "weak_instrument_robust": True,
        "inversion": "analytic_quadratic_not_grid_search",
        "assumptions": [
            "iid_errors",
            "homoskedastic_errors",
            "Gaussian_errors_for_exact_finite_sample_calibration",
            "valid_instrument_exogeneity_and_exclusion",
            "linear_single_endogenous_regressor_model",
        ],
        "warning": "This confidence set may be unbounded, disconnected, or empty; do not force a finite Wald interval.",
    }
