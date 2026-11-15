"""Second-opinion checks: grid weighting, the agreement rule, and the committed
GPCP / GISTEMP regional series."""

import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from terrapulse import analysis as an
from terrapulse import crosscheck as cc
from terrapulse import data, ndvi
from terrapulse.api import app
from terrapulse.catalog import REGIONS, VARIABLES

client = TestClient(app)


# ------------------------------------------------------------------ weighting


def test_overlap_weights_full_partial_and_outside_cells():
    lats = np.array([12.5, 10.0, 7.5])  # 2.5 degree cells, north to south
    lons = np.array([0.0, 2.5, 5.0])
    w = cc.overlap_weights(lats, lons, [1.25, 8.75, 3.75, 11.25], 1.25, 1.25)  # exactly the centre cell
    assert w[1, 1] == pytest.approx(2.5 * 2.5 * np.cos(np.deg2rad(10.0)))
    assert (np.delete(w.ravel(), 4) == 0).all()
    # a box covering the centre cell and the western half of the cell to its east
    w = cc.overlap_weights(lats, lons, [1.25, 8.75, 5.0, 11.25], 1.25, 1.25)
    assert w[1, 2] == pytest.approx(w[1, 1] / 2)


def test_overlap_weights_accept_longitudes_from_0_to_360():
    lats = np.array([38.75])
    east_positive = np.array([251.25, 253.75, 256.25])  # = -108.75, -106.25, -103.75
    a = cc.overlap_weights(lats, east_positive, REGIONS["upper-colorado"]["bbox"], 1.25, 1.25)
    b = cc.overlap_weights(lats, east_positive - 360.0, REGIONS["upper-colorado"]["bbox"], 1.25, 1.25)
    assert (a > 0).all() and a == pytest.approx(b)


def test_regional_series_is_a_weighted_mean_that_skips_missing_cells():
    grid = np.array([[[1.0, 3.0]], [[np.nan, 3.0]], [[np.nan, np.nan]]])
    w = np.array([[1.0, 3.0]])
    out = cc.regional_series(grid, w)
    assert out[0] == pytest.approx((1 * 1 + 3 * 3) / 4) and out[1] == pytest.approx(3.0) and np.isnan(out[2])


# ------------------------------------------------------------- agreement rule


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ((+0.5, +0.3, +0.7, True), (+0.4, +0.2, +0.6, True), "agrees"),
        ((-0.54, -0.64, -0.44, True), (-0.28, -0.37, -0.19, True), "direction_only"),
        ((+0.43, +0.30, +0.55, True), (+0.03, -0.08, +0.14, False), "not_confirmed"),
        ((-0.03, -0.16, +0.10, False), (+0.29, +0.21, +0.36, True), "missed"),
        ((+0.01, -0.05, +0.07, False), (-0.03, -0.08, +0.02, False), "agrees_none"),
        ((+0.3, +0.1, +0.5, True), (-0.3, -0.5, -0.1, True), "conflict"),
    ],
)
def test_classification(a, b, expected):
    assert cc.classify(*a, *b) == expected


def test_descriptions_state_what_was_found_without_claiming_a_cause():
    b = {"slope_per_decade": -0.282, "ci_low": -0.372, "ci_high": -0.192}
    text = cc.describe("direction_only", "GPCP v2.3", "mm/day", -0.541, b)
    assert "same direction" in text and "1.9 times as large" in text and "size as uncertain" in text
    weak = {"slope_per_decade": 0.028, "ci_low": -0.079, "ci_high": 0.135}
    assert "not significant" in cc.describe("not_confirmed", "GPCP v2.3", "mm/day", 0.426, weak)
    for code in ("agrees", "agrees_none", "direction_only", "not_confirmed", "missed", "conflict"):
        sentence = cc.describe(code, "X", "u", 1.0, b).lower()
        assert "because" not in sentence and "caused" not in sentence and "due to" not in sentence
    assert set(cc.LABELS) == {"agrees", "agrees_none", "direction_only", "not_confirmed", "missed", "conflict", "none"}


# ------------------------------------------------------------ committed files


