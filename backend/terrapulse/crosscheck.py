"""Second opinions: the same regional trend computed from an independent dataset.

A trend that is statistically robust inside one dataset can still be a product
of how that dataset was built. MERRA-2 is a reanalysis, and its precipitation in
particular is sensitive to changes in the observations fed into it. So for the
variables where an independent, openly available record exists, TerraPulse
repeats the calculation on that record and says plainly whether the two agree.

    PRECTOTCORR (MERRA-2)  vs  GPCP v2.3 monthly precipitation (satellite + rain gauges)
    T2M (MERRA-2)          vs  NASA GISTEMP v4 surface temperature (stations + ships/buoys)

Humidity, wind speed, soil wetness and NDVI have no second dataset here, and the
app says so rather than implying they were checked.

Run:  uv run --group ndvi python -m terrapulse.crosscheck        (re-download both)

The regional series are committed under data/crosscheck/ with a provenance
record, so the comparison is reproducible offline.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import stats
from .catalog import REGIONS, VARIABLES, variable_period

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "crosscheck"
ALPHA = stats.ALPHA

DATASETS: dict[str, dict] = {
    "gpcp": {
        "id": "gpcp",
        "variable": "PRECTOTCORR",
        "name": "GPCP v2.3",
        "long_name": "Global Precipitation Climatology Project (GPCP) Monthly Analysis, Version 2.3",
        "kind": "A merged analysis of satellite estimates and rain-gauge measurements, on a 2.5° grid.",
        "units": "mm/day",
        "native_grid": "2.5° latitude x 2.5° longitude",
        "opendap": "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc",
        "url": "https://psl.noaa.gov/data/gridded/data.gpcp.html",
        "data_variable": "precip",
        "access": "NOAA Physical Sciences Laboratory (OPeNDAP)",
        "citation": "Adler, R. F., et al. (2018). The Global Precipitation Climatology Project (GPCP) Monthly Analysis "
        "(New Version 2.3) and a Review of 2017 Global Precipitation. Atmosphere, 9(4), 138. "
        "GPCP data provided by the NOAA PSL, Boulder, Colorado, USA, from https://psl.noaa.gov",
        "caveat": "GPCP cells are 2.5° wide, much coarser than the region boxes, and its rain-gauge input also "
        "changes over time. Agreement is support, not proof.",
    },
    "gistemp": {
        "id": "gistemp",
        "variable": "T2M",
        "name": "NASA GISTEMP v4",
        "long_name": "NASA GISS Surface Temperature Analysis (GISTEMP), version 4, 1200 km smoothing, land and ocean",
        "kind": "Weather-station and ship/buoy measurements interpolated onto a 2° grid, as differences from 1951–1980.",
        "units": "°C",
        "native_grid": "2° latitude x 2° longitude, smoothed over 1200 km",
        "opendap": "https://psl.noaa.gov/thredds/dodsC/Datasets/gistemp/combined/1200km/air.2x2.1200.mon.anom.comb.nc",
        "url": "https://data.giss.nasa.gov/gistemp/",
        "data_variable": "air",
        "access": "NOAA Physical Sciences Laboratory (OPeNDAP)",
        "citation": "GISTEMP Team (2026). GISS Surface Temperature Analysis (GISTEMP), version 4. NASA Goddard Institute "
        "for Space Studies. https://data.giss.nasa.gov/gistemp/. Lenssen, N., et al. (2019). Improvements in the "
        "GISTEMP uncertainty model. J. Geophys. Res. Atmos., 124(12), 6307-6326.",
        "caveat": "GISTEMP spreads each station's signal over up to 1200 km, so a regional value blends in its "
        "surroundings. Agreement is support, not proof.",
    },
}

BY_VARIABLE = {meta["variable"]: key for key, meta in DATASETS.items()}

LABELS = {
    "agrees": "Supported by a second dataset",
    "agrees_none": "Second dataset also finds no trend",
    "direction_only": "Second dataset agrees on direction, not size",
    "not_confirmed": "Not confirmed by a second dataset",
    "missed": "Second dataset finds a trend this one does not",
    "conflict": "Contradicted by a second dataset",
    "none": "No second dataset checked",
}


# ------------------------------------------------------------------ pure parts


def overlap_weights(lats: np.ndarray, lons: np.ndarray, bbox: list[float], half_lat: float, half_lon: float) -> np.ndarray:
    """Weight of every grid cell for a region box: overlap area x cos(latitude).

    Cells are rectangles of half-width ``half_lon`` / ``half_lat`` around their
    centres. Longitudes may be given as 0..360 or -180..180. Cells that do not
    touch the box get weight 0.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    lats = np.asarray(lats, dtype=float)
    lons = ((np.asarray(lons, dtype=float) + 180.0) % 360.0) - 180.0
    dlat = np.clip(np.minimum(lats + half_lat, lat_max) - np.maximum(lats - half_lat, lat_min), 0, None)
    dlon = np.clip(np.minimum(lons + half_lon, lon_max) - np.maximum(lons - half_lon, lon_min), 0, None)
    return (dlat * np.cos(np.deg2rad(lats)))[:, None] * dlon[None, :]


