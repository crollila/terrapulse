# Project submission draft

Draft text for the fields of the Space Apps project page. **Nothing here has been submitted.**
The Team Owner must review every claim, add the demo link, and press "Submit for Judging" before
Sunday November 15, 23:59 in the Team Owner's local time (MST). A project saved or submitted after
that time is not eligible, and only the last saved version is judged.

The code was frozen on November 15, 2026. This text describes the frozen version.

Items marked **TEAM OWNER** need a person's decision or knowledge and cannot be settled from the
repository.

## Project name

TerraPulse

## High-level project summary

TerraPulse is an interactive web tool that turns students and curious members of the public into
Earth-system trend detectives. Choose a variable and a region on a map; TerraPulse plots decades
of NASA data (MERRA-2 weather variables since 1981, MODIS vegetation greenness since 2000), removes
the seasonal cycle, measures the rate of change with a confidence interval, and tests whether the
trend is statistically significant. It then tries to break its own answer. It recomputes the trend
for every possible start and end year to show whether the result depends on cherry-picked dates,
corrects for testing many regions at once, and, where no trend is detected, estimates how many
years of data would be needed to detect one. For rainfall and temperature it also asks a second,
independent dataset the same question and says plainly whether the two agree, and it flags and
tests a documented problem in one of NASA's own datasets. This matters because a trend line and
"p < 0.05" are easy to produce and easy to get wrong: a trend that is detected is not yet a change
that is validated, and learning to ask "should I believe this?" is the core skill of a data
detective.

## Link to project demo

**TEAM OWNER:** a video of 30 seconds or less, **or** a deck of at most 7 slides including the
title slide, at a public link that opens without a login. Exceeding either limit makes the project
ineligible for Global Judging. English, or English subtitles. No one under 18 shown. SI-generated
images or video need a visible watermark. A shot-by-shot script with narration, and a 7-slide
outline, are in [DEMO.md](DEMO.md).

## Link to final project

- Live tool: https://crollila.github.io/terrapulse/
- Source code: https://github.com/crollila/terrapulse

## Detailed project description

**What it does.** Six variables (air temperature, precipitation, humidity, wind speed, root-zone
soil wetness from 1981 to 2025, and satellite vegetation greenness from 2000) for eight region
boxes on six continents, monthly. For each combination the dashboard shows: a map coloured by
trend direction and significance; the raw and deseasonalised time series with the fitted trend and
its 95% range; the slope per decade by least squares and by Sen's method; a t-test and a
Mann–Kendall test, both corrected for month-to-month persistence, with a plain-language
explanation of what a p-value means; a heat map of the trend for every start/end-year window; a
comparison of all regions with a false-discovery-rate correction; the number of years needed to
detect a trend of that size; a second opinion from an independent dataset where one exists; a note
where a data problem is documented; and a data-quality and provenance panel. Any two regions can
be overlaid on one chart, and the plotted series can be downloaded as CSV. Four guided "case
files" show how to use it.

**How it works.** A Python pipeline downloads regional MERRA-2 grids from the NASA POWER API,
reads MODIS NDVI regional means prepared by a team member from MOD13C2 granules, forms
area-weighted regional means, and computes all statistics with NumPy, pandas, SciPy and
statsmodels. A FastAPI service serves the results; the same JSON is exported as static files for
the public demo. The interface is Next.js, TypeScript and Tailwind CSS with a MapLibre map over
NASA GIBS Blue Marble imagery and Plotly charts. Eighty-four automated tests verify the
statistics against statsmodels, pymannkendall, hand calculations and synthetic series with known
trends, and check the delivered data files and the published numbers.

**What we found.** In MERRA-2, air temperature rose significantly in seven of the eight region
boxes, fastest in northern Alaska (+0.51 °C per decade, 95% range +0.32 to +0.70). NASA GISTEMP,
an independent record, supports six of those trends and also puts northern Alaska first (+0.41).

