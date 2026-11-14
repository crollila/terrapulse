"""Second-opinion checks: grid weighting, the agreement rule, and the committed
GPCP / GISTEMP regional series."""

import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from terrapulse import analysis as an
from terrapulse import crosscheck as cc
from terrapulse import ndvi
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
