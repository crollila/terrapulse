"""Trend statistics for monthly Earth-system time series.

All functions are pure (arrays in, plain numbers out) so they can be tested
against synthetic series with known answers. See docs/METHODOLOGY.md.

References
----------
Santer et al. (2008), Int. J. Climatol. 28, 1703-1722  (AR(1) effective sample size)
Mann (1945); Kendall (1975)                             (Mann-Kendall test)
Hamed & Rao (1998), J. Hydrol. 204, 182-196             (autocorrelation-corrected MK)
Sen (1968), J. Am. Stat. Assoc. 63, 1379-1389           (Theil-Sen slope)
Weatherhead et al. (1998), J. Geophys. Res. 103, 17149  (years needed to detect a trend)
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

ALPHA = 0.05


def monthly_climatology(months: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Mean of each calendar month (index 0 = January), ignoring NaN."""
    clim = np.full(12, np.nan)
    for m in range(1, 13):
        sel = values[months == m]
        if np.isfinite(sel).any():
            clim[m - 1] = np.nanmean(sel)
    return clim


def deseasonalize(months: np.ndarray, values: np.ndarray, clim: np.ndarray | None = None) -> np.ndarray:
    """Anomalies: each value minus the mean of its calendar month."""
    if clim is None:
        clim = monthly_climatology(months, values)
    return values - clim[months - 1]


def lag1_autocorrelation(x: np.ndarray) -> float:
    """Lag-1 autocorrelation of an evenly spaced series (standard biased estimator)."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom == 0 or len(x) < 3:
        return 0.0
    return float(np.dot(x[:-1], x[1:]) / denom)


def lag1_autocorrelation_at(t: np.ndarray, x: np.ndarray) -> float:
    """Lag-1 autocorrelation of a series observed at times ``t`` that may have gaps.

    For an evenly spaced series this is exactly ``lag1_autocorrelation``. When
    months are missing, only pairs of truly consecutive time steps are used, so
    a jump across a gap is not mistaken for a one-step lag. The estimate is
    scaled so that it reduces to the standard estimator when nothing is missing.
    """
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return 0.0
    steps = np.diff(t)
    adjacent = steps < 1.5 * steps.min()
    if adjacent.all():
        return lag1_autocorrelation(x)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    n_pairs = int(adjacent.sum())
    if denom == 0 or n_pairs < 2:
        return 0.0
    num = float(np.dot(x[:-1][adjacent], x[1:][adjacent]))
    r1 = (num / n_pairs) / (denom / n) * ((n - 1) / n)
    return float(min(max(r1, -1.0), 1.0))


def mask_sparse_calendar_months(months: np.ndarray, values: np.ndarray, min_fraction: float = 0.8) -> tuple[np.ndarray, list[int]]:
    """Drop calendar months that are missing in too many years.

    If, say, November has data in only a third of the years, its anomalies come
    from a different mix of years than the other months, and a change in data
    availability over time could masquerade as a trend. Such calendar months
    are set to NaN in every year. Returns (values, excluded month numbers).
    A complete series is returned unchanged.
    """
    values = np.asarray(values, dtype=float)
    out = values.copy()
    excluded: list[int] = []
    for m in range(1, 13):
        sel = months == m
        if not sel.any():
            continue
        share = float(np.isfinite(values[sel]).mean())
        if share < min_fraction:
            out[sel] = np.nan
            if share > 0:
                excluded.append(m)
    return out, excluded


def ols_trend(t: np.ndarray, y: np.ndarray, alpha: float = ALPHA) -> dict:
    """Least-squares linear trend with an AR(1)-adjusted t-test.

    The naive OLS standard error assumes independent residuals. Monthly climate
    anomalies are autocorrelated, so the sample size is replaced by an effective
    sample size n_eff = n (1 - r1) / (1 + r1), where r1 is the lag-1
    autocorrelation of the residuals (Santer et al. 2008). Negative r1 is treated
    as zero so the adjustment can only widen the interval. Missing values (NaN)
    are dropped; r1 is then estimated from truly consecutive months only.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(t) & np.isfinite(y)
    t, y = t[ok], y[ok]
    n = len(y)
    if n < 8:
        raise ValueError("need at least 8 valid points for a trend")
    tm = t.mean()
    sxx = float(np.sum((t - tm) ** 2))
    slope = float(np.sum((t - tm) * (y - y.mean())) / sxx)
    intercept = float(y.mean() - slope * tm)
    resid = y - (intercept + slope * t)
    sse = float(np.sum(resid**2))
    se_naive = math.sqrt(sse / (n - 2) / sxx)

    r1 = lag1_autocorrelation_at(t, resid)
    r1_used = min(max(r1, 0.0), 0.99)
    n_eff = max(3.0, n * (1 - r1_used) / (1 + r1_used))
    se_adj = math.sqrt(sse / (n_eff - 2) / sxx)

    def _ci_p(se: float, df: float) -> tuple[float, float, float]:
        if se == 0:
            return slope, slope, 0.0 if slope != 0 else 1.0
        tcrit = float(sps.t.ppf(1 - alpha / 2, df))
        p = float(2 * sps.t.sf(abs(slope / se), df))
        return slope - tcrit * se, slope + tcrit * se, p

    lo_n, hi_n, p_n = _ci_p(se_naive, n - 2)
    lo_a, hi_a, p_a = _ci_p(se_adj, n_eff - 2)
    sst = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": n,
        "slope": slope,
        "intercept": intercept,
        "r_squared": 0.0 if sst == 0 else 1 - sse / sst,
        "residual_std": math.sqrt(sse / (n - 2)),
        "lag1_autocorrelation": r1,
        "n_effective": n_eff,
        "naive": {"se": se_naive, "ci_low": lo_n, "ci_high": hi_n, "p_value": p_n},
        "adjusted": {"se": se_adj, "ci_low": lo_a, "ci_high": hi_a, "p_value": p_a},
    }


