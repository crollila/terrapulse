"""Download monthly MERRA-2 values from the NASA POWER regional API and
reduce them to one area-weighted series per region.

Run:  uv run python -m terrapulse.power            (all regions and variables)

Raw API responses are cached under data/raw/ (not committed). The reduced
series and a provenance record are written to data/processed/ (committed), so
the analysis can be reproduced offline and re-fetched at any time.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from .catalog import END_YEAR, REGIONS, SOURCE, START_YEAR, VARIABLES

# The variables this module fetches (NDVI comes from MOD13C2 files, see ndvi.py).
MERRA2_VARIABLES = [v for v, meta in VARIABLES.items() if meta["source"] == "merra2"]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FILL_VALUE = -999.0


def request_params(region_id: str, variable: str) -> dict:
    lon_min, lat_min, lon_max, lat_max = REGIONS[region_id]["bbox"]
    return {
        "parameters": variable,
        "community": "AG",
        "latitude-min": lat_min,
        "latitude-max": lat_max,
        "longitude-min": lon_min,
        "longitude-max": lon_max,
        "start": START_YEAR,
        "end": END_YEAR,
        "format": "JSON",
    }


def fetch_raw(region_id: str, variable: str, client: httpx.Client, force: bool = False) -> dict:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{region_id}__{variable}.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.get(SOURCE["api_endpoint"], params=request_params(region_id, variable))
            resp.raise_for_status()
            payload = resp.json()
            payload["_retrieved_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            payload["_request_url"] = str(resp.request.url)
            path.write_text(json.dumps(payload), encoding="utf-8")
            return payload
        except (httpx.HTTPError, ValueError) as exc:  # retry transient failures
            last_error = exc
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"NASA POWER request failed for {region_id}/{variable}: {last_error}")


def reduce_to_series(payload: dict, variable: str) -> tuple[pd.DataFrame, dict]:
    """Area-weighted (cos latitude) mean over all grid cells, per month.

    Returns a frame indexed by (year, month) with columns value, n_cells_valid,
    and a small summary of the grid.
    """
    features = payload["features"]
    if not features:
        raise ValueError("NASA POWER returned no grid cells")
    fill = float(payload.get("header", {}).get("fill_value", FILL_VALUE))
    keys = [
        f"{y}{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)
    ]
    lats = np.array([f["geometry"]["coordinates"][1] for f in features], dtype=float)
    lons = np.array([f["geometry"]["coordinates"][0] for f in features], dtype=float)
    grid = np.full((len(features), len(keys)), np.nan)
    for i, feat in enumerate(features):
        vals = feat["properties"]["parameter"][variable]
        for j, key in enumerate(keys):
            v = vals.get(key)
            if v is not None and v != fill:
                grid[i, j] = float(v)
    weights = np.cos(np.deg2rad(lats))[:, None]
    valid = np.isfinite(grid)
    wsum = (weights * valid).sum(axis=0)
    total = np.where(valid, grid * weights, 0.0).sum(axis=0)
    mean = np.where(wsum > 0, total / np.where(wsum > 0, wsum, 1), np.nan)
    frame = pd.DataFrame(
        {
            "year": [int(k[:4]) for k in keys],
            "month": [int(k[4:]) for k in keys],
            "value": mean,
            "n_cells_valid": valid.sum(axis=0),
        }
    )
    grid_info = {
        "n_cells": int(len(features)),
        "lat_min": float(lats.min()),
        "lat_max": float(lats.max()),
        "lon_min": float(lons.min()),
        "lon_max": float(lons.max()),
    }
    return frame, grid_info


def build(force: bool = False) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    provenance: dict = {"source": SOURCE, "period": [START_YEAR, END_YEAR], "series": {}}
    with httpx.Client(timeout=180) as client:
        for region_id in REGIONS:
            columns: dict[str, pd.Series] = {}
            base: pd.DataFrame | None = None
            for variable in MERRA2_VARIABLES:
                payload = fetch_raw(region_id, variable, client, force=force)
                frame, grid_info = reduce_to_series(payload, variable)
                base = frame[["year", "month"]] if base is None else base
                columns[variable] = frame["value"]
                columns[f"{variable}_cells"] = frame["n_cells_valid"]
                header = payload.get("header", {})
                n_missing = int(frame["value"].isna().sum())
                provenance["series"][f"{region_id}/{variable}"] = {
                    "request_url": payload.get("_request_url"),
                    "retrieved_utc": payload.get("_retrieved_utc"),
                    "api_version": header.get("api", {}).get("version"),
                    "api_title": header.get("title"),
                    "sources": header.get("sources"),
                    "units_reported": payload.get("parameters", {}).get(variable, {}).get("units"),
                    "longname_reported": payload.get("parameters", {}).get(variable, {}).get("longname"),
                    "grid": grid_info,
                    "months_total": int(len(frame)),
                    "months_missing": n_missing,
                    "first_month": f"{START_YEAR}-01",
                    "last_month": f"{END_YEAR}-12",
                }
                print(f"{region_id:16s} {variable:12s} cells={grid_info['n_cells']:4d} missing={n_missing}")
            assert base is not None
            out = pd.concat([base, pd.DataFrame(columns)], axis=1)
            out.to_csv(PROCESSED_DIR / f"{region_id}.csv", index=False, float_format="%.5f")
    (PROCESSED_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


def load_series(region_id: str, variable: str) -> pd.DataFrame:
    frame = pd.read_csv(PROCESSED_DIR / f"{region_id}.csv")
    out = frame[["year", "month"]].copy()
    out["value"] = frame[variable]
    out["n_cells_valid"] = frame[f"{variable}_cells"]
    return out


def load_provenance() -> dict:
    return json.loads((PROCESSED_DIR / "provenance.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    build(force="--force" in sys.argv)
