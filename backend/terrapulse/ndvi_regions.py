"""Reduce gridded monthly MOD13C2 NDVI to one CSV per TerraPulse region.

Input: gridded NDVI on a regular latitude/longitude grid, as one or more files
that each hold a stack of monthly maps (for example one NetCDF file per year
with dimensions time x lat x lon). The native 0.05 degree grid and coarser
regular grids made from it (such as 0.2 degree) both work.

Output: ``backend/data/ndvi/<region-id>.csv`` for every region plus
``provenance.json``, in the format ``ndvi.py`` reads (docs/NDVI_HANDOFF.md).

Run from ``backend/``::

    uv run --group ndvi python -m terrapulse.ndvi_regions \
        --input "D:/modis/ndvi_*.nc" \
        --processed-by "Your Name" \
        --resampling "0.05 to 0.2 degree by mean of valid pixels" \
        --quality-filter "fill -3000 excluded; pixel reliability 0-1 kept"

Add ``--dry-run`` to print what was detected without writing any file.

This file does the arithmetic only. It does not download data and it never
creates values: a month with no valid pixel is written as missing.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__, ndvi
from .catalog import REGIONS, SOURCES

LAT_NAMES = ("lat", "latitude", "y", "Latitude", "LAT")
LON_NAMES = ("lon", "longitude", "x", "Longitude", "LON")
TIME_NAMES = ("time", "date", "month", "t", "Time")
VAR_HINTS = ("ndvi", "NDVI")


class GridError(ValueError):
    """The input grid could not be understood."""


def normalize_lons(lons: np.ndarray) -> np.ndarray:
    """Longitudes as -180..180 (accepts 0..360 input)."""
    return ((np.asarray(lons, dtype=float) + 180.0) % 360.0) - 180.0


def detect_scale(values: np.ndarray) -> str:
    """'raw' for stored MOD13C2 integers (NDVI x 10000), 'physical' for NDVI units."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise GridError("the first monthly map contains no finite values")
    vmax = float(np.max(np.abs(finite)))
    if vmax > 30000:
        raise GridError(
            f"values reach {vmax:g}. MOD13C2 stores NDVI x 10000 (at most 10000); these look scaled twice. "
            "A common cause is a reader applying the HDF 'scale_factor = 10000' attribute as a multiplier."
        )
    return "raw" if vmax > 1.5 else "physical"


def to_ndvi(values: np.ndarray, scale: str) -> np.ndarray:
    """Convert a map to NDVI units with every invalid value set to NaN."""
    out = np.asarray(values, dtype=float).copy()
    if scale == "raw":
        lo, hi = ndvi.VALID_RANGE_RAW
        out[(out < lo) | (out > hi)] = np.nan  # removes the -3000 fill as well
        out *= ndvi.SCALE_FACTOR
    elif scale == "physical":
        out[(out < ndvi.VALID_MIN - 1e-9) | (out > ndvi.VALID_MAX + 1e-9)] = np.nan
    else:
        raise GridError(f"unknown scale {scale!r}")
    return out