The most useful finding was a warning. In the south-western Amazon box, MERRA-2 shows rainfall
falling by 0.54 mm/day per decade, significant in both tests and stable across nearly every choice
of dates. The independent GPCP record also shows a decline, but at about half the rate. A team
member's scientific review traced this to NASA's own evaluation of MERRA-2 (Reichle et al. 2017),
which documents its gauge-corrected rainfall dropping against GPCP over the Amazon from 2005, when
the number of rain gauges behind the correction falls sharply. We tested that on our box: the two
records differ by a jump of 1.07 mm/day in 2005 (95% range 0.63 to 1.51) and agree within their
ranges before and after it. So much of MERRA-2's faster decline probably comes from how the
dataset was built. Both records show rainfall falling there; neither confirms how fast, and we do
not say why.

MERRA-2 also shows rainfall rising steeply near the Malay Peninsula and in the Punjab region; both
trends are statistically significant, yet GPCP shows no significant change in either. MODIS
vegetation greenness rose significantly in the Punjab, central Sahel, northern Alaska and Malay
Peninsula boxes and fell in the south-western Amazon box; those NDVI results have no second
dataset yet.

A trend can be statistically solid inside one dataset and still not be real at that size, which is
why the tool shows a second opinion beside every rainfall and temperature verdict.

**Limitations we state in the tool.** Regions are rectangles, not basins or countries, and some
include sea. Humidity, wind speed, soil wetness and NDVI have no independent check. Agreement
between two datasets is support, not proof. The Amazon result was not checked against a third
rainfall record. Trends are linear, and a significant trend says nothing about its cause.

**Benefits and goals.** Users learn that significance depends on noise, persistence and the dates
chosen, that "not significant" can mean "not enough data", that one dataset is not enough, and
that detected is not the same as validated. The pipeline is reproducible and can be extended to
more regions, variables and datasets.

**Tools.** Python, FastAPI, NumPy, pandas, SciPy, statsmodels, xarray, pytest; TypeScript, Next.js,
React, Tailwind CSS, MapLibre GL JS, Plotly.js; GitHub Actions and GitHub Pages.

## Use of Super Intelligence (SI)

Yes, in planning and in building.

Before the hackathon the team lead worked with an SI assistant (Anthropic Claude) to study the
challenge statement and write a private planning note listing candidate approaches. The approach
built here (testing a trend against persistence, date choice and multiple testing, and estimating
the record length needed to detect it) was one of them. At the start of the hackathon an SI coding
session picked that approach from the note and began building it; the team lead reviewed the
result and kept it. Adding MODIS vegetation data was the team's own plan, and a team member
selected, downloaded and processed that data.

During the hackathon an SI coding assistant (Anthropic Claude, via Claude Code) generated most of
the code, tests and documentation, chose the eight region boxes and the five MERRA-2 variables,
and carried out the review that added the independent second opinions, corrected the region names
and removed unsupported claims. Team members contributed the side-by-side region comparison and
the scientific validation review; the SI assistant reviewed and integrated both, wrote fixes on
top of the comparison, and implemented the 2005 level-shift test that the validation review
recommended. The team lead directed that work and decided what was merged.

All statistics are computed by the code from NASA and NOAA-hosted data and checked by automated
tests; none are SI-generated numbers. SI use is acknowledged in the README, the source header, the
page footer and the page metadata. No SI-generated images, audio or video are used in the tool. No
NASA branding is used.

**TEAM OWNER:**

1. The Project Submission Guide says SI "should not be used to (come up with your idea of how to
   solve the challenge)". The paragraphs above are written from the project's own records. Only
   you know how the idea actually developed, including what you brought to the planning note
   yourself. Correct anything that is wrong, in either direction, before submitting. The same text
   is in the README, so change both.
2. Ask each team member whether they used SI tools for their own contribution (the NDVI
   processing, the comparison feature, the validation review, the demo). The statement above only
   covers the SI assistant's own work. If they did, add one sentence saying so here and in the
   README. If the demo uses an SI voice, image or video, say so and watermark it.

## NASA data

