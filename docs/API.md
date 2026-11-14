# TerraPulse API contract

The same JSON is available from the FastAPI service and as static files. Interactive docs for the
live service are at `/docs`.

| Live API | Static file (under `frontend/public/data/`) | Returns |
|---|---|---|
| `GET /api/health` | — | `{status, version}` |
| `GET /api/catalog` | `catalog.json` | minimum window, regions, variables (each with its own `period` and `source`), `sources` |
| `GET /api/analysis/{region}/{variable}` | `analysis/{region}/{variable}.json` | series, full-record trend, all windows, verdict, quality, provenance |
| `GET /api/overview/{variable}` | `overview/{variable}.json` | full-record trend for every region, with FDR-adjusted p-values |
| `GET /api/trend/{region}/{variable}?start=&end=` | — (live only) | every statistic for one custom window of 15+ years |
| `GET /api/provenance` | `provenance.json` | request URL, retrieval time and grid for every series |

Unknown region or variable: `404`. A variable whose data has not been delivered (NDVI, until its
regional files exist) is not listed in the catalog and also returns `404`. Window shorter than 15
years or outside the variable's period: `422`. `start` and `end` default to the variable's period.

## `analysis` payload

```jsonc
{
  "region":   { "id", "name", "short_name", "country", "bbox": [lonW, latS, lonE, latN], "setting", "land_share" },
  "variable": { "id", "name", "long_name", "units", "definition", "decimals", "source", "period" },
  "period":   [1981, 2025],           // per variable; [2000, 2026] for NDVI
  "first_month": "1981-01", "last_month": "2025-12",
  "series": {
    "t": [1981.0417, ...],          // decimal year at mid-month, 540 values
    "year": [...], "month": [...],
    "value": [...],                 // regional mean, variable units; null = missing
    "anomaly": [...],               // value minus calendar-month mean
    "climatology": [12 values],
    "annual_year": [...], "annual_mean": [...]
  },
  "trend": {                        // full record; slopes are per decade
    "start", "end", "n_months",
    "ols": { "slope_per_decade", "intercept", "r_squared",
             "ci_low", "ci_high", "p_value",                   // AR(1)-adjusted
             "naive_ci_low", "naive_ci_high", "naive_p_value" },
    "theil_sen": { "slope_per_decade", "ci_low", "ci_high" },
    "mann_kendall": { "tau", "p_value", "classic_p_value", "variance_factor" },  // p_value = Hamed-Rao
    "noise": { "residual_std", "lag1_autocorrelation", "n_effective" },
    "detectability": { "years_needed", "low", "high", "record_years", "more_years" }
  },
  "windows": [ { "start", "end", "slope_per_decade", "intercept", "ci_low", "ci_high", "p_value", "significant" } ],  // 496
  "windows_summary": { "n_windows", "min_years", "share_same_direction",
                       "share_significant_same_direction", "share_significant_opposite_direction",
                       "slope_min", "slope_max" },
  "verdict": { "code": "robust | date_sensitive | mixed | not_detected", "title", "text", "direction" },
  "crosscheck": {                   // the same trend from an independent dataset, where one exists
    "code": "agrees | agrees_none | direction_only | not_confirmed | missed | conflict | none",
    "label", "text",
    "period", "trend": { "slope_per_decade", "ci_low", "ci_high", "p_value", "mk_p_value", "significant", "n_months" },
    "anomaly_correlation", "cells", "retrieved_utc",
    "dataset": { "id", "name", "long_name", "kind", "native_grid", "access", "url", "citation", "caveat" }
  },                                // code "none" carries only code, label and text
  "quality": { "months_total", "months_missing", "coverage", "grid_cells", "min_cells_valid",
               "lag1_autocorrelation", "n_effective", "units_reported_by_nasa",
               "months_used", "calendar_months_excluded" },
  "provenance": { "request_url", "retrieved_utc", "api_version", "sources", "grid", "source" }
}
```

`intercept` is the value of the fitted line at decimal year 0, so the line is
`intercept + (slope_per_decade / 10) * t`.

## Test fixtures

There is no mock-data mode in the app. Synthetic series with known trends exist only in
`backend/tests` to verify the statistics.