def region_cells(lats: np.ndarray, lons: np.ndarray, bbox: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Indices of grid rows and columns whose cell centres fall inside the box."""
    lon_min, lat_min, lon_max, lat_max = bbox
    rows = np.where((lats >= lat_min) & (lats <= lat_max))[0]
    cols = np.where((lons >= lon_min) & (lons <= lon_max))[0]
    if rows.size == 0 or cols.size == 0:
        raise GridError(f"no grid cells fall inside the box {bbox}; is the grid global?")
    return rows, cols


def region_mean(ndvi_map: np.ndarray, lats: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> tuple[float, int, np.ndarray]:
    """Area-weighted (cos latitude) mean of the valid cells of one monthly map.

    Returns (mean or NaN, number of valid cells, boolean mask of valid cells).
    """
    sub = ndvi_map[np.ix_(rows, cols)]
    valid = np.isfinite(sub)
    n = int(valid.sum())
    if n == 0:
        return float("nan"), 0, valid
    weights = np.cos(np.deg2rad(lats[rows]))[:, None] * np.ones((1, cols.size))
    mean = float(np.sum(np.where(valid, sub, 0.0) * weights) / np.sum(weights * valid))
    return mean, n, valid


def aggregate(
    maps: list[tuple[int, int, np.ndarray]],
    lats: np.ndarray,
    lons: np.ndarray,
    scale: str,
) -> dict[str, pd.DataFrame]:
    """Regional CSV frames from monthly maps given as (year, month, 2-D array[lat, lon]).

    Months missing between the first and the last map are written as rows with
    no value, so every file has one row per calendar month.
    """
    lats = np.asarray(lats, dtype=float)
    lons = normalize_lons(lons)
    if not maps:
        raise GridError("no monthly maps were found")
    keys = [y * 12 + (m - 1) for y, m, _ in maps]
    if len(set(keys)) != len(keys):
        raise GridError("the same month appears more than once in the input")
    order = np.argsort(keys)
    first, last = min(keys), max(keys)

    frames: dict[str, pd.DataFrame] = {}
    for region_id, region in REGIONS.items():
        rows, cols = region_cells(lats, lons, region["bbox"])
        ever_valid = np.zeros((rows.size, cols.size), dtype=bool)
        by_month: dict[int, tuple[float, int]] = {}
        for i in order:
            year, month, raw = maps[i]
            if raw.shape != (lats.size, lons.size):
                raise GridError(f"map for {year}-{month:02d} has shape {raw.shape}, expected {(lats.size, lons.size)}")
            mean, n, valid = region_mean(to_ndvi(raw, scale), lats, rows, cols)
            ever_valid |= valid
            by_month[keys[i]] = (mean, n)
        total = int(ever_valid.sum())
        if total == 0:
            raise GridError(f"region {region_id}: no valid NDVI pixel in any month")
        records = []
        for k in range(first, last + 1):
            mean, n = by_month.get(k, (float("nan"), 0))
            records.append({"year": k // 12, "month": k % 12 + 1, "NDVI": mean, "NDVI_cells": n, "NDVI_cells_total": total})
        frames[region_id] = ndvi.validate_frame(pd.DataFrame.from_records(records, columns=ndvi.COLUMNS), f"{region_id}.csv")
    return frames


# ---------------------------------------------------------------- file reading


def _pick(names: tuple[str, ...], available) -> str | None:
    lowered = {str(a).lower(): a for a in available}
    for n in names:
        if n.lower() in lowered:
            return lowered[n.lower()]
    return None


def _months_from_filename(path: Path, n: int) -> list[tuple[int, int]]:
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", path.stem)
    if not match:
        raise GridError(
            f"{path.name}: no readable time coordinate and no 4-digit year in the file name; "
            "cannot tell which months the maps are"
        )
    year = int(match.group(1))
    if n > 12:
        raise GridError(f"{path.name}: {n} maps in one yearly file; expected at most 12")
    # Terra MOD13C2 begins in February 2000, so a short first-year file starts in February.
    start = 2 if (year == 2000 and n == 11) else 1
    return [(year, start + i) for i in range(n)]


def read_stack(path: Path, var: str | None = None) -> tuple[list[tuple[int, int, np.ndarray]], np.ndarray, np.ndarray, dict]:
    """Read one file holding a time x lat x lon stack (NetCDF/HDF5 via xarray)."""
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - depends on the optional group
        raise GridError("reading gridded files needs xarray: run with `uv run --group ndvi ...`") from exc

    # mask_and_scale=False: read the stored numbers untouched. MODIS files carry
    # 'scale_factor = 10000', which readers following the CF convention would
    # wrongly multiply by.
    ds = xr.open_dataset(path, mask_and_scale=False, decode_times=True)
    try:
        candidates = [v for v in ds.data_vars if ds[v].ndim in (2, 3)]
        if var:
            if var not in ds.data_vars:
                raise GridError(f"{path.name}: no variable {var!r}; found {list(ds.data_vars)}")
            name = var
        else:
            hinted = [v for v in candidates if any(h.lower() in str(v).lower() for h in VAR_HINTS)]
            pool = hinted or candidates
            if len(pool) != 1:
                raise GridError(f"{path.name}: cannot tell which variable is NDVI among {list(ds.data_vars)}; pass --var")
            name = pool[0]
        da = ds[name]
        lat_name = _pick(LAT_NAMES, list(da.dims) + list(ds.coords))
        lon_name = _pick(LON_NAMES, list(da.dims) + list(ds.coords))
        if lat_name is None or lon_name is None:
            raise GridError(f"{path.name}: latitude/longitude coordinates not found (dims {da.dims})")
        lats = np.asarray(ds[lat_name].values, dtype=float)
        lons = np.asarray(ds[lon_name].values, dtype=float)
        if lats.ndim != 1 or lons.ndim != 1:
            raise GridError(f"{path.name}: the grid must be regular (1-D latitude and longitude)")
        time_dim = next((d for d in da.dims if d not in (ds[lat_name].dims[0], ds[lon_name].dims[0])), None)
        da = da.transpose(*( [time_dim] if time_dim else [] ), ds[lat_name].dims[0], ds[lon_name].dims[0])
        data = np.asarray(da.values)
        if data.ndim == 2:
            data = data[None, :, :]
        months: list[tuple[int, int]] | None = None
        if time_dim and time_dim in ds.coords and np.issubdtype(ds[time_dim].dtype, np.datetime64):
            stamps = pd.to_datetime(ds[time_dim].values)
            months = [(int(s.year), int(s.month)) for s in stamps]
            source = f"time coordinate '{time_dim}'"
        else:
            months = _months_from_filename(path, data.shape[0])
            source = "file name (no datetime coordinate found)"
        fill = da.attrs.get("_FillValue")
        info = {
            "file": path.name,
            "variable": str(name),
            "dtype": str(data.dtype),
            "shape": list(data.shape),
            "months_from": source,
            "fill_value_attribute": None if fill is None else float(np.asarray(fill).reshape(-1)[0]),
        }
        maps = [(y, m, data[i]) for i, (y, m) in enumerate(months)]
        return maps, lats, lons, info
    finally:
        ds.close()


def build_provenance(frames: dict[str, pd.DataFrame], lats: np.ndarray, lons: np.ndarray, scale: str, args: argparse.Namespace, files: list[dict]) -> dict:
    lons = normalize_lons(lons)
    first = next(iter(frames.values()))
    regions = {}
    for region_id, frame in frames.items():
        rows, cols = region_cells(np.asarray(lats, dtype=float), lons, REGIONS[region_id]["bbox"])
        regions[region_id] = {
            "bbox": REGIONS[region_id]["bbox"],
            "n_cells_total": int(frame["NDVI_cells_total"].iloc[0]),
            "n_cells_in_box": int(rows.size * cols.size),
            "lat_min": float(lats[rows].min()),
            "lat_max": float(lats[rows].max()),
            "lon_min": float(lons[cols].min()),
            "lon_max": float(lons[cols].max()),
        }
    step_lat = float(np.median(np.abs(np.diff(lats))))
    step_lon = float(np.median(np.abs(np.diff(np.sort(lons)))))
    return {
        "product": "MOD13C2",
        "version": "061",
        "doi": SOURCES["mod13c2"]["doi"],
        "layer": "CMG 0.05 Deg Monthly NDVI",
        "first_month": f"{int(first['year'].iloc[0])}-{int(first['month'].iloc[0]):02d}",
        "last_month": f"{int(first['year'].iloc[-1])}-{int(first['month'].iloc[-1]):02d}",
        "downloaded_from": args.downloaded_from,
        "downloaded_utc": args.downloaded_utc,
        "processed_by": args.processed_by,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": f"terrapulse.ndvi_regions {__version__}",
        "processing": {
            "input_grid": f"{step_lat:g}° x {step_lon:g}° regular latitude/longitude, {len(lats)} x {len(lons)} cells",
            "resampling": args.resampling,
            "quality_filter": args.quality_filter,
            "input_values": "stored integers (NDVI x 10000)" if scale == "raw" else "NDVI units",
            "scale_factor": ndvi.SCALE_FACTOR,
            "fill_value_raw": ndvi.FILL_VALUE_RAW,
            "valid_range_raw": list(ndvi.VALID_RANGE_RAW),
            "regional_mean": "cos(latitude)-weighted mean of valid cells whose centres fall inside the box",
            "cells_total": "cells inside the box that are valid in at least one month of the record",
        },
        "input_files": files,
        "regions": regions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", required=True, nargs="+", help="files or glob patterns, e.g. \"D:/modis/ndvi_*.nc\"")
    parser.add_argument("--var", help="name of the NDVI variable in the files (auto-detected if there is one candidate)")
    parser.add_argument("--scale", choices=["auto", "raw", "physical"], default="auto")
    parser.add_argument("--out", type=Path, default=ndvi.NDVI_DIR)
    parser.add_argument("--processed-by", required=True, help="who prepared the gridded files")
    parser.add_argument("--resampling", required=True, help="how the 0.05° product was put on the input grid")
    parser.add_argument("--quality-filter", required=True, help="how fill, cloud, snow and water pixels were excluded")
    parser.add_argument("--downloaded-from", default="NASA LP DAAC (Earthdata)")
    parser.add_argument("--downloaded-utc", default=None, help="date the MOD13C2 files were downloaded, e.g. 2026-11-14")
    parser.add_argument("--dry-run", action="store_true", help="report what was detected; write nothing")
    args = parser.parse_args(argv)

    paths: list[Path] = []
    for pattern in args.input:
        matches = sorted(glob.glob(pattern))
        if matches:
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(pattern))
    missing = [p for p in paths if not p.exists()]
    if missing or not paths:
        print(f"error: input not found: {[str(p) for p in missing] or args.input}", file=sys.stderr)
        return 2

    try:
        maps: list[tuple[int, int, np.ndarray]] = []
        files: list[dict] = []
        lats = lons = None
        for path in paths:
            m, la, lo, info = read_stack(path, args.var)
            if lats is None:
                lats, lons = la, lo
            elif la.shape != lats.shape or lo.shape != lons.shape or not (np.allclose(la, lats) and np.allclose(lo, lons)):
                raise GridError(f"{path.name}: grid differs from the first file")
            maps.extend(m)
            files.append(info)
            print(f"read {path.name}: variable {info['variable']}, {info['shape']}, {info['dtype']}, months from {info['months_from']}")
        assert lats is not None and lons is not None
        scale = detect_scale(np.asarray(maps[0][2], dtype=float)) if args.scale == "auto" else args.scale
        print(f"values treated as: {'stored integers, multiplied by 0.0001' if scale == 'raw' else 'NDVI units'}")
        print(f"grid: {len(lats)} x {len(lons)}, latitude {lats[0]:g} to {lats[-1]:g}, longitude {lons[0]:g} to {lons[-1]:g}")
        frames = aggregate(maps, lats, lons, scale)
        prov = build_provenance(frames, lats, lons, scale, args, files)
        ndvi.validate_provenance(prov)
    except (GridError, ndvi.NdviDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"record: {prov['first_month']} to {prov['last_month']} ({len(next(iter(frames.values())))} months)")
    for region_id, frame in frames.items():
        low = int((frame["NDVI_cells"] < ndvi.MIN_CELL_FRACTION * frame["NDVI_cells_total"]).sum())
        print(
            f"  {region_id:16s} land cells {int(frame['NDVI_cells_total'].iloc[0]):5d}  "
            f"NDVI {frame['NDVI'].min():.3f} to {frame['NDVI'].max():.3f}  "
            f"months below {ndvi.MIN_CELL_FRACTION:.0%} coverage: {low}"
        )
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    for region_id, frame in frames.items():
        frame.to_csv(args.out / f"{region_id}.csv", index=False, float_format="%.5f")
    (args.out / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print(f"wrote {len(frames)} CSV files and provenance.json to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
