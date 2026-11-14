# TerraPulse

**Find a trend in NASA Earth-system data. Then find out whether you should believe it.**

TerraPulse is Team Orbital Alpha's entry for the NASA Space Apps Challenge 2026 challenge
[Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/)

- Live demo: https://crollila.github.io/terrapulse/
- Methodology: [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
- API contract: [docs/API.md](docs/API.md)
- Adding the NDVI data: [docs/NDVI_HANDOFF.md](docs/NDVI_HANDOFF.md)

## What it does

Pick a variable and a region on the map. TerraPulse shows the monthly NASA MERRA-2 time series for
1981–2025 and answers the challenge's four questions:

| Question | How TerraPulse answers it |
|---|---|
| What is changing? | Five variables with plain-language definitions: air temperature, precipitation, humidity, wind speed, root-zone soil wetness |
| Where? | Eight regions on an interactive map, coloured by the direction and significance of their trend |
| How much? | Rate of change per decade (least squares and Sen's slope) with a 95% confidence interval |
| Is it significant? | A t-test and a Mann–Kendall test, both corrected for month-to-month persistence |

It then goes one step further and tries to break its own result:

- **Did you just pick good dates?** The trend is recomputed for all 496 start/end-year windows of
  15 years or more and shown as a heat map. A trend that flips sign with the dates is labelled as such.
- **Did you just test many places?** A false-discovery-rate correction is applied across regions.
- **Not significant, or not significant *yet*?** When no trend is detected, TerraPulse estimates how
  many years of data would be needed to detect one of that size (Weatherhead et al. 1998).

Each result is summarised as one of four verdicts: *holds up*, *depends on dates*, *tests disagree*,
or *not detected yet*. Verdicts describe change in the dataset. They never claim a cause.

## Results in the current data snapshot

Full-record (1981–2025) trends per decade with 95% confidence intervals, from the committed data
(retrieved 2026-11-14). These numbers are produced by `backend/terrapulse/analysis.py`; nothing is
typed in by hand elsewhere in the app.

| Region | Air temperature (°C/decade) | Verdict | Precipitation (mm/day/decade) | Verdict |
|---|---|---|---|---|
| Upper Colorado River Basin | +0.33 [+0.21, +0.45] | holds up | −0.023 [−0.055, +0.010] | not detected yet |
| Alaska North Slope | +0.51 [+0.32, +0.70] | holds up | +0.045 [+0.005, +0.084] | depends on dates |
| Southwestern Amazon (Rondonia) | +0.49 [+0.35, +0.62] | holds up | −0.54 [−0.64, −0.44] | holds up |
| Moroccan Atlas | +0.26 [+0.17, +0.36] | depends on dates | +0.011 [−0.048, +0.070] | not detected yet |
| Central Sahel | +0.14 [+0.04, +0.24] | depends on dates | +0.098 [+0.044, +0.152] | depends on dates |
| Punjab Plain | −0.03 [−0.16, +0.10] | depends on dates | +0.19 [+0.11, +0.27] | depends on dates |
| Malay Peninsula | +0.19 [+0.14, +0.24] | holds up | +0.43 [+0.30, +0.55] | holds up |
| Murray-Darling Basin (south) | +0.25 [+0.14, +0.37] | holds up | −0.017 [−0.081, +0.046] | not detected yet |

**Read these with care.** They are trends in a reanalysis, not in direct measurements, and they
have not been validated against independent datasets. Large precipitation trends in particular
(for example Rondonia) may partly reflect changes in the observations fed into MERRA-2 over time.
See [Limitations](docs/METHODOLOGY.md#7-limitations).

## NASA data and resources

| Resource | Use | Link |
|---|---|---|
| MERRA-2 reanalysis, NASA GMAO | All five variables, monthly, 1981–2025 | https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/ |
| NASA POWER Monthly and Annual API v2.10.0, NASA LaRC | Regional data access (parameters `T2M`, `PRECTOTCORR`, `QV2M`, `WS10M`, `GWETROOT`) | https://power.larc.nasa.gov/ |
| NASA GIBS, Blue Marble Shaded Relief and Bathymetry | Base map imagery | https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api |

A sixth variable, vegetation greenness (NDVI) from MODIS/Terra MOD13C2 v6.1 (NASA LP DAAC,
https://doi.org/10.5067/MODIS/MOD13C2.061), is supported by the pipeline and tests. It appears in
the app only once a team member's regional files are added to `backend/data/ndvi/`; until then no
NDVI values exist in the app. See [docs/NDVI_HANDOFF.md](docs/NDVI_HANDOFF.md).

MERRA-2 is named in the challenge statement. The exact request URL, retrieval time, API version,
grid-cell count and missing-month count for every series are recorded in
[`backend/data/processed/provenance.json`](backend/data/processed/provenance.json) and shown in the
dashboard's provenance panel.

## Architecture

```
NASA POWER API ──> backend/terrapulse/power.py ──> data/processed/*.csv + provenance.json
                                                        │
                        backend/terrapulse/stats.py + analysis.py   (NumPy, pandas, SciPy, statsmodels)
                                                        │
                 ┌──────────────────────────────────────┴───────────────────────┐
     FastAPI  (terrapulse/api.py)                              static JSON  (terrapulse/export.py)
     GET /api/analysis/{region}/{variable}                     frontend/public/data/analysis/...
                 └──────────────────────────────────────┬───────────────────────┘
                              Next.js + TypeScript + Tailwind dashboard
                              MapLibre GL map, Plotly charts
```

The dashboard reads the same JSON contract from either source. The public demo uses the static
snapshot so it has no server to fail; set `NEXT_PUBLIC_API_URL` to use the live API.

## Run it

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+.

```bash
# backend: tests, then the API on http://localhost:8000
cd backend
uv sync
uv run pytest
uv run uvicorn terrapulse.api:app --reload

# frontend on http://localhost:3000 (uses the committed static snapshot by default)
cd frontend
npm ci
npm run dev
# or against the live API:
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Reproduce the data and results

```bash
cd backend
uv run python -m terrapulse.power --force   # re-download every series from NASA POWER
uv run python -m terrapulse.export          # recompute all statistics and rewrite the static JSON
uv run pytest                               # 62 tests (1 skipped until NDVI files are delivered)
```

No credentials are needed. NASA may revise MERRA-2 or POWER, so a later download can differ
slightly from the committed snapshot; `provenance.json` records when each series was retrieved.

## Tests

`backend/tests` checks the statistics against independent references: statsmodels (OLS slope,
standard error, p-value, interval), pymannkendall (Mann–Kendall S, tau, Z, p; Hamed–Rao correction;
Sen's slope), a hand calculation of the Weatherhead formula, and synthetic series with known trends,
including a simulation showing that the persistence-adjusted test keeps the false-positive rate
near 5% where the naive test exceeds 25%. It also checks the area weighting, fill-value handling,
the completeness and physical plausibility of the committed NASA series, and the API contract.
A further set checks that the static JSON served by the public site equals what the code computes,
and covers the NDVI path: file validation, the regional reduction of gridded MOD13C2 data, a record
with a different date range, and series with seasonal gaps.
Synthetic data are used only in tests, in temporary folders, never in the app.

## Resources, licenses and credits

| Resource | License |
|---|---|
| NASA MERRA-2, NASA POWER, NASA GIBS | NASA open data, no restrictions on use; please cite |
| Next.js, React, Tailwind CSS, FastAPI, uvicorn, httpx | MIT |
| MapLibre GL JS, NumPy, pandas, SciPy, statsmodels | BSD-3-Clause |
| xarray (Apache-2.0), netCDF4-python (MIT): used only by the NDVI reduction script | as stated |
| Plotly.js, pymannkendall (tests only), pytest (tests only) | MIT |

Methods: Sen (1968); Mann (1945); Kendall (1975); Hamed & Rao (1998); Weatherhead et al. (1998);
Santer et al. (2008); Benjamini & Hochberg (1995). Full references are in the methodology.

Data citation: Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and
Applications, Version 2 (MERRA-2). *Journal of Climate*, 30, 5419–5454. Data obtained from the NASA
Langley Research Center POWER Project, funded through the NASA Earth Science Directorate Applied
Science Program.

## Use of Super Intelligence (SI) tools

The code, tests and documentation in this repository were generated with an SI coding assistant
(Anthropic Claude, via Claude Code) during the hackathon on November 14–15, 2026, working from the
team's brief and plan. The team chose the challenge, the product direction (a trend tool that
checks significance, date sensitivity and detectability) and the technology stack. The SI tool
selected the specific regions and the five MERRA-2 variables, wrote the implementation, and drafted
this documentation. Vegetation greenness (MODIS NDVI) was chosen by the team and its data prepared
by a team member; the SI tool wrote the loader and its tests. All statistics are computed by the code from NASA data and are verified by the test
suite against independent libraries; none are SI-generated numbers. No SI-generated images, audio or
video are included. No NASA logos or branding are used.

## License

[MIT](LICENSE). TerraPulse is not an official NASA product and is not endorsed by NASA.
