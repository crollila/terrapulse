"""Checks of the data reduction, the committed NASA series, and the API."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from terrapulse import analysis as an
from terrapulse.api import app
from terrapulse import data
from terrapulse.catalog import END_YEAR, REGIONS, START_YEAR
from terrapulse.power import MERRA2_VARIABLES, load_provenance, load_series, reduce_to_series

client = TestClient(app)


def _payload(cells):
    """Minimal NASA POWER regional response: cells = [(lat, lon, value)]"""
    feats = []
    for lat, lon, value in cells:
        vals = {f"{y}{m:02d}": value for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 14)}
        feats.append({"geometry": {"coordinates": [lon, lat, 0]}, "properties": {"parameter": {"X": vals}}})
    return {"features": feats, "header": {"fill_value": -999.0}}


def test_area_weighting_uses_cos_latitude():
    frame, grid = reduce_to_series(_payload([(0.0, 0.0, 10.0), (60.0, 0.0, 20.0)]), "X")
    # weights 1 and 0.5 -> (10 + 0.5 * 20) / 1.5
    assert frame["value"].iloc[0] == pytest.approx(40 / 3)
    assert grid["n_cells"] == 2
    assert len(frame) == (END_YEAR - START_YEAR + 1) * 12  # annual "month 13" dropped


def test_fill_values_are_missing_not_numbers():
    frame, _ = reduce_to_series(_payload([(0.0, 0.0, -999.0), (0.0, 1.0, 5.0)]), "X")
    assert frame["value"].iloc[0] == pytest.approx(5.0)
    assert frame["n_cells_valid"].iloc[0] == 1
    frame, _ = reduce_to_series(_payload([(0.0, 0.0, -999.0)]), "X")
    assert np.isnan(frame["value"].iloc[0])


@pytest.mark.parametrize("region", list(REGIONS))
def test_committed_nasa_series_are_complete_and_plausible(region):
    limits = {
        "T2M": (-45, 45),
        "PRECTOTCORR": (0, 40),
        "QV2M": (0, 30),
        "WS10M": (0, 25),
        "GWETROOT": (0, 1),
    }
    prov = load_provenance()["series"]
    for variable in MERRA2_VARIABLES:
        frame = load_series(region, variable)
        assert len(frame) == (END_YEAR - START_YEAR + 1) * 12
        assert frame["value"].notna().mean() > 0.98
        lo, hi = limits[variable]
        assert frame["value"].min() >= lo and frame["value"].max() <= hi
        record = prov[f"{region}/{variable}"]
        # wind speed is derived by POWER from MERRA-2 winds and is labelled ["MERRA2", "POWER"]
        assert "MERRA2" in record["sources"] and set(record["sources"]) <= {"MERRA2", "POWER"}
        assert "power.larc.nasa.gov" in record["request_url"]


def test_catalog_and_health():
    assert client.get("/api/health").json()["status"] == "ok"
    cat = client.get("/api/catalog").json()
    assert len(cat["regions"]) == len(REGIONS)
    assert [v["id"] for v in cat["variables"]] == data.available_variables()
    assert set(MERRA2_VARIABLES) <= {v["id"] for v in cat["variables"]}
    for r in cat["regions"]:
        lon0, lat0, lon1, lat1 = r["bbox"]
        assert 2 <= lon1 - lon0 <= 10 and 2 <= lat1 - lat0 <= 10


def test_analysis_payload_is_consistent():
    body = client.get("/api/analysis/upper-colorado/T2M").json()
    s, tr = body["series"], body["trend"]
    assert len(s["t"]) == len(s["value"]) == len(s["anomaly"]) == 540
    assert tr["ols"]["ci_low"] <= tr["ols"]["slope_per_decade"] <= tr["ols"]["ci_high"]
    # adjusted interval is at least as wide as the naive one
    assert tr["ols"]["ci_high"] - tr["ols"]["ci_low"] >= tr["ols"]["naive_ci_high"] - tr["ols"]["naive_ci_low"] - 1e-12
    assert tr["mann_kendall"]["p_value"] >= tr["mann_kendall"]["classic_p_value"] - 1e-15
    assert len(body["windows"]) == body["windows_summary"]["n_windows"] == 496
    full = [w for w in body["windows"] if w["start"] == START_YEAR and w["end"] == END_YEAR][0]
    assert full["slope_per_decade"] == pytest.approx(tr["ols"]["slope_per_decade"])
    assert full["p_value"] == pytest.approx(tr["ols"]["p_value"])
    assert body["verdict"]["code"] in {"robust", "date_sensitive", "mixed", "not_detected"}
    assert "MERRA2" in body["provenance"]["sources"]
    assert 0.98 <= body["quality"]["coverage"] <= 1


def test_custom_trend_and_errors():
    a = client.get("/api/trend/upper-colorado/T2M?start=1990&end=2020").json()
    w = [x for x in an.analysis("upper-colorado", "T2M")["windows"] if x["start"] == 1990 and x["end"] == 2020][0]
    assert a["ols"]["slope_per_decade"] == pytest.approx(w["slope_per_decade"])
    assert client.get("/api/trend/upper-colorado/T2M?start=2015&end=2020").status_code == 422
    assert client.get("/api/analysis/atlantis/T2M").status_code == 404
    assert client.get("/api/analysis/upper-colorado/NOPE").status_code == 404


def test_overview_applies_false_discovery_control():
    body = client.get("/api/overview/T2M").json()
    assert len(body["regions"]) == len(REGIONS)
    for r in body["regions"]:
        assert r["p_value_fdr"] >= r["p_value"] - 1e-15
    mt = body["multiple_testing"]
    assert mt["n_significant_fdr"] <= mt["n_significant_raw"]
