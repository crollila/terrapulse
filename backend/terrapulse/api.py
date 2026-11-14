"""FastAPI service.  Run:  uv run uvicorn terrapulse.api:app --reload"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, analysis as an, data, ndvi
from .catalog import END_YEAR, REGIONS, SOURCE, SOURCES, START_YEAR, VARIABLES
from .power import load_provenance

app = FastAPI(
    title="TerraPulse API",
    version=__version__,
    description="Trend slope, uncertainty and significance for regional series of NASA Earth-system data.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _check(region: str, variable: str) -> None:
    if region not in REGIONS:
        raise HTTPException(404, f"unknown region '{region}'")
    _check_variable(variable)


def _check_variable(variable: str) -> None:
    if variable not in VARIABLES:
        raise HTTPException(404, f"unknown variable '{variable}'")
    if not data.available(variable):
        raise HTTPException(404, f"variable '{variable}' has no data yet: {data.unavailable_reason(variable)}")


def _variable_entry(variable: str) -> dict:
    """Catalog entry with the period actually served (read from the data for NDVI)."""
    return {"id": variable, **VARIABLES[variable], "period": list(data.period(variable))}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/catalog")
def catalog() -> dict:
    return {
        "period": [START_YEAR, END_YEAR],
        "min_window_years": an.MIN_WINDOW_YEARS,
        "regions": [{"id": k, **v} for k, v in REGIONS.items()],
        # Only variables with data behind them are listed.
        "variables": [_variable_entry(v) for v in data.available_variables()],
        "source": SOURCE,
        "sources": {s: SOURCES[s] for s in dict.fromkeys(data.source_id(v) for v in data.available_variables())},
    }


@app.get("/api/analysis/{region}/{variable}")
def get_analysis(region: str, variable: str) -> dict:
    _check(region, variable)
    return an.analysis(region, variable)


@app.get("/api/trend/{region}/{variable}")
def get_trend(region: str, variable: str, start: int | None = None, end: int | None = None) -> dict:
    _check(region, variable)
    try:
        return an.custom_trend(region, variable, start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/overview/{variable}")
def get_overview(variable: str) -> dict:
    _check_variable(variable)
    return an.overview(variable)


@app.get("/api/provenance")
def provenance() -> dict:
    out = load_provenance()
    ndvi_record = ndvi.load_provenance()
    if ndvi_record is not None:
        out = {**out, "ndvi": ndvi_record}
    return out