def level_shift(t: np.ndarray, y: np.ndarray, after: np.ndarray, alpha: float = ALPHA) -> dict:
    """Size of a step in ``y`` at a known date, with a steady drift allowed.

    Fits ``y = a + b (t - mean t) + c * after`` by least squares, where ``after``
    is False before the date and True from it on; ``c`` is the step and ``b`` the
    drift. Standard errors allow for month-to-month persistence in the same way
    as ols_trend: the residual variance uses the effective sample size
    n_eff = n (1 - r1) / (1 + r1).

    The date must come from outside the data (a documented change in a dataset).
    Picking the date that fits best and then testing it would overstate the evidence.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    after = np.asarray(after, dtype=bool)
    ok = np.isfinite(t) & np.isfinite(y)
    t, y, after = t[ok], y[ok], after[ok]
    n = len(y)
    if n < 24 or after.sum() < 12 or (~after).sum() < 12:
        raise ValueError("need at least 12 valid points on each side of the date")
    design = np.column_stack([np.ones(n), t - t.mean(), after.astype(float)])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    sse = float(resid @ resid)
    r1 = lag1_autocorrelation_at(t, resid)
    r1_used = min(max(r1, 0.0), 0.99)
    n_eff = max(5.0, n * (1 - r1_used) / (1 + r1_used))
    df = n_eff - 3
    se = np.sqrt(np.diag(np.linalg.inv(design.T @ design)) * sse / df)
    tcrit = float(sps.t.ppf(1 - alpha / 2, df))

    def _term(i: int) -> dict:
        value, err = float(beta[i]), float(se[i])
        p = 1.0 if err == 0 and value == 0 else (0.0 if err == 0 else float(2 * sps.t.sf(abs(value / err), df)))
        return {"value": value, "se": err, "ci_low": value - tcrit * err, "ci_high": value + tcrit * err, "p_value": p}

    return {
        "n": n,
        "step": _term(2),
        "drift_per_year": _term(1),
        "lag1_autocorrelation": r1,
        "n_effective": n_eff,
        "sse": sse,
    }


def _mk_score(x: np.ndarray) -> float:
    n = len(x)
    s = 0.0
    for k in range(n - 1):
        s += float(np.sign(x[k + 1 :] - x[k]).sum())
    return s


def _mk_variance(x: np.ndarray) -> float:
    n = len(x)
    _, counts = np.unique(x, return_counts=True)
    ties = float(np.sum(counts * (counts - 1) * (2 * counts + 5)))
    return (n * (n - 1) * (2 * n + 5) - ties) / 18.0


def _acf(x: np.ndarray, nlags: int) -> np.ndarray:
    y = x - x.mean()
    n = len(x)
    acov = np.correlate(y, y, "full")[n - 1 :] / n
    return acov[: nlags + 1] / acov[0]


def sen_slope_per_step(x: np.ndarray) -> float:
    """Median of all pairwise slopes for an evenly spaced series (per time step)."""
    n = len(x)
    idx = np.arange(n)
    i, j = np.triu_indices(n, k=1)
    return float(np.median((x[j] - x[i]) / (idx[j] - idx[i])))


def mann_kendall(
    y: np.ndarray,
    alpha: float = ALPHA,
    max_lag: int | None = 24,
    conservative: bool = True,
) -> dict:
    """Mann-Kendall trend test, classic and Hamed-Rao (1998) corrected.

    NaN values are dropped and the remaining values are treated as consecutive.
    For a series with gaps that is an approximation in the persistence
    correction (the S statistic itself needs only the order). The Hamed-Rao
    correction inflates the variance of S using the significant autocorrelations
    of the ranks of the Sen-detrended series, up to ``max_lag`` steps
    (``None`` = all lags, as in the pymannkendall default). With
    ``conservative=True`` the correction factor is never allowed below 1, so the
    correction cannot make a trend look more significant than the classic test.
    """
    x = np.asarray(y, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 8:
        raise ValueError("need at least 8 valid points for Mann-Kendall")
    s = _mk_score(x)
    var_s = _mk_variance(x)
    tau = s / (0.5 * n * (n - 1))

    def _z(v: float) -> float:
        if v <= 0 or s == 0:
            return 0.0
        return (s - 1) / math.sqrt(v) if s > 0 else (s + 1) / math.sqrt(v)

    z_classic = _z(var_s)
    p_classic = float(2 * sps.norm.sf(abs(z_classic)))

    lag = n if max_lag is None else min(max_lag + 1, n)
    detrended = x - np.arange(1, n + 1) * sen_slope_per_step(x)
    ranks = sps.rankdata(detrended)
    acf = _acf(ranks, lag - 1)
    bound = float(sps.norm.ppf(1 - alpha / 2)) / math.sqrt(n)
    sni = 0.0
    for i in range(1, lag):
        if abs(acf[i]) > bound:
            sni += (n - i) * (n - i - 1) * (n - i - 2) * acf[i]
    factor = 1 + (2 / (n * (n - 1) * (n - 2))) * sni
    if conservative:
        factor = max(factor, 1.0)
    z_hr = _z(var_s * factor)
    p_hr = float(2 * sps.norm.sf(abs(z_hr)))
    return {
        "n": n,
        "s": s,
        "tau": float(tau),
        "classic": {"z": float(z_classic), "p_value": p_classic},
        "hamed_rao": {"z": float(z_hr), "p_value": p_hr, "variance_factor": float(factor)},
    }


def theil_sen(t: np.ndarray, y: np.ndarray, alpha: float = ALPHA) -> dict:
    """Theil-Sen median slope with its rank-based confidence interval.

    The interval assumes independent values, so for autocorrelated monthly data
    it is narrower than it should be; the AR(1)-adjusted OLS interval is the
    headline interval.
    """
    ok = np.isfinite(t) & np.isfinite(y)
    res = sps.theilslopes(y[ok], t[ok], alpha=1 - alpha)
    return {
        "slope": float(res[0]),
        "intercept": float(res[1]),
        "ci_low": float(res[2]),
        "ci_high": float(res[3]),
    }


def years_to_detect(slope_per_year: float, noise_std: float, phi: float, record_years: float) -> dict:
    """Years of monthly data needed to detect a trend (Weatherhead et al. 1998, eq. 3).

    n* = [ (3.3 sigma_N / |omega|) sqrt((1 + phi) / (1 - phi)) ] ^ (2/3)

    is the record length giving a 90% chance of detecting a real trend of size
    omega (per year) at the 95% confidence level, given monthly noise with
    standard deviation sigma_N and lag-1 autocorrelation phi. The uncertainty
    range is n* exp(+-B) with B = (4 / (3 sqrt(M))) sqrt((1 + phi) / (1 - phi)),
    M = months of data used to estimate sigma_N and phi.
    """
    phi_used = min(max(phi, 0.0), 0.95)
    omega = abs(slope_per_year)
    if omega == 0 or noise_std == 0:
        return {"years_needed": None, "low": None, "high": None, "record_years": record_years, "more_years": None}
    ar = math.sqrt((1 + phi_used) / (1 - phi_used))
    n_star = (3.3 * noise_std / omega * ar) ** (2 / 3)
    b = 4 / (3 * math.sqrt(record_years * 12)) * ar
    return {
        "years_needed": n_star,
        "low": n_star * math.exp(-b),
        "high": n_star * math.exp(b),
        "record_years": record_years,
        "more_years": max(0.0, n_star - record_years),
    }
