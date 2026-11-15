"""Numerical checks of the statistics against independent references:
statsmodels (OLS), pymannkendall (Mann-Kendall, Sen), hand calculations, and
synthetic series with known trends. Synthetic data appear only in tests.
"""

import math

import numpy as np
import pymannkendall as pmk
import pytest
import statsmodels.api as sm

from terrapulse import stats


def _time(n_years=40):
    year = np.repeat(np.arange(1981, 1981 + n_years), 12)
    month = np.tile(np.arange(1, 13), n_years)
    return year, month, year + (month - 0.5) / 12


def _ar1(rng, n, phi, sigma=1.0):
    e = rng.normal(0, sigma, n)
    x = np.zeros(n)
    x[0] = e[0] / math.sqrt(1 - phi**2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_ols_matches_statsmodels():
    rng = np.random.default_rng(1)
    _, _, t = _time()
    y = 0.03 * (t - t[0]) + rng.normal(0, 0.5, len(t))
    ours = stats.ols_trend(t, y)
    ref = sm.OLS(y, sm.add_constant(t)).fit()
    assert ours["slope"] == pytest.approx(ref.params[1], rel=1e-9)
    assert ours["intercept"] == pytest.approx(ref.params[0], rel=1e-9)
    assert ours["naive"]["se"] == pytest.approx(ref.bse[1], rel=1e-9)
    assert ours["naive"]["p_value"] == pytest.approx(ref.pvalues[1], rel=1e-6)
    lo, hi = ref.conf_int()[1]
    assert ours["naive"]["ci_low"] == pytest.approx(lo, rel=1e-6)
    assert ours["naive"]["ci_high"] == pytest.approx(hi, rel=1e-6)
    assert ours["r_squared"] == pytest.approx(ref.rsquared, rel=1e-9)


def test_known_slope_is_recovered_inside_interval():
    rng = np.random.default_rng(2)
    _, _, t = _time()
    y = 0.02 * t + rng.normal(0, 0.3, len(t))
    res = stats.ols_trend(t, y)
    assert res["adjusted"]["ci_low"] < 0.02 < res["adjusted"]["ci_high"]
    assert res["adjusted"]["p_value"] < 0.001


def test_ols_ignores_missing_values():
    rng = np.random.default_rng(3)
    _, _, t = _time()
    y = 0.02 * t + rng.normal(0, 0.3, len(t))
    y_gap = y.copy()
    y_gap[10:20] = np.nan
    keep = np.isfinite(y_gap)
    assert stats.ols_trend(t, y_gap)["slope"] == pytest.approx(stats.ols_trend(t[keep], y[keep])["slope"])


def test_autocorrelation_widens_interval_and_never_narrows_it():
    rng = np.random.default_rng(4)
    _, _, t = _time()
    red = stats.ols_trend(t, _ar1(rng, len(t), 0.7))
    assert red["lag1_autocorrelation"] == pytest.approx(0.7, abs=0.1)
    assert red["n_effective"] < 0.35 * red["n"]
    assert red["adjusted"]["se"] > 2 * red["naive"]["se"]
    # negatively autocorrelated residuals must not shrink the interval
    alt = stats.ols_trend(t, np.tile([1.0, -1.0], len(t) // 2) + rng.normal(0, 0.1, len(t)))
    assert alt["lag1_autocorrelation"] < 0
    assert alt["adjusted"]["se"] == pytest.approx(alt["naive"]["se"])


def test_false_positive_rate_on_trendless_red_noise():
    """With no real trend, ~5% of series should test significant. The naive
    test fails this badly on autocorrelated noise; the adjusted test does not."""
    rng = np.random.default_rng(5)
    _, _, t = _time(30)
    naive = adjusted = 0
    n_sim = 400
    for _ in range(n_sim):
        res = stats.ols_trend(t, _ar1(rng, len(t), 0.6))
        naive += res["naive"]["p_value"] < 0.05
        adjusted += res["adjusted"]["p_value"] < 0.05
    assert naive / n_sim > 0.25
    assert adjusted / n_sim < 0.09


@pytest.mark.parametrize("seed,slope,ties", [(10, 0.0, False), (11, 0.004, False), (12, -0.01, True)])
def test_mann_kendall_matches_pymannkendall(seed, slope, ties):
    rng = np.random.default_rng(seed)
    n = 240
    y = slope * np.arange(n) + _ar1(rng, n, 0.4)
    if ties:
        y = np.round(y, 1)
    ours = stats.mann_kendall(y, max_lag=None, conservative=False)
    ref = pmk.original_test(y)
    assert ours["s"] == pytest.approx(ref.s)
    assert ours["tau"] == pytest.approx(ref.Tau)
    assert ours["classic"]["z"] == pytest.approx(ref.z, rel=1e-9, abs=1e-12)
    assert ours["classic"]["p_value"] == pytest.approx(ref.p, rel=1e-6, abs=1e-12)
    ref_hr = pmk.hamed_rao_modification_test(y)
    assert ours["hamed_rao"]["z"] == pytest.approx(ref_hr.z, rel=1e-6, abs=1e-9)
    assert ours["hamed_rao"]["p_value"] == pytest.approx(ref_hr.p, rel=1e-5, abs=1e-12)
    ref_lag = pmk.hamed_rao_modification_test(y, lag=24)
    ours_lag = stats.mann_kendall(y, max_lag=24, conservative=False)
    assert ours_lag["hamed_rao"]["z"] == pytest.approx(ref_lag.z, rel=1e-6, abs=1e-9)


def test_mann_kendall_conservative_never_more_significant_than_classic():
    rng = np.random.default_rng(13)
    for _ in range(20):
        y = 0.002 * np.arange(200) + _ar1(rng, 200, rng.uniform(-0.5, 0.8))
        res = stats.mann_kendall(y)
        assert res["hamed_rao"]["p_value"] >= res["classic"]["p_value"] - 1e-15


def test_sen_slope_matches_pymannkendall_and_scipy_path():
    rng = np.random.default_rng(14)
    y = 0.05 * np.arange(120) + rng.normal(0, 1, 120)
    assert stats.sen_slope_per_step(y) == pytest.approx(pmk.sens_slope(y).slope)
    t = np.arange(120) / 12.0
    ts = stats.theil_sen(t, y)
    assert ts["slope"] == pytest.approx(pmk.sens_slope(y).slope * 12)
    assert ts["ci_low"] < 0.6 < ts["ci_high"]


def test_deseasonalize_removes_a_pure_seasonal_cycle():
    _, month, t = _time(20)
    seasonal = 10 * np.sin(2 * np.pi * (month - 1) / 12)
    y = seasonal + 0.05 * (t - t.mean())
    anomalies = stats.deseasonalize(month, y)
    # what is left is the trend (to within the small trend-in-climatology offset)
    assert np.abs(anomalies - 0.05 * (t - t.mean())).max() < 0.05
    assert stats.ols_trend(t, anomalies)["slope"] == pytest.approx(0.05, rel=0.01)
    # raw series: the seasonal cycle swamps the trend
    assert stats.ols_trend(t, y)["residual_std"] > 50 * stats.ols_trend(t, anomalies)["residual_std"]


def test_level_shift_matches_statsmodels_and_recovers_a_known_step():
    rng = np.random.default_rng(7)
    year, _, t = _time(45)
    after = year >= 2005
    y = 0.02 * (t - t[0]) - 1.0 * after + rng.normal(0, 0.6, len(t))
    ours = stats.level_shift(t, y, after)
    ref = sm.OLS(y, np.column_stack([np.ones(len(t)), t - t.mean(), after.astype(float)])).fit()
    assert ours["step"]["value"] == pytest.approx(ref.params[2], rel=1e-9)
    assert ours["drift_per_year"]["value"] == pytest.approx(ref.params[1], rel=1e-9)
    assert ours["step"]["ci_low"] < -1.0 < ours["step"]["ci_high"] and ours["step"]["p_value"] < 0.001
    assert ours["drift_per_year"]["ci_low"] < 0.02 < ours["drift_per_year"]["ci_high"]
    # with independent noise the adjusted standard error is close to the textbook one
    assert ours["step"]["se"] == pytest.approx(ref.bse[2], rel=0.15)


def test_level_shift_does_not_mistake_a_steady_trend_for_a_step():
    rng = np.random.default_rng(11)
    year, _, t = _time(45)
    after = year >= 2005
    y = -0.05 * (t - t[0]) + _ar1(rng, len(t), 0.6, 0.5)  # a trend with persistence, and no step
    fit = stats.level_shift(t, y, after)
    assert fit["step"]["ci_low"] < 0 < fit["step"]["ci_high"]
    assert fit["drift_per_year"]["ci_low"] < -0.05 < fit["drift_per_year"]["ci_high"]
    naive = sm.OLS(y, np.column_stack([np.ones(len(t)), t - t.mean(), after.astype(float)])).fit()
    assert fit["step"]["se"] > 1.5 * naive.bse[2]  # persistence widens the range
    with pytest.raises(ValueError):
        stats.level_shift(t[:20], y[:20], after[:20])


def test_years_to_detect_hand_calculation():
    # sigma 1, trend 0.1/yr, no autocorrelation: (3.3 * 10)^(2/3) = 10.288
    res = stats.years_to_detect(0.1, 1.0, 0.0, 30)
    assert res["years_needed"] == pytest.approx(33 ** (2 / 3))
    assert res["years_needed"] == pytest.approx(10.288, abs=0.001)
    assert res["more_years"] == 0
    # phi 0.5 multiplies the bracket by sqrt(3)
    res2 = stats.years_to_detect(0.1, 1.0, 0.5, 5)
    assert res2["years_needed"] == pytest.approx((33 * math.sqrt(3)) ** (2 / 3))
    assert res2["more_years"] == pytest.approx(res2["years_needed"] - 5)
    assert res2["low"] < res2["years_needed"] < res2["high"]
    # smaller trend or noisier data takes longer
    assert stats.years_to_detect(0.05, 1.0, 0.0, 30)["years_needed"] > res["years_needed"]
    assert stats.years_to_detect(0.1, 2.0, 0.0, 30)["years_needed"] > res["years_needed"]
    assert stats.years_to_detect(0.0, 1.0, 0.0, 30)["years_needed"] is None
