# Project submission draft

Draft text for the fields of the Space Apps project page. **Nothing here has been submitted.**
The team must review every claim, add the demo link, and press "Submit for Judging" before
Sunday November 15, 23:59 in the Team Owner's local time.

## Project name

TerraPulse

## High-level project summary

TerraPulse is an interactive web tool that turns students and curious members of the public into
Earth-system trend detectives. Choose a variable and a region on a map; TerraPulse plots 45 years
of NASA MERRA-2 data, removes the seasonal cycle, measures the rate of change with a confidence
interval, and tests whether the trend is statistically significant. It then tries to break its own
answer. It recomputes the trend for every possible start and end year to show whether the result
depends on cherry-picked dates, corrects for testing many regions at once, and, where no trend is
detected, estimates how many years of data would be needed to detect one. Each result is summarised
in one plain-language verdict. This matters because a trend line and "p < 0.05" are easy to produce
and easy to get wrong: learning to ask "should I believe this?" is the core skill of a data
detective.

## Link to project demo

TODO: 30-second video **or** a deck of at most 7 slides, at a public link (see issue #5).

## Link to final project

- Live tool: https://crollila.github.io/terrapulse/
- Source code: https://github.com/crollila/terrapulse

## Detailed project description

**What it does.** Five variables (air temperature, precipitation, humidity, wind speed, root-zone
soil wetness) for eight regions on six continents, monthly from 1981 to 2025. For each combination
the dashboard shows: a map coloured by trend direction and significance; the raw and deseasonalised
time series with the fitted trend and its 95% range; the slope per decade by least squares and by
Sen's method; a t-test and a Mann–Kendall test, both corrected for month-to-month persistence; a
heat map of the trend for all 496 start/end-year windows; a comparison of all regions with a
false-discovery-rate correction; the number of years needed to detect a trend of that size; and a
data-quality and provenance panel linking to the exact NASA request. Four guided "case files" show
how to use it.

**How it works.** A Python pipeline downloads regional MERRA-2 grids from the NASA POWER API,
forms an area-weighted regional mean, and computes all statistics with NumPy, pandas, SciPy and
statsmodels. A FastAPI service serves the results; the same JSON is exported as static files for
the public demo. The interface is Next.js, TypeScript and Tailwind CSS with a MapLibre map over
NASA GIBS Blue Marble imagery and Plotly charts. More than sixty automated tests verify the statistics
against statsmodels, pymannkendall, hand calculations and synthetic series with known trends.

**What we found.** In this dataset, air temperature rose significantly in seven of the eight
regions, fastest on the Alaska North Slope (+0.51 °C per decade, 95% range +0.32 to +0.70).
Precipitation shows opposite significant trends in two tropical regions. Several results change
with the dates chosen, and several are not detectable yet. These are trends in a reanalysis and
have not been validated against independent observations; see the limitations in the methodology.

**Benefits and goals.** Users learn that significance depends on noise, persistence and the dates
chosen, and that "not significant" can mean "not yet". The pipeline is reproducible with no
credentials and can be extended to more regions, variables and datasets.

**Tools.** Python, FastAPI, NumPy, pandas, SciPy, statsmodels, pytest; TypeScript, Next.js, React,
Tailwind CSS, MapLibre GL JS, Plotly.js; GitHub Actions and GitHub Pages.

## Use of Super Intelligence (SI)

Yes. An SI coding assistant (Anthropic Claude, via Claude Code) generated the code, tests and
documentation during the hackathon, working from the team's brief. The team chose the challenge,
the product direction and the technology stack. All statistics are computed by the code from NASA
data and checked by automated tests; none are SI-generated numbers. SI use is acknowledged in the
README, the source file header and the page footer. No SI-generated images, audio or video are
used. No NASA branding is used.

TODO (team): confirm this matches how the idea was actually developed. The guide says SI "should
not be used to come up with your idea of how to solve the challenge".

## NASA data

- MERRA-2 reanalysis (NASA GMAO): `T2M`, `PRECTOTCORR`, `QV2M`, `WS10M`, `GWETROOT`, monthly, 1981–2025.
- NASA POWER Monthly and Annual API v2.10.0 (NASA LaRC): regional data access. https://power.larc.nasa.gov/
- NASA GIBS Blue Marble Shaded Relief and Bathymetry: base map imagery.
- Challenge resources consulted: Giovanni and the challenge statement's list of datasets.

## Space Agency Partner data and other references

No Space Agency Partner data are used. Software: Next.js, React, Tailwind CSS, MapLibre GL JS,
Plotly.js, FastAPI, uvicorn, httpx, NumPy, pandas, SciPy, statsmodels, pytest, pymannkendall, uv.
Methods: Sen (1968); Mann (1945); Kendall (1975); Hamed & Rao (1998); Weatherhead et al. (1998);
Santer et al. (2008); Benjamini & Hochberg (1995); Gelaro et al. (2017). Full citations are in
docs/METHODOLOGY.md.

## Before submitting

- [ ] Science review done (issue #4), or unreviewed claims removed from the text above.
- [ ] Demo within the limit: 30 seconds or 7 slides. Over the limit means ineligible.
- [ ] All links open in a private browser window without a login.
- [ ] Optional: request a FortiGuard web filter classification for the demo URL (see the guide).
- [ ] At least two team members are on the Universal Event team page.
- [ ] Everything is in English.