@pytest.mark.parametrize("dataset_id", list(cc.DATASETS))
def test_committed_series_are_complete_and_documented(dataset_id):
    table = pd.read_csv(cc.DATA_DIR / f"{dataset_id}.csv")
    assert list(table.columns) == ["year", "month", *REGIONS]
    assert len(table) == 540 and (table["year"].iloc[0], table["year"].iloc[-1]) == (1981, 2025)
    assert table[list(REGIONS)].notna().all().all()
    lo, hi = {"gpcp": (0, 30), "gistemp": (-12, 12)}[dataset_id]  # mm/day; degrees C anomaly
    assert table[list(REGIONS)].min().min() >= lo and table[list(REGIONS)].max().max() <= hi
    record = json.loads((cc.DATA_DIR / "provenance.json").read_text(encoding="utf-8"))["datasets"][dataset_id]
    assert record["opendap_url"].startswith("https://psl.noaa.gov/") and record["retrieved_utc"] and record["citation"]
    assert set(record["regions"]) == set(REGIONS) and all(r["n_cells"] >= 4 for r in record["regions"].values())


def test_every_analysis_says_whether_a_second_dataset_was_checked():
    an.clear_caches()
    for variable in ("T2M", "PRECTOTCORR", "QV2M", "WS10M", "GWETROOT"):
        body = client.get(f"/api/analysis/upper-colorado/{variable}").json()
        check = body["crosscheck"]
        assert check["code"] in cc.LABELS and check["label"] == cc.LABELS[check["code"]] and check["text"]
        if variable in cc.BY_VARIABLE:
            assert check["code"] != "none"
            assert check["trend"]["ci_low"] <= check["trend"]["slope_per_decade"] <= check["trend"]["ci_high"]
            assert check["period"] == body["period"] and check["trend"]["n_months"] == 540
            assert check["dataset"]["url"].startswith("https://") and check["dataset"]["citation"]
            assert 0.5 < check["anomaly_correlation"] <= 1  # the two records move together month to month
        else:
            assert check["code"] == "none" and "not been compared" in check["text"]
    overview = client.get("/api/overview/PRECTOTCORR").json()
    assert {r["crosscheck"] for r in overview["regions"]} <= set(cc.LABELS)


def test_published_cross_check_results():
    """The agreement statements quoted in the README. A data refresh that changes one must change the README too."""
    an.clear_caches()
    expected = {
        ("rondonia", "PRECTOTCORR"): "direction_only",
        ("malay-peninsula", "PRECTOTCORR"): "not_confirmed",
        ("punjab-plain", "PRECTOTCORR"): "not_confirmed",
        ("central-sahel", "PRECTOTCORR"): "agrees",
        ("north-slope", "PRECTOTCORR"): "agrees",
        ("moroccan-atlas", "PRECTOTCORR"): "agrees_none",
        ("murray-darling", "PRECTOTCORR"): "agrees_none",
        ("upper-colorado", "PRECTOTCORR"): "missed",
        ("north-slope", "T2M"): "agrees",
        ("upper-colorado", "T2M"): "agrees",
        ("moroccan-atlas", "T2M"): "agrees",
        ("central-sahel", "T2M"): "agrees",
        ("malay-peninsula", "T2M"): "agrees",
        ("murray-darling", "T2M"): "agrees",
        ("rondonia", "T2M"): "direction_only",
        ("punjab-plain", "T2M"): "missed",
    }
    found = {key: an.analysis(*key)["crosscheck"]["code"] for key in expected}
    assert found == expected
    rondonia = an.analysis("rondonia", "PRECTOTCORR")
    assert rondonia["crosscheck"]["trend"]["slope_per_decade"] == pytest.approx(-0.282, abs=2e-3)
    assert rondonia["trend"]["ols"]["slope_per_decade"] == pytest.approx(-0.541, abs=2e-3)


# ------------------------------------------------------- known data issues


