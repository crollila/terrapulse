"""NDVI (MOD13C2) path: file validation, regional reduction, gaps, and that the
existing MERRA-2 variables are untouched.

Every NDVI number in this file is SYNTHETIC and exists only inside pytest's
temporary directories. Nothing here writes to backend/data/ or to the static
export, so no invented observation can reach the deployed dashboard.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from terrapulse import analysis as an
from terrapulse import data, ndvi, ndvi_regions, stats
from terrapulse.api import app
from terrapulse.catalog import REGIONS, VARIABLES
from terrapulse.power import MERRA2_VARIABLES

client = TestClient(app)

N_MONTHS = 321  # February 2000 .. October 2026, as delivered by MOD13C2 v6.1
STATIC = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


def month_table(n: int = N_MONTHS, first=(2000, 2)) -> tuple[np.ndarray, np.ndarray]:
    idx = first[0] * 12 + (first[1] - 1) + np.arange(n)
    return idx // 12, idx % 12 + 1


def synthetic_region_frame(seed: int, slope_per_decade: float = 0.02, total: int = 700) -> pd.DataFrame:
    """Seasonal cycle + linear trend + AR(1) noise. Test fixture, not data."""
    rng = np.random.default_rng(seed)
    year, month = month_table()
    t = year + (month - 0.5) / 12
    noise = np.zeros(N_MONTHS)
    for i in range(1, N_MONTHS):
        noise[i] = 0.4 * noise[i - 1] + rng.normal(0, 0.012)
    values = 0.45 + 0.18 * np.sin(2 * np.pi * (month - 4) / 12) + slope_per_decade / 10 * (t - t.mean()) + noise
    return pd.DataFrame(
        {"year": year, "month": month, "NDVI": np.clip(values, -0.2, 1.0), "NDVI_cells": total, "NDVI_cells_total": total}
    )


def provenance_stub(first="2000-02", last="2026-10") -> dict:
    return {
        "product": "MOD13C2",
        "version": "061",
        "first_month": first,
        "last_month": last,
        "processed_by": "pytest synthetic fixture",
        "processing": {"quality_filter": "synthetic fixture", "resampling": "none"},
    }


def write_dataset(directory: Path, frames: dict[str, pd.DataFrame], prov: dict | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for region_id, frame in frames.items():
        frame.to_csv(directory / f"{region_id}.csv", index=False, float_format="%.5f")
    (directory / "provenance.json").write_text(json.dumps(prov or provenance_stub()), encoding="utf-8")


@pytest.fixture
def ndvi_dir(tmp_path, monkeypatch):
    """Point the loader at an empty temporary directory and reset caches around the test."""
    target = tmp_path / "ndvi"
    monkeypatch.setattr(ndvi, "NDVI_DIR", target)
    an.clear_caches()
    yield target
    an.clear_caches()


@pytest.fixture
def synthetic_ndvi(ndvi_dir):
    frames = {region_id: synthetic_region_frame(seed=i) for i, region_id in enumerate(REGIONS)}
    write_dataset(ndvi_dir, frames)
    return frames


# --------------------------------------------------------------- availability


def test_ndvi_is_not_served_until_real_files_exist(ndvi_dir):
    assert not ndvi.available()
    assert data.available_variables() == MERRA2_VARIABLES
    cat = client.get("/api/catalog").json()
    assert [v["id"] for v in cat["variables"]] == MERRA2_VARIABLES
    assert list(cat["sources"]) == ["merra2"]
    assert client.get("/api/analysis/upper-colorado/NDVI").status_code == 404
    assert client.get("/api/overview/NDVI").status_code == 404
    assert "ndvi" not in client.get("/api/provenance").json()


def test_committed_ndvi_files_are_real_and_valid_if_present():
    """Runs against backend/data/ndvi once a teammate delivers it; CI then blocks a bad delivery."""
    an.clear_caches()
    if not ndvi.NDVI_DIR.exists():
        pytest.skip("NDVI regional files have not been delivered yet")
    status = ndvi.status()
    assert status["available"], status.get("reason")
    prov = ndvi.load_provenance()
    assert "synthetic" not in json.dumps(prov).lower() and "pytest" not in json.dumps(prov).lower()
    assert status["first_month"] >= "2000-02"
    for region_id in REGIONS:
        frame = ndvi.load_series(region_id)
        assert frame["value"].min() >= ndvi.VALID_MIN and frame["value"].max() <= ndvi.VALID_MAX
        # A polar or snowy region legitimately loses its dark and snow-covered months, so no
        # minimum share of months is demanded. What matters is that enough remains for a trend:
        # at least three calendar months, observed in most years.
        body = an.analysis(region_id, "NDVI")
        used = [m for m, a in zip(body["series"]["month"], body["series"]["anomaly"]) if a is not None]
        assert len(set(used)) >= 3, region_id
        assert body["quality"]["months_used"] == len(used) >= 60, region_id


def test_static_export_contains_ndvi_only_when_data_is_available():
    an.clear_caches()
    exported = (STATIC / "overview" / "NDVI.json").exists()
    assert exported == ndvi.available()
    listed = "NDVI" in [v["id"] for v in json.loads((STATIC / "catalog.json").read_text(encoding="utf-8"))["variables"]]
    assert listed == ndvi.available()


# ------------------------------------------------------------ file validation


def test_valid_file_passes_and_keeps_all_months():
    frame = ndvi.validate_frame(synthetic_region_frame(1))
    assert len(frame) == N_MONTHS
    assert (frame["year"].iloc[0], frame["month"].iloc[0]) == (2000, 2)
    assert (frame["year"].iloc[-1], frame["month"].iloc[-1]) == (2026, 10)


def _broken(kind: str) -> pd.DataFrame:
    f = synthetic_region_frame(2)
    if kind == "raw_integers":
        f["NDVI"] = (f["NDVI"] * 10000).round()
    elif kind == "fill_averaged_in":
        f.loc[5, "NDVI"] = -0.3
    elif kind == "skipped_month":
        f = f.drop(index=40).reset_index(drop=True)
    elif kind == "duplicate_month":
        f = pd.concat([f.iloc[:10], f.iloc[9:]]).reset_index(drop=True)
    elif kind == "starts_before_terra":
        f["year"] = f["year"] - 1
    elif kind == "missing_column":
        f = f.drop(columns=["NDVI_cells_total"])
    elif kind == "cells_exceed_total":
        f.loc[3, "NDVI_cells"] = 9999
    elif kind == "value_without_cells":
        f.loc[3, "NDVI_cells"] = 0
    elif kind == "cells_without_value":
        f.loc[3, "NDVI"] = np.nan
    elif kind == "total_changes":
        f.loc[3, "NDVI_cells_total"] = 650
    elif kind == "month_13":
        f.loc[0, "month"] = 13
    return f


@pytest.mark.parametrize(
    "kind, message",
    [
        ("raw_integers", "multiply by 0.0001"),
        ("fill_averaged_in", "fill value"),
        ("skipped_month", "consecutive months"),
        ("duplicate_month", "consecutive months"),
        ("starts_before_terra", "begins in 2000-02"),
        ("missing_column", "missing column"),
        ("cells_exceed_total", "between 0 and NDVI_cells_total"),
        ("value_without_cells", "NDVI_cells is 0"),
        ("cells_without_value", "no NDVI value"),
        ("total_changes", "same positive number"),
        ("month_13", "month must be 1-12"),
    ],
)
def test_bad_files_are_rejected_with_a_useful_message(kind, message):
    with pytest.raises(ndvi.NdviDataError, match=message):
        ndvi.validate_frame(_broken(kind), "region.csv")


def test_dataset_must_be_complete_and_consistent(ndvi_dir):
    frames = {r: synthetic_region_frame(i) for i, r in enumerate(REGIONS)}
    # one region missing
    write_dataset(ndvi_dir, {r: f for r, f in frames.items() if r != "rondonia"})
    assert "rondonia.csv not found" in ndvi.status()["reason"]
    # one region covering different months
    an.clear_caches()
    short = dict(frames)
    short["rondonia"] = frames["rondonia"].iloc[:-3]
    write_dataset(ndvi_dir, short)
    assert "different months" in ndvi.status()["reason"]
    # provenance disagreeing with the files
    an.clear_caches()
    write_dataset(ndvi_dir, frames, provenance_stub(last="2026-09"))
    assert "last_month" in ndvi.status()["reason"]
    # wrong product or version, or no statement about quality filtering
    for change, expect in (({"product": "MYD13C2"}, "product"), ({"version": "006"}, "version"), ({"processing": {"quality_filter": " "}}, "quality_filter")):
        an.clear_caches()
        write_dataset(ndvi_dir, frames, {**provenance_stub(), **change})
        assert expect in ndvi.status()["reason"]
    an.clear_caches()
    write_dataset(ndvi_dir, frames)
    assert ndvi.status() == {"available": True, "first_month": "2000-02", "last_month": "2026-10", "period": (2000, 2026)}


def test_months_with_too_few_valid_pixels_are_dropped(ndvi_dir):
    frames = {r: synthetic_region_frame(i) for i, r in enumerate(REGIONS)}
    f = frames["north-slope"]
    f.loc[10, "NDVI_cells"] = 349  # just under half of 700
    f.loc[11, "NDVI_cells"] = 350  # exactly half is kept
    write_dataset(ndvi_dir, frames)
    series = ndvi.load_series("north-slope")
    assert np.isnan(series["value"].iloc[10]) and np.isfinite(series["value"].iloc[11])
    assert ndvi.provenance_record("north-slope")["months_missing"] == 1


# -------------------------------------------------- regional reduction (grid)


def tiny_grid():
    """Global 1-degree grid, latitude descending like MOD13C2 (row 0 at the north)."""
    lats = np.arange(89.5, -90, -1.0)
    lons = np.arange(-179.5, 180, 1.0)
    return lats, lons


def test_region_mean_is_cos_latitude_weighted_and_ignores_fill():
    lats, lons = tiny_grid()
    rows, cols = ndvi_regions.region_cells(lats, lons, [0.0, 0.0, 2.0, 60.0])
    grid = np.full((lats.size, lons.size), np.nan)
    grid[np.where(lats == 0.5)[0][0], np.where(lons == 0.5)[0][0]] = 0.2
    grid[np.where(lats == 59.5)[0][0], np.where(lons == 0.5)[0][0]] = 0.8
    mean, n, _ = ndvi_regions.region_mean(grid, lats, rows, cols)
    w0, w1 = np.cos(np.deg2rad(0.5)), np.cos(np.deg2rad(59.5))
    assert n == 2
    assert mean == pytest.approx((0.2 * w0 + 0.8 * w1) / (w0 + w1))


def test_raw_integers_fill_and_out_of_range_values():
    raw = np.array([[-3000, 5000], [10001, -2000]], dtype=np.int16)
    out = ndvi_regions.to_ndvi(raw, "raw")
    assert np.isnan(out[0, 0]) and np.isnan(out[1, 0])  # fill, above valid range
    assert out[0, 1] == pytest.approx(0.5) and out[1, 1] == pytest.approx(-0.2)
    phys = ndvi_regions.to_ndvi(np.array([[-0.3, 0.5], [np.nan, 1.0]]), "physical")
    assert np.isnan(phys[0, 0]) and np.isnan(phys[1, 0]) and phys[1, 1] == 1.0
    assert ndvi_regions.detect_scale(raw.astype(float)) == "raw"
    assert ndvi_regions.detect_scale(np.array([0.1, 0.9, np.nan])) == "physical"
    with pytest.raises(ndvi_regions.GridError, match="scaled twice"):
        ndvi_regions.detect_scale(np.array([5.0e7]))


def _maps(values_by_month: dict[tuple[int, int], float], lats, lons, ocean_cols: int = 0):
    out = []
    for (y, m), v in values_by_month.items():
        grid = np.full((lats.size, lons.size), int(round(v * 10000)), dtype=np.int16)
        if ocean_cols:
            grid[:, :ocean_cols] = -3000
        out.append((y, m, grid))
    return out


def test_aggregate_orientation_longitude_convention_and_missing_months():
    lats, lons = tiny_grid()
    year, month = month_table(14)
    months = {(int(y), int(m)): 0.30 + 0.01 * i for i, (y, m) in enumerate(zip(year, month))}
    del months[(2000, 4)]  # April 2000 missing on purpose
    base = ndvi_regions.aggregate(_maps(months, lats, lons), lats, lons, "raw")
    f = base["upper-colorado"]
    assert len(f) == 14 and f["month"].tolist()[:4] == [2, 3, 4, 5]  # the missing month keeps its row
    assert f["NDVI"].tolist()[:2] == pytest.approx([0.30, 0.31]) and np.isnan(f["NDVI"].iloc[2])
    assert f["NDVI"].iloc[3] == pytest.approx(0.33)
    assert f["NDVI_cells"].tolist()[:4] == [28, 28, 0, 28]  # 7 x 4 one-degree cells in the Colorado box
    assert (f["NDVI_cells_total"] == 28).all()

    # same data stored south-to-north and with longitudes 0..360 gives the same answer
    flipped = [(y, m, g[::-1, :]) for y, m, g in _maps(months, lats, lons)]
    lons360 = np.where(lons < 0, lons + 360, lons)
    order = np.argsort(lons360)
    rolled = [(y, m, g[:, order]) for y, m, g in flipped]
    again = ndvi_regions.aggregate(rolled, lats[::-1], lons360[order], "raw")
    for region_id in REGIONS:
        pd.testing.assert_frame_equal(base[region_id], again[region_id])


def test_aggregate_counts_only_land_cells_and_values_differ_by_region():
    lats, lons = tiny_grid()
    year, month = month_table(24)
    maps = []
    for y, m in zip(year, month):
        grid = np.full((lats.size, lons.size), -3000, dtype=np.int16)
        land = (lons[None, :] != -108.5) & np.ones((lats.size, 1), dtype=bool)  # one "ocean" column at 108.5W
        grid[land] = 2000 + 100 * m
        maps.append((int(y), int(m), grid))
    frames = ndvi_regions.aggregate(maps, lats, lons, "raw")
    f = frames["upper-colorado"]  # box 109W..102W: the 108.5W column is ocean
    assert (f["NDVI_cells_total"] == 24).all() and (f["NDVI_cells"] == 24).all()
    assert f["NDVI"].iloc[0] == pytest.approx(0.2 + 0.01 * 2)


def test_duplicate_months_and_wrong_shapes_are_errors():
    lats, lons = tiny_grid()
    with pytest.raises(ndvi_regions.GridError, match="more than once"):
        ndvi_regions.aggregate(_maps({(2000, 2): 0.3}, lats, lons) * 2, lats, lons, "raw")
    with pytest.raises(ndvi_regions.GridError, match="shape"):
        ndvi_regions.aggregate([(2000, 2, np.zeros((3, 3)))], lats, lons, "raw")


# ---------------------------------------- reading yearly stacks (NetCDF files)


def write_year_file(path: Path, year: int, months: list[int], with_time: bool = True) -> None:
    xr = pytest.importorskip("xarray")
    lats, lons = tiny_grid()
    stack = np.empty((len(months), lats.size, lons.size), dtype=np.int16)
    for i, m in enumerate(months):
        stack[i] = 3000 + 10 * (year - 2000) + 100 * m  # stored integers, NDVI x 10000
    stack[:, :, :10] = -3000  # a strip of fill (180W..170W), outside every region
    coords = {"lat": lats, "lon": lons}
    dims = ("time", "lat", "lon")
    if with_time:
        coords["time"] = pd.to_datetime([f"{year}-{m:02d}-01" for m in months])
    da = xr.DataArray(stack, dims=dims, coords=coords, name="NDVI")
    # MODIS convention: scale_factor is a divisor. A CF-style reader would multiply by it.
    da.attrs["scale_factor"] = 10000.0
    da.attrs["_FillValue"] = np.int16(-3000)
    da.to_dataset().to_netcdf(path, encoding={"NDVI": {"dtype": "int16"}})


def test_yearly_netcdf_stacks_become_valid_regional_files(tmp_path, ndvi_dir, capsys):
    pytest.importorskip("xarray")
    src = tmp_path / "grids"
    src.mkdir()
    write_year_file(src / "ndvi_2000.nc", 2000, list(range(2, 13)), with_time=False)  # 11 maps: Feb..Dec
    write_year_file(src / "ndvi_2001.nc", 2001, list(range(1, 13)))
    write_year_file(src / "ndvi_2002.nc", 2002, list(range(1, 11)))
    args = [
        "--input", str(src / "ndvi_*.nc"),
        "--processed-by", "pytest synthetic fixture",
        "--resampling", "synthetic",
        "--quality-filter", "fill -3000 excluded",
        "--out", str(ndvi_dir),
    ]
    assert ndvi_regions.main(args + ["--dry-run"]) == 0
    assert not ndvi_dir.exists()  # a dry run writes nothing
    assert ndvi_regions.main(args) == 0
    out = capsys.readouterr().out
    assert "stored integers, multiplied by 0.0001" in out and "file name" in out

    prov = json.loads((ndvi_dir / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["first_month"], prov["last_month"]) == ("2000-02", "2002-10")
    assert prov["processing"]["input_values"].startswith("stored integers")
    assert [f["fill_value_attribute"] for f in prov["input_files"]] == [-3000.0] * 3
    assert sorted(p.stem for p in ndvi_dir.glob("*.csv")) == sorted(REGIONS)

    frame = ndvi.read_region_csv(ndvi_dir / "upper-colorado.csv")
    assert len(frame) == 33
    assert frame["NDVI"].iloc[0] == pytest.approx(0.3 + 0.01 * 2)  # Feb 2000, not 10000x too large
    assert frame["NDVI"].iloc[-1] == pytest.approx(0.3 + 0.001 * 2 + 0.01 * 10)  # Oct 2002
    assert ndvi.status()["available"]


def test_unreadable_inputs_fail_cleanly(tmp_path, ndvi_dir, capsys):
    assert ndvi_regions.main(["--input", str(tmp_path / "nothing_*.nc"), "--processed-by", "x", "--resampling", "x", "--quality-filter", "x"]) == 2
    with pytest.raises(ndvi_regions.GridError, match="4-digit year"):
        ndvi_regions._months_from_filename(Path("ndvi_stack.nc"), 12)
    assert ndvi_regions._months_from_filename(Path("ndvi_2000.nc"), 11)[0] == (2000, 2)
    assert ndvi_regions._months_from_filename(Path("ndvi_2026.nc"), 10)[-1] == (2026, 10)


# ----------------------------------------------- end to end with six variables


def test_ndvi_becomes_a_sixth_variable_with_its_own_period(synthetic_ndvi):
    cat = client.get("/api/catalog").json()
    assert [v["id"] for v in cat["variables"]] == MERRA2_VARIABLES + ["NDVI"]
    periods = {v["id"]: v["period"] for v in cat["variables"]}
    assert periods["NDVI"] == [2000, 2026] and periods["T2M"] == [1981, 2025]
    assert set(cat["sources"]) == {"merra2", "mod13c2"}

    body = client.get("/api/analysis/upper-colorado/NDVI").json()
    assert body["period"] == [2000, 2026]
    assert (body["first_month"], body["last_month"]) == ("2000-02", "2026-10")
    s, tr = body["series"], body["trend"]
    assert len(s["t"]) == len(s["value"]) == len(s["anomaly"]) == N_MONTHS
    assert tr["n_months"] == N_MONTHS
    assert tr["detectability"]["record_years"] == pytest.approx(26.75)
    # partial first and last years are not shown as annual means
    assert s["annual_year"][0] == 2001 and s["annual_year"][-1] == 2025 and len(s["annual_year"]) == 25
    # 27 calendar years, windows of 15+ years: 13 + 12 + ... + 1
    assert len(body["windows"]) == body["windows_summary"]["n_windows"] == 91
    assert {(w["start"], w["end"]) for w in body["windows"]} >= {(2000, 2014), (2012, 2026), (2000, 2026)}
    # the injected trend (+0.02 per decade) is recovered inside the interval
    assert tr["ols"]["ci_low"] < 0.02 < tr["ols"]["ci_high"]
    assert body["provenance"]["source"]["id"] == "mod13c2"
    assert body["provenance"]["sources"] == ["MOD13C2.061"]
    assert body["provenance"]["request_url"] is None
    assert body["quality"]["grid_cells"] == 700 and body["quality"]["months_missing"] == 0
    assert body["quality"]["calendar_months_excluded"] == []

    over = client.get("/api/overview/NDVI").json()
    assert over["period"] == [2000, 2026] and len(over["regions"]) == len(REGIONS)

    full = client.get("/api/trend/upper-colorado/NDVI").json()
    assert (full["start"], full["end"]) == (2000, 2026)
    assert full["ols"]["slope_per_decade"] == pytest.approx(tr["ols"]["slope_per_decade"])
    assert client.get("/api/trend/upper-colorado/NDVI?start=1990&end=2020").status_code == 422
    assert client.get("/api/trend/upper-colorado/NDVI?start=2005&end=2024").status_code == 200
    assert client.get("/api/provenance").json()["ndvi"]["product"] == "MOD13C2"


def test_existing_variables_are_unchanged_when_ndvi_is_present(synthetic_ndvi):
    with_ndvi = client.get("/api/analysis/upper-colorado/T2M").json()
    assert with_ndvi["period"] == [1981, 2025]
    assert len(with_ndvi["series"]["t"]) == 540 and len(with_ndvi["windows"]) == 496
    assert with_ndvi["provenance"]["source"]["id"] == "merra2"
    assert client.get("/api/trend/upper-colorado/T2M").json()["start"] == 1981


def assert_same(served, computed, path="", rel=1e-9, abs_tol=1e-12):
    """Deep comparison that tolerates last-digit floating-point differences between machines
    (the snapshot is written on one operating system and re-checked by CI on another)."""
    if isinstance(served, dict):
        assert isinstance(computed, dict) and served.keys() == computed.keys(), path
        for key in served:
            assert_same(served[key], computed[key], f"{path}/{key}", rel, abs_tol)
    elif isinstance(served, list):
        assert isinstance(computed, list) and len(served) == len(computed), path
        for i, (a, b) in enumerate(zip(served, computed)):
            assert_same(a, b, f"{path}[{i}]", rel, abs_tol)
    elif isinstance(served, float) or isinstance(computed, float):
        assert served == pytest.approx(computed, rel=rel, abs=abs_tol), path
    else:
        assert served == computed, path


@pytest.mark.parametrize("variable", MERRA2_VARIABLES)
def test_deployed_snapshot_matches_the_pipeline(variable):
    """The static JSON the public site serves equals what the code computes from the committed data."""
    an.clear_caches()
    for region_id in REGIONS:
        served = json.loads((STATIC / "analysis" / region_id / f"{variable}.json").read_text(encoding="utf-8"))
        computed = an.analysis(region_id, variable)
        for block in ("region", "trend", "windows", "windows_summary", "verdict", "crosscheck", "quality", "series", "period"):
            assert_same(served[block], computed[block], f"{region_id}/{variable}/{block}")
    assert_same(json.loads((STATIC / "overview" / f"{variable}.json").read_text(encoding="utf-8")), an.overview(variable), f"overview/{variable}")


def test_assert_same_detects_real_differences():
    assert_same({"a": [1.0, None, "x"]}, {"a": [1.0 + 1e-13, None, "x"]})
    for wrong in ({"a": [1.001, None, "x"]}, {"a": [1.0, 0, "x"]}, {"a": [1.0, None, "y"]}, {"b": [1.0, None, "x"]}, {"a": [1.0, None]}):
        with pytest.raises(AssertionError):
            assert_same({"a": [1.0, None, "x"]}, wrong)


def test_pinned_headline_numbers_for_the_default_view():
    """Colorado air temperature, 1981-2025, as published in the README table."""
    an.clear_caches()
    tr = an.analysis("upper-colorado", "T2M")["trend"]["ols"]
    assert tr["slope_per_decade"] == pytest.approx(0.326, abs=5e-4)
    assert tr["ci_low"] == pytest.approx(0.206, abs=5e-4) and tr["ci_high"] == pytest.approx(0.446, abs=5e-4)


# ------------------------------------------------------------ gaps in a series


def polar_night_frame(seed: int) -> pd.DataFrame:
    """Nov-Jan never observed; October observed in only half of the years."""
    f = synthetic_region_frame(seed)
    dark = f["month"].isin([11, 12, 1])
    patchy_october = (f["month"] == 10) & (f["year"] % 2 == 0)
    f.loc[dark | patchy_october, "NDVI"] = np.nan
    f.loc[dark | patchy_october, "NDVI_cells"] = 0
    return f


def test_seasonal_gaps_are_analysed_without_treating_them_as_values(ndvi_dir):
    frames = {r: synthetic_region_frame(i) for i, r in enumerate(REGIONS)}
    frames["north-slope"] = polar_night_frame(99)
    write_dataset(ndvi_dir, frames)
    body = client.get("/api/analysis/north-slope/NDVI").json()
    q = body["quality"]
    n_dark = int(polar_night_frame(99)["NDVI"].isna().sum())
    assert q["months_missing"] == n_dark and q["coverage"] == pytest.approx(1 - n_dark / N_MONTHS)
    assert q["calendar_months_excluded"] == [10]  # too patchy to compare across years
    n_feb_to_sep = int(np.isin(month_table()[1], np.arange(2, 10)).sum())
    assert q["months_used"] == body["trend"]["n_months"] == n_feb_to_sep
    anomalies = np.array(body["series"]["anomaly"], dtype=float)
    months = np.array(body["series"]["month"])
    assert np.isnan(anomalies[np.isin(months, [10, 11, 12, 1])]).all()
    assert np.isfinite(anomalies[np.isin(months, [2, 3, 4, 5, 6, 7, 8, 9])]).all()
    assert body["series"]["annual_year"] == []  # no year has all twelve months
    assert body["trend"]["ols"]["ci_low"] < 0.02 < body["trend"]["ols"]["ci_high"]
    assert len(body["windows"]) == 91


def test_sparse_calendar_months_rule():
    months = np.tile(np.arange(1, 13), 10)
    values = np.ones(120)
    mask79 = (months == 3) & (np.arange(120) < 36)  # March missing in 3 of 10 years -> 70% present
    values[mask79] = np.nan
    values[months == 12] = np.nan  # December never observed
    out, excluded = stats.mask_sparse_calendar_months(months, values, 0.8)
    assert excluded == [3]  # December had no data at all, so it is not listed as "excluded"
    assert np.isnan(out[months == 3]).all() and np.isfinite(out[months == 5]).all()
    same, none = stats.mask_sparse_calendar_months(months, np.ones(120), 0.8)
    assert none == [] and (same == 1).all()


def test_gap_aware_autocorrelation():
    rng = np.random.default_rng(7)
    n, phi = 6000, 0.6
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    t = 2000 + (np.arange(n) + 0.5) / 12
    # identical to the standard estimator when nothing is missing
    assert stats.lag1_autocorrelation_at(t, x) == stats.lag1_autocorrelation(x)
    # drop 4 consecutive months out of every 12
    keep = (np.arange(n) % 12) < 8
    aware = stats.lag1_autocorrelation_at(t[keep], x[keep])
    naive = stats.lag1_autocorrelation(x[keep])
    assert abs(aware - phi) < 0.04
    assert abs(aware - phi) < abs(naive - phi)  # treating a 5-month jump as one step biases r1 low
    assert naive < aware


def test_every_listed_variable_names_a_known_source():
    for variable, meta in VARIABLES.items():
        assert meta["source"] in {"merra2", "mod13c2"}
        assert len(meta["period"]) == 2 and meta["period"][0] < meta["period"][1]
