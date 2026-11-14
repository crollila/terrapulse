"""One door to the regional series, whichever NASA source a variable comes from.

MERRA-2 variables are always available (their reduced series are committed).
NDVI is available only when real MOD13C2 regional files have been delivered and
pass validation; until then it is left out of the catalog, the API and the
static export, so the dashboard never shows a variable without data behind it.
"""

from __future__ import annotations

import pandas as pd

from . import ndvi, power
from .catalog import VARIABLES, variable_period


def source_id(variable: str) -> str:
    return VARIABLES[variable]["source"]


def available(variable: str) -> bool:
    if variable not in VARIABLES:
        return False
    return True if source_id(variable) == "merra2" else ndvi.available()


def available_variables() -> list[str]:
    return [v for v in VARIABLES if available(v)]


def unavailable_reason(variable: str) -> str | None:
    if variable in VARIABLES and source_id(variable) == "mod13c2":
        return ndvi.status().get("reason")
    return None


def period(variable: str) -> tuple[int, int]:
    """First and last calendar year of the record actually served."""
    if source_id(variable) == "mod13c2":
        return ndvi.period()
    return variable_period(variable)


def load_series(region_id: str, variable: str) -> pd.DataFrame:
    """Frame with year, month, value, n_cells_valid; one row per month, in order."""
    if source_id(variable) == "mod13c2":
        return ndvi.load_series(region_id, variable)
    return power.load_series(region_id, variable)


def provenance_record(region_id: str, variable: str) -> dict:
    if source_id(variable) == "mod13c2":
        return ndvi.provenance_record(region_id)
    return power.load_provenance()["series"][f"{region_id}/{variable}"]


def clear_cache() -> None:
    ndvi.clear_cache()