def test_documented_amazon_rainfall_break_is_tested_against_the_committed_series():
    """Reichle et al. (2017): MERRA-2 corrected rainfall drops against GPCP in the Amazon from 2005.

    The numbers below are quoted in the README, the methodology and the submission text.
    """
    an.clear_caches()
    check = an.analysis("rondonia", "PRECTOTCORR")["crosscheck"]
    issue = check["known_issue"]
    assert check["code"] == "direction_only"
    assert issue["break_year"] == 2005 == issue["best_fit_break_year"]  # the documented year is also the best fit
    assert issue["gap_before"] == pytest.approx(-0.13, abs=0.01) and issue["gap_after"] == pytest.approx(-0.99, abs=0.01)
    assert issue["step"]["value"] == pytest.approx(-1.07, abs=0.01)
    assert issue["step"]["ci_low"] == pytest.approx(-1.51, abs=0.01) and issue["step"]["ci_high"] == pytest.approx(-0.63, abs=0.01)
    assert issue["drift_per_decade"]["ci_low"] < 0 < issue["drift_per_decade"]["ci_high"]  # nothing left but the jump
    before, after = issue["periods"]
    assert (before["start"], before["end"], after["start"], after["end"]) == (1981, 2004, 2005, 2025)
    assert before["main"]["slope_per_decade"] == pytest.approx(-0.14, abs=0.01)
    assert before["independent"]["slope_per_decade"] == pytest.approx(-0.14, abs=0.01)
    assert not before["main"]["significant"] and not before["independent"]["significant"]
    assert after["main"]["slope_per_decade"] == pytest.approx(-0.59, abs=0.01)
    assert after["independent"]["slope_per_decade"] == pytest.approx(-0.83, abs=0.01)
    assert after["main"]["significant"] and after["independent"]["significant"]
    assert before["ranges_overlap"] and after["ranges_overlap"]
    text = issue["text"]
    assert "Reichle et al. 2017" in text and "not a validated change" in text and "size is not confirmed" in text
    assert "deforestation" not in text.lower() and "caused" not in text.lower()  # no cause of the rainfall change is claimed
    assert len(issue["sources"]) == 3 and all(s["url"].startswith("https://") and s["label"] for s in issue["sources"])
    served = client.get("/api/analysis/rondonia/PRECTOTCORR").json()["crosscheck"]["known_issue"]
    assert served["id"] == issue["id"] and served["text"] == text


def test_known_issues_are_shown_only_where_one_is_documented():
    an.clear_caches()
    flagged = {(r, v) for r in REGIONS for v in data.available_variables() if "known_issue" in an.analysis(r, v)["crosscheck"]}
    assert flagged == set(cc.KNOWN_ISSUES) == {("rondonia", "PRECTOTCORR"), ("rondonia", "GWETROOT")}
    soil = an.analysis("rondonia", "GWETROOT")["crosscheck"]
    assert soil["code"] == "none" and "break_year" not in soil["known_issue"]
    assert "has not tested" in soil["known_issue"]["text"]  # an untested caveat must say so


def test_best_break_year_finds_a_planted_step():
    year = np.repeat(np.arange(1981, 2026), 12)
    t = year + (np.tile(np.arange(1, 13), 45) - 0.5) / 12
    rng = np.random.default_rng(3)
    y = np.where(year >= 1997, -0.8, 0.0) + rng.normal(0, 0.3, len(t))
    assert cc.best_break_year(t, year, y) == 1997


# -------------------------------------------------------------- region boxes


def test_region_descriptions_match_the_land_actually_in_the_box():
    """land_share in the catalog is checked against the 0.2 degree NDVI grid when those files are present."""
    for region_id, region in REGIONS.items():
        assert 0 < region["land_share"] <= 1
        if region["land_share"] < 0.9:
            assert "sea" in region["setting"].lower()
    if not ndvi.available():
        pytest.skip("NDVI regional files not present")
    for region_id, region in REGIONS.items():
        lon0, lat0, lon1, lat1 = region["bbox"]
        in_box = round((lon1 - lon0) / 0.2) * round((lat1 - lat0) / 0.2)
        land = int(pd.read_csv(ndvi.NDVI_DIR / f"{region_id}.csv")["NDVI_cells_total"].iloc[0])
        assert region["land_share"] == pytest.approx(land / in_box, abs=0.01), region_id


def test_variables_without_a_second_dataset_are_named():
    assert set(cc.BY_VARIABLE) == {"PRECTOTCORR", "T2M"}
    assert set(VARIABLES) - set(cc.BY_VARIABLE) == {"QV2M", "WS10M", "GWETROOT", "NDVI"}
