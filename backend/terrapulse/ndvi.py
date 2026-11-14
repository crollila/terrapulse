"""Regional NDVI series from MODIS/Terra MOD13C2 v6.1 (monthly, 0.05 degree CMG).

NDVI is not fetched by this application. A teammate downloads MOD13C2 from
NASA LP DAAC, reduces it to one small CSV per region, and commits those files
to ``backend/data/ndvi/`` together with a provenance record. This module reads
and validates them. The exact file format is described in docs/NDVI_HANDOFF.md.

Nothing here invents data: if the files are missing or fail validation, NDVI is
simply not served (see ``status``).

One CSV per region, ``<region-id>.csv``::

    year,month,NDVI,NDVI_cells,NDVI_cells_total
    2000,2,0.23145,688,700
    2000,3,0.24410,700,700

- one row for every calendar month from the first to the last month, in order
- NDVI          area-weighted (cos latitude) mean of the valid pixels, in NDVI
                units (-0.2 to 1.0), i.e. the stored MOD13C2 integer x 0.0001;
                empty when no pixel in the region is valid that month
- NDVI_cells    number of valid pixels averaged that month
- NDVI_cells_total  number of land pixels of the grid inside the region box
                (the same in every row)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import REGIONS, SOURCES

VARIABLE = "NDVI"
NDVI_DIR = Path(__file__).resolve().parent.parent / "data" / "ndvi"

# MOD13C2 NDVI: stored int16 = NDVI x 10000, valid -2000..10000, fill -3000.
SCALE_FACTOR = 0.0001
FILL_VALUE_RAW = -3000
VALID_RANGE_RAW = (-2000, 10000)
VALID_MIN = VALID_RANGE_RAW[0] * SCALE_FACTOR  # -0.2
VALID_MAX = VALID_RANGE_RAW[1] * SCALE_FACTOR  # 1.0

# Terra MODIS vegetation indices begin with February 2000.
FIRST_POSSIBLE_MONTH = (2000, 2)

# A month's regional mean is used only if at least this share of the region's
# land pixels is valid; otherwise the mean describes an unrepresentative part
# of the region (for example only its snow-free southern edge) and is dropped.
MIN_CELL_FRACTION = 0.5

COLUMNS = ["year", "month", "NDVI", "NDVI_cells", "NDVI_cells_total"]
REQUIRED_PROVENANCE = ("product", "version", "first_month", "last_month", "processed_by", "processing")
ACCEPTED_VERSIONS = {"061", "6.1", "61"}


class NdviDataError(ValueError):
    """A delivered NDVI file does not follow docs/NDVI_HANDOFF.md."""


def _month_index(year: np.ndarray | int, month: np.ndarray | int):
    return np.asarray(year) * 12 + (np.asarray(month) - 1)


def validate_frame(frame: pd.DataFrame, name: str = "NDVI file") -> pd.DataFrame:
    """Check one regional CSV and return it with clean dtypes.

    Raises NdviDataError with a message a person can act on.
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise NdviDataError(f"{name}: missing column(s) {missing}; expected exactly {COLUMNS}")
    frame = frame[COLUMNS].copy()
    if len(frame) < 12:
        raise NdviDataError(f"{name}: only {len(frame)} rows; expected one row per month of the record")

    for col in ("year", "month", "NDVI_cells", "NDVI_cells_total"):
        values = pd.to_numeric(frame[col], errors="coerce")
        if values.isna().any() or (values % 1 != 0).any():
            raise NdviDataError(f"{name}: column {col} must hold whole numbers in every row")
        frame[col] = values.astype(int)
    frame["NDVI"] = pd.to_numeric(frame["NDVI"], errors="coerce").astype(float)

    year, month = frame["year"].to_numpy(), frame["month"].to_numpy()
    if ((month < 1) | (month > 12)).any():
        raise NdviDataError(f"{name}: month must be 1-12")
    idx = _month_index(year, month)
    if idx[0] < _month_index(*FIRST_POSSIBLE_MONTH):
        raise NdviDataError(
            f"{name}: first row is {year[0]}-{month[0]:02d}, but Terra MOD13C2 begins in "
            f"{FIRST_POSSIBLE_MONTH[0]}-{FIRST_POSSIBLE_MONTH[1]:02d}"
        )
    steps = np.diff(idx)
    if (steps != 1).any():
        bad = int(np.argmax(steps != 1))
        raise NdviDataError(
            f"{name}: rows must be consecutive months with none skipped or repeated; "
            f"problem after {year[bad]}-{month[bad]:02d} (next row is {year[bad + 1]}-{month[bad + 1]:02d}). "
            "Keep a row for a month with no valid pixels and leave its NDVI empty."
        )

    total = frame["NDVI_cells_total"].to_numpy()
    cells = frame["NDVI_cells"].to_numpy()
    if (total != total[0]).any() or total[0] <= 0:
        raise NdviDataError(f"{name}: NDVI_cells_total must be the same positive number in every row")
    if (cells < 0).any() or (cells > total).any():
        raise NdviDataError(f"{name}: NDVI_cells must be between 0 and NDVI_cells_total")

    ndvi = frame["NDVI"].to_numpy()
    has_value = np.isfinite(ndvi)
    if (has_value & (cells == 0)).any():
        raise NdviDataError(f"{name}: a row has an NDVI value but NDVI_cells is 0")
    if (~has_value & (cells > 0)).any():
        raise NdviDataError(f"{name}: a row has NDVI_cells > 0 but no NDVI value")
    if has_value.any():
        lo, hi = float(np.nanmin(ndvi)), float(np.nanmax(ndvi))
        if hi > 1.5 or lo < -1.5:
            raise NdviDataError(
                f"{name}: NDVI values range from {lo:g} to {hi:g}. They look like stored MOD13C2 integers; "
                f"multiply by {SCALE_FACTOR} so NDVI is between {VALID_MIN} and {VALID_MAX}."
            )
        if lo < VALID_MIN - 1e-9 or hi > VALID_MAX + 1e-9:
            raise NdviDataError(
                f"{name}: NDVI values range from {lo:g} to {hi:g}, outside the valid range {VALID_MIN} to {VALID_MAX}. "
                f"A fill value ({FILL_VALUE_RAW} raw, {FILL_VALUE_RAW * SCALE_FACTOR} scaled) may have been averaged in."
            )
    if not has_value.any():
        raise NdviDataError(f"{name}: no NDVI values at all")
    return frame