def regional_series(grid: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Weighted mean of each time step of ``grid[time, lat, lon]``, ignoring missing cells."""
    valid = np.isfinite(grid) & (weights[None] > 0)
    wsum = (weights[None] * valid).sum(axis=(1, 2))
    total = np.where(valid, grid * weights[None], 0.0).sum(axis=(1, 2))
    return np.where(wsum > 0, total / np.where(wsum > 0, wsum, 1.0), np.nan)


def classify(a_slope: float, a_low: float, a_high: float, a_sig: bool, b_slope: float, b_low: float, b_high: float, b_sig: bool) -> str:
    """How an independent trend (b) relates to the main one (a).

    "Significant" means both tests pass at p < 0.05, the same rule as the verdict.
    """
    if a_sig and b_sig:
        if np.sign(a_slope) != np.sign(b_slope):
            return "conflict"
        overlap = a_low <= b_high and b_low <= a_high
        return "agrees" if overlap else "direction_only"
    if a_sig:
        return "not_confirmed"
    if b_sig:
        return "missed"
    return "agrees_none"


def _fmt(x: float) -> str:
    """Signed number with a true minus sign, as the dashboard prints its own numbers."""
    return f"{x:+.3g}".replace("-", "−")


def describe(code: str, name: str, units: str, a_slope: float, b: dict) -> str:
    """One or two plain sentences. Describes agreement between datasets, never causes."""
    rate = f"{_fmt(b['slope_per_decade'])} {units} per decade (95% range {_fmt(b['ci_low'])} to {_fmt(b['ci_high'])})"
    if code == "agrees":
        return f"{name}, an independent record, shows {rate}: also significant, and its range overlaps this one."
    if code == "agrees_none":
        return f"{name}, an independent record, shows {rate}, which is not significant either."
    if code == "direction_only":
        ratio = abs(a_slope / b["slope_per_decade"])
        size = f"about {ratio:.1f} times as large" if ratio >= 1 else f"about {1 / ratio:.1f} times smaller"
        return (
            f"{name}, an independent record, shows {rate}: the same direction, but the two ranges do not overlap. "
            f"The rate here is {size}. Treat the direction as supported and the size as uncertain."
        )
    if code == "not_confirmed":
        return (
            f"{name}, an independent record, shows {rate}, which is not significant. The trend here may come "
            f"from how this dataset was built rather than from the real world."
        )
    if code == "missed":
        return f"{name}, an independent record, shows {rate}, which is significant. This dataset does not detect it."
    if code == "conflict":
        return f"{name}, an independent record, shows {rate}: a significant trend in the opposite direction."
    raise ValueError(code)


# --------------------------------------------------------------- stored series


@lru_cache(maxsize=None)
def _table(dataset_id: str) -> pd.DataFrame | None:
    path = DATA_DIR / f"{dataset_id}.csv"
    return pd.read_csv(path) if path.exists() else None


@lru_cache(maxsize=None)
def load_provenance() -> dict | None:
    path = DATA_DIR / "provenance.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def clear_cache() -> None:
    _table.cache_clear()
    load_provenance.cache_clear()


def available(variable: str) -> bool:
    dataset_id = BY_VARIABLE.get(variable)
    return dataset_id is not None and _table(dataset_id) is not None and load_provenance() is not None


def independent_trend(variable: str, region_id: str) -> dict:
    """Trend of the independent series over the variable's period, with the same methods."""
    dataset_id = BY_VARIABLE[variable]
    table = _table(dataset_id)
    assert table is not None
    first_year, last_year = variable_period(variable)
    sel = (table["year"] >= first_year) & (table["year"] <= last_year)
    year = table.loc[sel, "year"].to_numpy()
    month = table.loc[sel, "month"].to_numpy()
    values = table.loc[sel, region_id].to_numpy(dtype=float)
    anomalies = stats.deseasonalize(month, values, stats.monthly_climatology(month, values))
    ols = stats.ols_trend(year + (month - 0.5) / 12.0, anomalies)
    mk = stats.mann_kendall(anomalies)
    p_t, p_mk = ols["adjusted"]["p_value"], mk["hamed_rao"]["p_value"]
    return {
        "slope_per_decade": ols["slope"] * 10,
        "ci_low": ols["adjusted"]["ci_low"] * 10,
        "ci_high": ols["adjusted"]["ci_high"] * 10,
        "p_value": p_t,
        "mk_p_value": p_mk,
        "significant": bool(p_t < ALPHA and p_mk < ALPHA),
        "n_months": ols["n"],
        "anomalies": anomalies,
    }


def compare(region_id: str, variable: str, main_trend: dict, main_anomalies: np.ndarray | None = None) -> dict:
    """The cross-check block of the analysis payload."""
    if not available(variable):
        return {
            "code": "none",
            "label": LABELS["none"],
            "text": "This result has not been compared with an independent dataset. It describes this dataset; "
            "whether another record would show the same is not known.",
        }
    dataset = DATASETS[BY_VARIABLE[variable]]
    b = independent_trend(variable, region_id)
    a_ols = main_trend["ols"]
    a_sig = bool(a_ols["p_value"] < ALPHA and main_trend["mann_kendall"]["p_value"] < ALPHA)
    code = classify(a_ols["slope_per_decade"], a_ols["ci_low"], a_ols["ci_high"], a_sig, b["slope_per_decade"], b["ci_low"], b["ci_high"], b["significant"])
    correlation = None
    anomalies = b.pop("anomalies")
    if main_anomalies is not None and len(main_anomalies) == len(anomalies):
        ok = np.isfinite(main_anomalies) & np.isfinite(anomalies)
        if ok.sum() > 24:
            correlation = float(np.corrcoef(main_anomalies[ok], anomalies[ok])[0, 1])
    prov = (load_provenance() or {}).get("datasets", {}).get(dataset["id"], {})
    return {
        "code": code,
        "label": LABELS[code],
        "text": describe(code, dataset["name"], VARIABLES[variable]["units"], a_ols["slope_per_decade"], b),
        "period": list(variable_period(variable)),
        "trend": b,
        "anomaly_correlation": correlation,
        "dataset": {k: dataset[k] for k in ("id", "name", "long_name", "kind", "native_grid", "access", "url", "citation", "caveat")},
        "cells": (prov.get("regions") or {}).get(region_id, {}).get("n_cells"),
        "retrieved_utc": prov.get("retrieved_utc"),
    }


# ---------------------------------------------------------------- downloading


def fetch(dataset_id: str) -> tuple[pd.DataFrame, dict]:
    """Read one dataset over OPeNDAP and reduce it to a monthly series per region."""
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - optional dependency group
        raise RuntimeError("reading the cross-check datasets needs xarray: run with `uv run --group ndvi ...`") from exc

    meta = DATASETS[dataset_id]
    first_year, last_year = variable_period(meta["variable"])
    ds = xr.open_dataset(meta["opendap"], drop_variables=["time_bnds", "lat_bnds", "lon_bnds"])
    try:
        da = ds[meta["data_variable"]].sel(time=slice(f"{first_year}-01-01", f"{last_year}-12-31")).load()
        lats, lons = da["lat"].values.astype(float), da["lon"].values.astype(float)
        half_lat = abs(float(lats[1] - lats[0])) / 2
        half_lon = abs(float(lons[1] - lons[0])) / 2
        grid = da.values.astype(float)
        table = pd.DataFrame({"year": da["time"].dt.year.values, "month": da["time"].dt.month.values})
        expected = (last_year - first_year + 1) * 12
        if len(table) != expected:
            raise RuntimeError(f"{dataset_id}: expected {expected} months for {first_year}-{last_year}, found {len(table)}")
        regions = {}
        for region_id, region in REGIONS.items():
            w = overlap_weights(lats, lons, region["bbox"], half_lat, half_lon)
            series = regional_series(grid, w)
            if not np.isfinite(series).all():
                raise RuntimeError(f"{dataset_id}/{region_id}: {int(np.isnan(series).sum())} months have no data")
            table[region_id] = series
            regions[region_id] = {"n_cells": int((w > 0).sum()), "bbox": region["bbox"]}
        record = {
            "name": meta["long_name"],
            "opendap_url": meta["opendap"],
            "title_in_file": ds.attrs.get("title"),
            "version_in_file": ds.attrs.get("version"),
            "data_variable": meta["data_variable"],
            "units_in_file": da.attrs.get("units"),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "first_month": f"{first_year}-01",
            "last_month": f"{last_year}-12",
            "months": int(len(table)),
            "grid": f"{2 * half_lat:g}° x {2 * half_lon:g}°, {lats.size} x {lons.size} cells",
            "regional_mean": "mean of the grid cells that overlap the region box, weighted by overlap area x cos(latitude)",
            "regions": regions,
            "citation": meta["citation"],
        }
        return table, record
    finally:
        ds.close()


def build() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    provenance: dict = {"datasets": {}}
    for dataset_id in DATASETS:
        table, record = fetch(dataset_id)
        table.to_csv(DATA_DIR / f"{dataset_id}.csv", index=False, float_format="%.5f")
        provenance["datasets"][dataset_id] = record
        print(f"{dataset_id}: {record['months']} months, {record['title_in_file']}")
    (DATA_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    clear_cache()


if __name__ == "__main__":
    build()
    sys.exit(0)
