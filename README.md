# TerraPulse

**Find a trend in NASA Earth-system data. Then find out whether you should believe it.**

TerraPulse is Team Orbital Alpha's entry for the NASA Space Apps Challenge 2026 challenge
[Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/)

- Live demo: https://crollila.github.io/terrapulse/
- Methodology: [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
- API contract: [docs/API.md](docs/API.md)
- NDVI file specification: [docs/NDVI_HANDOFF.md](docs/NDVI_HANDOFF.md)
- Scientific validation review and what was done about it: [SCIENTIFIC_VALIDATION.md](SCIENTIFIC_VALIDATION.md)
- 30-second demo script: [docs/DEMO.md](docs/DEMO.md)

## What it does

Pick a variable and a region on the map. TerraPulse shows the monthly NASA time series (MERRA-2
weather variables for 1981–2025, MODIS vegetation greenness from 2000) and answers the challenge's
four questions:

| Question | How TerraPulse answers it |
|---|---|
| What is changing? | Six variables with plain-language definitions: air temperature, precipitation, humidity, wind speed, root-zone soil wetness, vegetation greenness (NDVI) |
| Where? | Eight region boxes on an interactive map, coloured by the direction and significance of their trend |
| How much? | Rate of change per decade (least squares and Sen's slope) with a 95% confidence interval |
| Is it significant? | A t-test and a Mann–Kendall test, both corrected for month-to-month persistence |

It then goes one step further and tries to break its own result:

- **Did you just pick good dates?** The trend is recomputed for every start/end-year window of
  15 years or more (496 for a 1981–2025 record) and shown as a heat map. A trend that flips sign
  with the dates is labelled as such.
- **Did you just test many places?** A false-discovery-rate correction is applied across regions.
- **No trend, or not enough data?** When no significant trend is detected, TerraPulse estimates how
  many years of data would be needed to detect one of that size (Weatherhead et al. 1998).
- **Does a second dataset see it too?** For rainfall and temperature the same trend is computed
  from an independent record (GPCP and NASA GISTEMP), and the app says whether the two agree.
- **Is there a known problem in the data?** Where a change in how a dataset was built is documented
  for a region, the app says so and tests it. One case so far: MERRA-2 rainfall in the
  south-western Amazon, which shifts against GPCP in 2005.
- **How do two places compare?** Any region can be overlaid on another for the same variable, with
  both slopes, their 95% ranges and each region's second opinion. The plotted series downloads as CSV.

Each result gets one of four verdicts: *holds across dates*, *depends on dates*, *tests disagree*,
or *not detected*. A verdict describes one dataset. The second opinion, where there is one,
says whether another record backs it. Neither claims a cause.

**Detected is not validated.** A verdict says a trend is statistically detectable in one dataset.
Saying the environment really changed by that amount needs an independent record that agrees and a
check for known problems in how the data were made. TerraPulse does the first, does the second
for rainfall and temperature, and does the third for one documented case.

## Results in the current data snapshot

Full-record trends per decade with 95% confidence intervals, from the committed data (retrieved
2026-11-14). The tables are copied from the output of `backend/terrapulse/analysis.py`, and a test
fails if the second-opinion column stops matching the data.

**Air temperature (°C per decade), 1981–2025**

| Region box | MERRA-2 trend [95% range] | Verdict within MERRA-2 | NASA GISTEMP v4 trend [95% range] | Second opinion |
|---|---|---|---|---|
| Colorado | +0.33 [+0.21, +0.45] | holds across dates | +0.26 [+0.15, +0.36] | supported |
| Northern Alaska | +0.51 [+0.32, +0.70] | holds across dates | +0.41 [+0.23, +0.58] | supported |
| Southwestern Amazon (Rondônia) | +0.49 [+0.35, +0.62] | holds across dates | +0.25 [+0.19, +0.31] | direction supported, size differs |
| Northern Morocco | +0.26 [+0.17, +0.36] | depends on dates | +0.36 [+0.28, +0.43] | supported |
| Central Sahel | +0.14 [+0.04, +0.24] | depends on dates | +0.23 [+0.17, +0.29] | supported |
| Punjab and the north-west Indian plains | −0.03 [−0.16, +0.10] | depends on dates | +0.29 [+0.21, +0.36] | **second record finds a trend MERRA-2 does not** |
| Malay Peninsula and Strait of Malacca | +0.19 [+0.14, +0.24] | holds across dates | +0.19 [+0.13, +0.24] | supported |
| Southern Murray–Darling Basin | +0.25 [+0.14, +0.37] | holds across dates | +0.26 [+0.18, +0.33] | supported |

**Precipitation (mm/day per decade), 1981–2025**

| Region box | MERRA-2 trend [95% range] | Verdict within MERRA-2 | GPCP v2.3 trend [95% range] | Second opinion |
|---|---|---|---|---|
| Colorado | −0.023 [−0.055, +0.010] | not detected | −0.035 [−0.067, −0.004] | **second record finds a trend MERRA-2 does not** |
| Northern Alaska | +0.045 [+0.005, +0.084] | depends on dates | +0.046 [+0.015, +0.076] | supported |
| Southwestern Amazon (Rondônia) | −0.541 [−0.641, −0.441] | holds across dates | −0.282 [−0.372, −0.192] | direction supported, size differs; **known data issue (2005)** |
| Northern Morocco | +0.011 [−0.048, +0.070] | not detected | −0.028 [−0.080, +0.023] | also no significant trend |
| Central Sahel | +0.098 [+0.044, +0.152] | depends on dates | +0.102 [+0.059, +0.146] | supported |
| Punjab and the north-west Indian plains | +0.188 [+0.109, +0.267] | depends on dates | +0.040 [−0.028, +0.108] | **not confirmed** |
| Malay Peninsula and Strait of Malacca | +0.426 [+0.302, +0.549] | holds across dates | +0.028 [−0.079, +0.135] | **not confirmed** |
| Southern Murray–Darling Basin | −0.017 [−0.081, +0.046] | not detected | +0.000 [−0.063, +0.064] | also no significant trend |

**Vegetation greenness (NDVI per decade), February 2000 – October 2026 (MODIS MOD13C2; no second dataset checked)**

| Region box | Trend [95% range] | Verdict | Months used |
|---|---|---|---|
| Colorado | +0.0035 [−0.0075, +0.0144] | not detected | 290 of 321 |
| Northern Alaska | +0.0140 [+0.0059, +0.0221] | holds across dates | 108 of 321 |
| Southwestern Amazon (Rondônia) | −0.0079 [−0.0122, −0.0036] | holds across dates | 321 of 321 |
| Northern Morocco | −0.0002 [−0.0127, +0.0124] | not detected | 321 of 321 |
| Central Sahel | +0.0110 [+0.0049, +0.0170] | holds across dates | 321 of 321 |
| Punjab and the north-west Indian plains | +0.0340 [+0.0280, +0.0400] | holds across dates | 321 of 321 |
| Malay Peninsula and Strait of Malacca | +0.0043 [+0.0019, +0.0067] | holds across dates | 321 of 321 |
| Southern Murray–Darling Basin | +0.0223 [−0.0109, +0.0556] | not detected | 321 of 321 |

### How to read these

- **Temperature.** Six of the eight MERRA-2 warming trends are supported by GISTEMP. In the
  southwestern Amazon box both records warm, but MERRA-2 warms about twice as fast. In the Punjab
  box MERRA-2 shows no warming while GISTEMP shows significant warming.
- **Rainfall.** MERRA-2's large rainfall increases in the Malay Peninsula and Punjab boxes are
  **not confirmed** by GPCP, which shows no significant change in either. The MERRA-2 decline in
  the southwestern Amazon box is confirmed in direction, but GPCP's rate is about half as large.
  The two records agree in northern Alaska and the central Sahel (increase) and in northern
  Morocco and the southern Murray–Darling (no detectable trend). In the Colorado box GPCP finds a
  small significant decline that MERRA-2 does not.
- **A documented data problem explains most of the Amazon gap.** NASA's evaluation of MERRA-2
  rainfall (Reichle et al. 2017) shows its gauge-corrected rainfall dropping against GPCP across
  the Amazon from 2005, when the number of rain gauges behind the correction falls sharply. A team
  member's validation review ([SCIENTIFIC_VALIDATION.md](SCIENTIFIC_VALIDATION.md)) pointed to it,
  and the tool now tests it for this box. MERRA-2 ran 0.13 mm/day below GPCP in 1981–2004 and
  0.99 mm/day below it from 2005. Fitted as a jump in 2005 with a steady drift allowed, the jump is
  −1.07 mm/day (95% range −1.51 to −0.63) and no significant drift is left; 2005 is also the
  best-fitting break year. Taken separately, the two periods give −0.14 against −0.14 mm/day per
  decade before 2005 (neither significant) and −0.59 against −0.83 from 2005 (both significant).
  So much of MERRA-2's faster full-record decline probably comes from how the dataset was built.
  Both records show a decline; neither confirms how fast. Soil wetness in the same box is driven by
  the same rainfall and carries the same caveat, untested. A check against a third rainfall record
  (CHIRPS) has not been done.
- **Do not cite the unconfirmed MERRA-2 trends as findings.** MERRA-2 is a reanalysis: a model
  constrained by observations, and changes in those observations over time can create trends.
  Three of its results here (rainfall in the Malay Peninsula and Punjab boxes, temperature in the
  Punjab box) disagree with an independent record, and a fourth and fifth (rainfall and
  temperature in the southwestern Amazon box) are about twice the size the independent record shows.
- **Agreement is support, not proof.** GPCP cells are 2.5° wide and GISTEMP smooths over up to
  1200 km, so both are coarse next to the region boxes, and both have their own weaknesses.
- **Humidity, wind speed, soil wetness and NDVI have no second dataset here.** Their results
  describe one dataset only. The app says so on every one of them.

## Regions

A region is a latitude/longitude rectangle, not a basin, state or country. The names say what each
rectangle really covers. For the MERRA-2 weather variables, sea cells inside a box are part of the
average; soil wetness and NDVI exist over land only.

| Region box | West–East, South–North | Land in the box | What the box covers |
|---|---|---|---|
| Colorado (`upper-colorado`) | 109°W–102°W, 37°N–41°N | all | A box matching the state of Colorado: the Rocky Mountains, where the Colorado, Rio Grande, Arkansas and South Platte rivers rise, and the high plains to the east. |
| Northern Alaska (`north-slope`) | 160°W–150°W, 66°N–71°N | 97% | Arctic tundra and permafrost: the North Slope and the Brooks Range, with a strip of interior Alaska to the south and a little of the Arctic Ocean. |
| Southwestern Amazon (Rondônia) (`rondonia`) | 66°W–60°W, 13°S–8°S | all | Tropical rainforest with extensive land clearing since the 1980s. The box covers the Brazilian state of Rondônia and neighbouring parts of Bolivia and of other Brazilian states. |
| Northern Morocco (`moroccan-atlas`) | 10°W–2°W, 30°N–35°N | 83% | Mediterranean-to-desert transition across the Atlas Mountains and the Atlantic plains. About a sixth of the box is sea. |
| Central Sahel (`central-sahel`) | 0°E–10°E, 12°N–17°N | all | Semi-arid belt between the Sahara and the West African savanna, from eastern Burkina Faso across southern Niger and northern Nigeria. |
| Punjab and the north-west Indian plains (`punjab-plain`) | 71°E–78°E, 28°N–33°N | all | Intensively irrigated farmland of the upper Indus plain and north-west India, with part of the Thar Desert in the south and Himalayan foothills in the north-east. |
| Malay Peninsula and Strait of Malacca (`malay-peninsula`) | 99°E–105°E, 1°N–7°N | 52% | Humid equatorial land and sea with two monsoon seasons: Peninsular Malaysia, eastern Sumatra and the waters around them. About half of the box is sea. |
| Southern Murray–Darling Basin (`murray-darling`) | 140°E–149°E, 37°S–30°S | all | Australia's main agricultural river basin, prone to multi-year drought. The box covers its southern half and some land just outside it. |

Land share is counted on the 0.2° MODIS grid (pixels with at least one valid NDVI value).

## Data and resources

| Resource | Use | Link |
|---|---|---|
| MERRA-2 reanalysis, NASA GMAO | Five weather and soil variables, monthly, 1981–2025 | https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/ |
| MODIS/Terra Vegetation Indices Monthly 0.05° (MOD13C2 v6.1), NASA LP DAAC | Vegetation greenness (NDVI), monthly, February 2000 – October 2026 | https://doi.org/10.5067/MODIS/MOD13C2.061 |
| NASA POWER Monthly and Annual API v2.10.0, NASA LaRC | Regional access to the MERRA-2 parameters `T2M`, `PRECTOTCORR`, `QV2M`, `WS10M`, `GWETROOT` | https://power.larc.nasa.gov/ |
| NASA GISTEMP v4, NASA GISS | Second opinion on temperature trends | https://data.giss.nasa.gov/gistemp/ |
| GPCP Monthly Analysis v2.3 (Adler et al. 2018) | Second opinion on rainfall trends | https://psl.noaa.gov/data/gridded/data.gpcp.html |
| NOAA Physical Sciences Laboratory THREDDS server | Access to the GISTEMP and GPCP grids (OPeNDAP, no login) | https://psl.noaa.gov/ |
| NASA GIBS, Blue Marble Shaded Relief and Bathymetry | Base map imagery | https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api |

MERRA-2 and MODIS are named in the challenge statement. For every series, the exact request, the
retrieval time, the grid-cell count and the missing-month count are recorded in
[`backend/data/processed/provenance.json`](backend/data/processed/provenance.json),
[`backend/data/ndvi/provenance.json`](backend/data/ndvi/provenance.json) and
[`backend/data/crosscheck/provenance.json`](backend/data/crosscheck/provenance.json), and shown in
the dashboard.

NDVI was downloaded from NASA LP DAAC and reduced to regional monthly means by a team member
(Kawtar Ag): 0.05° pixels were averaged to 0.2° after removing the fill value, and only pixels
graded good or marginal by the product's pixel-reliability layer were kept, so snow, cloud and
values NASA filled in from the long-term average are excluded. The format and the checks applied
to the files are in [docs/NDVI_HANDOFF.md](docs/NDVI_HANDOFF.md).

## Architecture

```
NASA POWER API ──> terrapulse/power.py ──────> data/processed/*.csv   (MERRA-2, five variables)
MOD13C2 grids ───> terrapulse/ndvi_regions.py ─> data/ndvi/*.csv        (NDVI, prepared by a team member)
GPCP, GISTEMP ───> terrapulse/crosscheck.py ──> data/crosscheck/*.csv  (second opinions)
                                    │
               terrapulse/stats.py + analysis.py   (NumPy, pandas, SciPy, statsmodels)
                                    │
            ┌───────────────────────┴────────────────────────┐
 FastAPI  (terrapulse/api.py)                 static JSON  (terrapulse/export.py)
 GET /api/analysis/{region}/{variable}        frontend/public/data/analysis/...
            └───────────────────────┬────────────────────────┘
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
uv run python -m terrapulse.power --force   # re-download the MERRA-2 series from NASA POWER
uv run python -m terrapulse.crosscheck      # re-download the GPCP and GISTEMP regional series
uv run python -m terrapulse.export          # recompute all statistics and rewrite the static JSON
uv run pytest                               # 84 tests
```

No credentials are needed for these steps. Re-creating the NDVI files from MOD13C2 granules needs a
free NASA Earthdata login and is described in [docs/NDVI_HANDOFF.md](docs/NDVI_HANDOFF.md). NASA
and NOAA revise their products, so a later download can differ slightly from the committed
snapshot; the provenance files record when each series was retrieved.

## Tests

`backend/tests` checks the statistics against independent references: statsmodels (OLS slope,
standard error, p-value, interval), pymannkendall (Mann–Kendall S, tau, Z, p; Hamed–Rao correction;
Sen's slope), a hand calculation of the Weatherhead formula, and synthetic series with known trends,
including a simulation showing that the persistence-adjusted test keeps the false-positive rate
near 5% where the naive test exceeds 25%. It also checks the area weighting, fill-value handling,
the completeness and physical plausibility of the committed series, and the API contract.
Further tests check that the static JSON served by the public site equals what the code computes,
cover the NDVI path (file validation, the reduction of gridded MOD13C2 data, a record with a
different date range, series with seasonal gaps), and cover the second opinions (grid weighting,
the agreement rule, the committed GPCP and GISTEMP series, and the results quoted above).
The level-shift test used for the documented 2005 break is checked against statsmodels and on
series with and without a planted step, and the Amazon numbers quoted above are pinned by a test.
Synthetic data are used only in tests, in temporary folders, never in the app.

## Resources, licenses and credits

| Resource | License or terms |
|---|---|
| NASA MERRA-2, NASA POWER, NASA GIBS, NASA MODIS MOD13C2, NASA GISTEMP | NASA open data, no restrictions on use; please cite |
| GPCP v2.3 (via NOAA PSL) | Freely available; cite Adler et al. (2018) and acknowledge NOAA PSL |
| Next.js, React, Tailwind CSS, Plotly.js, FastAPI, netCDF4-python, ESLint (development), pytest and pymannkendall (tests) | MIT |
| MapLibre GL JS, NumPy, pandas, SciPy, statsmodels, uvicorn, httpx | BSD-3-Clause |
| xarray, TypeScript | Apache-2.0 |
| uv (Python package manager), Node.js and npm (JavaScript runtime and package manager) | MIT or Apache-2.0 (uv); MIT and Artistic-2.0 (Node.js, npm) |
| GitHub Actions and GitHub Pages | Hosting and continuous integration services |

Methods: Sen (1968); Mann (1945); Kendall (1975); Hamed & Rao (1998); Weatherhead et al. (1998);
Santer et al. (2008); Benjamini & Hochberg (1995). Full references are in the methodology.

Literature used to check results:

- Reichle, R. H., et al. (2017). Land Surface Precipitation in MERRA-2. *Journal of Climate*,
  30(5), 1643–1664. https://doi.org/10.1175/JCLI-D-16-0570.1 (the 2005 discontinuity)
- Reichle, R. (2023). *The Land Surface in Earth System Reanalysis*. ECMWF Annual Seminar,
  Reading, UK. NASA NTRS 20230012995, slide 12. https://ntrs.nasa.gov/citations/20230012995
- Moreira, R. M., et al. (2023). Precipitation Variability for Protected Areas of Primary Forest
  and Pastureland in Southwestern Amazônia. *Climate*, 11(2), 27.
  https://doi.org/10.3390/cli11020027 (declining rainfall in parts of Rondônia, 1981–2020, from
  CHIRPS; a different area, dataset and period, so context rather than confirmation)
- The other sources cited by the validation review are listed in
  [SCIENTIFIC_VALIDATION.md](SCIENTIFIC_VALIDATION.md).

Data citations:

- Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications,
  Version 2 (MERRA-2). *Journal of Climate*, 30, 5419–5454. Data obtained from the NASA Langley
  Research Center POWER Project, funded through the NASA Earth Science Directorate Applied Science
  Program.
- Didan, K. (2021). *MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061* [Data set].
  NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MOD13C2.061
- GISTEMP Team (2026). *GISS Surface Temperature Analysis (GISTEMP), version 4*. NASA Goddard
  Institute for Space Studies. https://data.giss.nasa.gov/gistemp/. Lenssen, N., et al. (2019).
  Improvements in the GISTEMP uncertainty model. *J. Geophys. Res. Atmos.*, 124, 6307–6326.
- Adler, R. F., et al. (2018). The Global Precipitation Climatology Project (GPCP) Monthly Analysis
  (New Version 2.3) and a Review of 2017 Global Precipitation. *Atmosphere*, 9(4), 138. GPCP and
  GISTEMP grids were provided by the NOAA PSL, Boulder, Colorado, USA, from https://psl.noaa.gov

## Who did what

- **NASA data engineering (Kawtar Ag, GitHub `kawtarAg`):** selected, downloaded and processed the
  MODIS MOD13C2 vegetation data into the regional NDVI files (pull request #8).
- **Dashboard (Muhammad Rehan Farooq, GitHub `rehanfarooq1911`):** the side-by-side region
  comparison and the CSV download (pull request #11).
- **Scientific research and validation (GitHub `DerekKered044`):** the independent validation
  review (pull request #12) that pointed to the documented 2005 discontinuity in MERRA-2 rainfall
  over the Amazon and to the wording of the map colours and several labels.
- **Presentation and demo:** a team member (see the team page on spaceappschallenge.org).
- **Team lead (GitHub `crollila`):** direction, decisions, review and merging.
- **SI coding assistant:** see the next section.

## Use of Super Intelligence (SI) tools

SI tools were used in planning this project as well as in building it. This section says where.

**Conception.** The team chose the challenge. Before the hackathon the team lead worked with an SI
assistant (Anthropic Claude) to study the challenge statement and to write a private planning note
that listed candidate approaches. The approach built here was one of them: test a trend against
month-to-month persistence, against the choice of start and end dates and against the number of
places tested, and ask how long a record would be needed to detect it. At the start of the
hackathon an SI coding session picked that approach from the note and began building it; the team
lead reviewed the result and kept it. Nothing was built before the hackathon began. Adding
satellite vegetation data (MODIS NDVI) was the team's own plan, and a team member selected,
downloaded and processed that data.

**Construction.** An SI coding assistant (Anthropic Claude, via Claude Code) generated most of the
code, the tests and this documentation during the hackathon on November 14–15, 2026. It chose the
eight region boxes and the five MERRA-2 variables. It also carried out the review that added the
independent second opinions (GPCP and GISTEMP), corrected the region names and removed claims the
second opinions did not support. The team lead directed that work and decided what was merged.

The side-by-side comparison and the validation review were contributed by team members (see "Who
did what"). The SI assistant reviewed and integrated both, wrote the fixes on top of the
comparison (caption wording, chart legend), implemented the 2005 level-shift test that the
validation review recommended, and wrote the follow-up sections of SCIENTIFIC_VALIDATION.md.

**What is not SI-generated.** Every number in the app is computed by the code from NASA and
NOAA-hosted data, and the statistics are verified by tests against independent libraries. No
SI-generated images, audio or video are included. No NASA logos or branding are used.

SI use is also acknowledged in the source (`backend/terrapulse/__init__.py`), in the page footer,
in the page metadata and in the commit history.

## License

[MIT](LICENSE). TerraPulse is not an official NASA product and is not endorsed by NASA.