def read_region_csv(path: Path) -> pd.DataFrame:
    return validate_frame(pd.read_csv(path), name=path.name)


def validate_provenance(prov: dict) -> None:
    missing = [k for k in REQUIRED_PROVENANCE if not prov.get(k)]
    if missing:
        raise NdviDataError(f"provenance.json: missing {missing}")
    if str(prov["product"]).upper() != "MOD13C2":
        raise NdviDataError(f"provenance.json: product must be MOD13C2, got {prov['product']!r}")
    if str(prov["version"]) not in ACCEPTED_VERSIONS:
        raise NdviDataError(f"provenance.json: version must be 061 (Collection 6.1), got {prov['version']!r}")
    if not str(prov["processing"].get("quality_filter", "")).strip():
        raise NdviDataError("provenance.json: processing.quality_filter must say how invalid pixels were excluded")


@lru_cache(maxsize=None)
def _dataset(directory: str) -> dict:
    """Read and cross-check every regional file. Raises NdviDataError."""
    root = Path(directory)
    prov_path = root / "provenance.json"
    if not prov_path.exists():
        raise NdviDataError("NDVI regional files have not been delivered yet (data/ndvi/provenance.json not found)")
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    validate_provenance(prov)

    frames: dict[str, pd.DataFrame] = {}
    span: tuple[int, int] | None = None
    for region_id in REGIONS:
        path = root / f"{region_id}.csv"
        if not path.exists():
            raise NdviDataError(f"{path.name} not found; one file is needed for each of the {len(REGIONS)} regions")
        frame = read_region_csv(path)
        idx = _month_index(frame["year"].to_numpy(), frame["month"].to_numpy())
        this = (int(idx[0]), int(idx[-1]))
        if span is None:
            span = this
        elif this != span:
            raise NdviDataError(f"{path.name}: covers different months than the other regions; all files must match")
        frames[region_id] = frame
    assert span is not None

    def label(i: int) -> str:
        return f"{i // 12}-{i % 12 + 1:02d}"

    for key, i in (("first_month", span[0]), ("last_month", span[1])):
        if prov[key] != label(i):
            raise NdviDataError(f"provenance.json: {key} is {prov[key]!r} but the files say {label(i)!r}")
    return {
        "frames": frames,
        "provenance": prov,
        "first_month": label(span[0]),
        "last_month": label(span[1]),
        "period": (span[0] // 12, span[1] // 12),
    }


def clear_cache() -> None:
    _dataset.cache_clear()


def status() -> dict:
    """Whether real NDVI data is present and valid, and if not, why."""
    try:
        ds = _dataset(str(NDVI_DIR))
    except NdviDataError as exc:
        return {"available": False, "reason": str(exc)}
    return {"available": True, "first_month": ds["first_month"], "last_month": ds["last_month"], "period": ds["period"]}


def available() -> bool:
    return status()["available"]


def period() -> tuple[int, int]:
    """First and last calendar year present in the delivered files."""
    return _dataset(str(NDVI_DIR))["period"]


def load_series(region_id: str, variable: str = VARIABLE) -> pd.DataFrame:
    """Monthly regional NDVI with low-coverage months set to missing."""
    if variable != VARIABLE:
        raise KeyError(variable)
    frame = _dataset(str(NDVI_DIR))["frames"][region_id]
    out = frame[["year", "month"]].copy()
    enough = frame["NDVI_cells"] >= MIN_CELL_FRACTION * frame["NDVI_cells_total"]
    out["value"] = frame["NDVI"].where(enough)
    out["n_cells_valid"] = frame["NDVI_cells"]
    out["n_cells_total"] = frame["NDVI_cells_total"]
    return out


def provenance_record(region_id: str) -> dict:
    """Provenance in the same shape the MERRA-2 series use, plus NDVI specifics."""
    ds = _dataset(str(NDVI_DIR))
    prov, frame = ds["provenance"], ds["frames"][region_id]
    series = load_series(region_id)
    lon_min, lat_min, lon_max, lat_max = REGIONS[region_id]["bbox"]
    region_info = (prov.get("regions") or {}).get(region_id, {})
    return {
        "request_url": None,
        "retrieved_utc": prov.get("downloaded_utc") or prov.get("created_utc"),
        "api_version": None,
        "api_title": None,
        "sources": [f"{prov['product']}.{prov['version']}"],
        "units_reported": "NDVI (unitless; stored integer x 0.0001)",
        "longname_reported": prov.get("layer", "CMG 0.05 Deg Monthly NDVI"),
        "grid": {
            "n_cells": int(frame["NDVI_cells_total"].iloc[0]),
            "lat_min": region_info.get("lat_min", lat_min),
            "lat_max": region_info.get("lat_max", lat_max),
            "lon_min": region_info.get("lon_min", lon_min),
            "lon_max": region_info.get("lon_max", lon_max),
        },
        "months_total": int(len(series)),
        "months_missing": int(series["value"].isna().sum()),
        "first_month": ds["first_month"],
        "last_month": ds["last_month"],
        "doi": SOURCES["mod13c2"]["doi"],
        "processed_by": prov.get("processed_by"),
        "processing": prov.get("processing"),
        "min_cell_fraction": MIN_CELL_FRACTION,
    }


def load_provenance() -> dict | None:
    """The delivered provenance record, or None when NDVI is not available."""
    if not available():
        return None
    return _dataset(str(NDVI_DIR))["provenance"]