- MERRA-2 reanalysis (NASA GMAO): `T2M`, `PRECTOTCORR`, `QV2M`, `WS10M`, `GWETROOT`, monthly, 1981–2025.
- MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061 (MOD13C2), NASA LP DAAC: NDVI, monthly, February 2000 – October 2026. https://doi.org/10.5067/MODIS/MOD13C2.061
- NASA POWER Monthly and Annual API v2.10.0 (NASA LaRC): regional data access. https://power.larc.nasa.gov/
- NASA GISTEMP v4 (NASA GISS): independent check of temperature trends. https://data.giss.nasa.gov/gistemp/
- NASA GIBS Blue Marble Shaded Relief and Bathymetry: base map imagery.

## Space Agency Partner data and other references

No Space Agency Partner data are used.

Other data: GPCP Monthly Analysis v2.3 (Adler et al. 2018), used as an independent check of
rainfall trends; GPCP and GISTEMP grids were read from the NOAA Physical Sciences Laboratory
(https://psl.noaa.gov).

Software: Next.js, React, Tailwind CSS, TypeScript, MapLibre GL JS, Plotly.js, ESLint, Node.js and
npm; Python, FastAPI, uvicorn, httpx, NumPy, pandas, SciPy, statsmodels, xarray, netCDF4-python,
pytest, pymannkendall, uv; GitHub Actions and GitHub Pages. SI tool: Anthropic Claude (Claude Code).

Methods and data papers: Sen (1968); Mann (1945); Kendall (1975); Hamed & Rao (1998); Weatherhead
et al. (1998); Santer et al. (2008); Benjamini & Hochberg (1995); Gelaro et al. (2017, MERRA-2);
Didan (2021, MOD13C2); Lenssen et al. (2019, GISTEMP); Adler et al. (2018, GPCP).

Literature used to check results: Reichle et al. (2017), Land Surface Precipitation in MERRA-2,
*Journal of Climate* 30(5), 1643–1664, https://doi.org/10.1175/JCLI-D-16-0570.1; Reichle (2023),
The Land Surface in Earth System Reanalysis, NASA NTRS 20230012995,
https://ntrs.nasa.gov/citations/20230012995; Moreira et al. (2023), *Climate* 11(2), 27,
https://doi.org/10.3390/cli11020027. The team's validation review cites further background
sources (Cui et al. 2026; Polasky et al. 2025; Mu et al. 2023; Guo et al. 2024; Zeng et al. 2023;
NOAA Arctic Report Card 2025), listed in full in SCIENTIFIC_VALIDATION.md.

Full citations and licenses are in the README, docs/METHODOLOGY.md and SCIENTIFIC_VALIDATION.md.

No images, text or code were copied from other projects.

## Checklist for the submission form

Do these in order. Tick each one yourself.

Before opening the form:

- [ ] Demo finished and within the limit: 30 seconds, or 7 slides including the title. It shows
      what the live tool shows today (see DEMO.md).
- [ ] Demo link, live tool link and source link each open in a private browser window without a
      login.
- [ ] SI statement above read and corrected by you (item 1), and each team member asked about
      their own SI use (item 2).
- [ ] Every team member is registered, in the Universal Event, and listed on the team's Members
      tab (at least two; at most six). Members cannot be added after submission closes.

On the form:

- [ ] Project name: TerraPulse.
- [ ] High-level summary pasted from above.
- [ ] Demo link pasted.
- [ ] Final project link: the live tool, with the source link in the description.
- [ ] Detailed description pasted from above.
- [ ] SI question answered "yes", with the SI statement pasted.
- [ ] NASA data list pasted.
- [ ] Partner data and references pasted.
- [ ] Both boxes can be ticked truthfully: the terms and guide, and "original work with every
      external resource listed in References".
- [ ] Everything is in English.

Submitting:

- [ ] "Submit for Judging" pressed well before Sunday 23:59 MST.
- [ ] The confirmation is on screen, and the page is not saved again afterwards.
- [ ] Optional: request a FortiGuard web filter classification for the demo URL (see the guide).

## Open in the science

- [ ] Humidity, wind speed, soil wetness and NDVI have no independent check.
- [ ] The Amazon rainfall result has not been compared with a third record such as CHIRPS.
- [ ] The second opinions use coarse grids (2.5° and 2°); a finer rainfall product such as GPM
      IMERG would be a better test.
- [ ] The disagreements in the Malay Peninsula and Punjab boxes have not been traced to a cause.
