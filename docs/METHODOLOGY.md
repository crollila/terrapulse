# TerraPulse methodology

Every number in the dashboard is computed by `backend/terrapulse/` from the NASA series in
`backend/data/processed/` (and, once delivered, `backend/data/ndvi/`). This document states what is
computed, why, and what it cannot tell you.

## 1. Data

| Item | Value |
|---|---|
| Dataset | MERRA-2 reanalysis, NASA Global Modeling and Assimilation Office |
| Access | NASA POWER Monthly and Annual API v2.10.0, regional endpoint, community `AG` |
| Period | January 1981 – December 2025 (540 months) |
| Native grid | 0.5° latitude × 0.625° longitude |
| Missing value flag | −999, converted to missing before any calculation |
| Missing months in the snapshot | 0 in all 40 series |

| Parameter | Meaning | Units |
|---|---|---|
| `T2M` | Temperature at 2 meters | °C |
| `PRECTOTCORR` | Precipitation, bias-corrected in MERRA-2 | mm/day |
| `QV2M` | Specific humidity at 2 meters | g/kg |
| `WS10M` | Wind speed at 10 meters (derived by POWER from MERRA-2 winds) | m/s |
| `GWETROOT` | Root-zone soil wetness | fraction, 0–1 |

| Region id | Name shown | Box (lon west, lat south, lon east, lat north) | Land in the box |
|---|---|---|---|
| `upper-colorado` | Colorado | −109, 37, −102, 41 | all |
| `north-slope` | Northern Alaska | −160, 66, −150, 71 | 97% |
| `rondonia` | Southwestern Amazon (Rondônia) | −66, −13, −60, −8 | all |
| `moroccan-atlas` | Northern Morocco | −10, 30, −2, 35 | 83% |
| `central-sahel` | Central Sahel | 0, 12, 10, 17 | all |
| `punjab-plain` | Punjab and the north-west Indian plains | 71, 28, 78, 33 | all |
| `malay-peninsula` | Malay Peninsula and Strait of Malacca | 99, 1, 105, 7 | 52% |
| `murray-darling` | Southern Murray–Darling Basin | 140, −37, 149, −30 | all |

Regions are rectangles no larger than 10° × 10°, the POWER regional limit. **A rectangle is not a
basin, a state or a country**, and the names describe what each rectangle really covers. For
example `upper-colorado` matches the state of Colorado, plains included, and is not the Upper
Colorado River Basin; `malay-peninsula` is about half sea and includes eastern Sumatra. The ids are
kept because data files are named after them. Land share is counted on the 0.2° MODIS grid (pixels
with at least one valid NDVI value), and a test checks it against the delivered NDVI files.

For the MERRA-2 weather variables the regional mean includes the sea cells in a box, so a trend
for a box that is half sea is partly a trend over the sea. Soil wetness and NDVI exist over land
only. Grid-cell counts are in the provenance files.

**Regional mean.** For each month, the regional value is the mean over all grid cells returned for
the box, weighted by the cosine of each cell's latitude so that cells count in proportion to their
area. Cells with a missing value are left out of that month's mean.

### 1.1 Vegetation greenness (NDVI)

The sixth variable comes from a different NASA source. It is served only while real regional files
are present in `backend/data/ndvi/` and pass validation (`backend/terrapulse/ndvi.py`); no
placeholder values exist anywhere.

| Item | Value |
|---|---|
| Dataset | MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG, Version 6.1 (MOD13C2), NASA LP DAAC, doi:10.5067/MODIS/MOD13C2.061 |
| Layer | `CMG 0.05 Deg Monthly NDVI`: 16-bit integer, NDVI = stored value ÷ 10000, valid −2000 to 10000, fill −3000 |
| Period | February 2000 onward (321 months to October 2026) |
| Delivery | One CSV per region with the monthly mean, the number of valid pixels and the number of land pixels, plus a provenance record. Format and checks: [NDVI_HANDOFF.md](NDVI_HANDOFF.md) |

**How the delivered files were made** (team member's processing, recorded in
`backend/data/ndvi/provenance.json`): MOD13C2 granules downloaded from NASA LP DAAC on 2026-11-14;
0.05° pixels averaged in 4 × 4 blocks to a 0.2° grid after removing the fill value and
out-of-range values; a 0.2° cell kept only if at least 8 of its 16 pixels were valid; only pixels
with pixel reliability 0 (good) or 1 (marginal) used, which excludes snow/ice, cloud and values
NASA estimated from the historical record. The reduction to region means was checked on delivery
against the rules in [NDVI_HANDOFF.md](NDVI_HANDOFF.md). The underlying 0.05° granules were not
re-processed independently.

**What the quality filter leaves** in the delivered record (321 months):

| Region | Months with at least half of the land pixels valid | Calendar months analysed |
|---|---|---|
| Northern Alaska | 129 | June–September only (snow and polar night remove the rest; May and October are present in too few years) |
| Colorado | 307 | All except January (snow) |
| The other six regions | 321 | All |

The Northern Alaska NDVI trend is therefore a growing-season (June–September) trend.

Because the record does not start in January, each variable carries its own period. For NDVI the
date windows span 2000–2026; the first and last calendar years are partial, annual means are shown
only for complete years, and record length is counted in months (26.75 years, not 27).

### 1.2 Missing months

The MERRA-2 series have none. A satellite series can: polar night, snow and cloud remove pixels.

- **Too few pixels.** A month's regional mean is used only if at least 50% of the region's land
  pixels are valid. Otherwise the mean would describe an unrepresentative part of the region.
- **Calendar months missing in many years.** A calendar month with data in fewer than 80% of the
  years is left out for that region in every year. If, for example, October were observed only in
  recent years, its anomalies would come from a different mix of years than the other months, and
  the change in coverage could look like a trend.
- **Statistics with gaps.** Missing months are never filled in. The least-squares slope uses the
  months that exist at their true dates. The lag-1 autocorrelation is estimated only from pairs of
  truly consecutive months. The Mann–Kendall statistic depends only on order, so gaps do not affect
  it; its Hamed–Rao correction treats the remaining months as consecutive, which is an
  approximation.

## 2. Removing the seasonal cycle

For each calendar month *m*, the climatology is the mean of all values for that month over the
variable's full record (1981–2025 for the MERRA-2 variables). The anomaly is the value minus its month's climatology. All trend statistics are
computed on anomalies. The climatology is fixed for the whole record so that results for different
date windows are comparable.

## 3. Rate of change

Time is measured in decimal years at mid-month. Slopes are reported per decade.

- **Least-squares slope** of anomaly against time. This is the headline rate.
- **Sen's slope** (Theil–Sen): the median of the slopes between all pairs of months. It is
  resistant to outliers and is reported as a cross-check. Its rank-based confidence interval assumes
  independent values and is therefore not used as the headline interval.

## 4. Significance and uncertainty

"Significant" means p < 0.05 throughout.

Monthly anomalies are persistent: a warm month tends to follow a warm month. Tests that assume
independent values then overstate significance. Two tests are used, each corrected for this.

**Adjusted t-test (Santer et al. 2008).** With *r₁* the lag-1 autocorrelation of the regression
residuals, the effective sample size is

    n_eff = n (1 − r₁) / (1 + r₁)

The standard error of the slope is computed with *n_eff − 2* in place of *n − 2* degrees of
freedom, and the 95% confidence interval and p-value use a t distribution with *n_eff − 2* degrees
of freedom. Negative *r₁* is treated as zero, so the adjustment can only widen the interval. The
unadjusted ("naive") p-value is shown beside it for comparison.

**Mann–Kendall test with the Hamed–Rao correction (1998).** The rank-based Mann–Kendall statistic
*S* is computed with the tie correction. Its variance is multiplied by

    1 + 2 / (n (n−1)(n−2)) · Σ (n−i)(n−i−1)(n−i−2) ρ(i)

where ρ(i) are the autocorrelations of the ranks of the Sen-detrended series that are individually
significant at the 5% level, for lags 1 to 24 months. The factor is not allowed below 1, so the
correction cannot make a trend look more significant than the uncorrected test.

A full-record trend is called significant only if **both** corrected tests give p < 0.05.

## 5. Trying to break the result

**Date-window sensitivity.** The adjusted least-squares trend is recomputed for every start year
and end year at least 15 years apart: 496 windows for a 1981–2025 record (91 for NDVI's 2000–2026). The dashboard shows the slope of each as a heat
map and marks windows that are not significant. Summary shares are reported: windows whose slope
has the same sign as the full record, and windows that are significant in the same or the opposite
direction. Windows overlap heavily and are not independent tests; the shares are descriptive.

**Multiple regions.** For each variable, the eight regional p-values (adjusted t-test) are also
adjusted with the Benjamini–Hochberg false-discovery-rate procedure at 0.05.

**A second dataset.** A trend can pass every test above and still be a product of how one dataset
was built. For the two variables with an openly available independent record, the same calculation
(same period, same anomaly method, same two tests) is repeated on that record
(`backend/terrapulse/crosscheck.py`):

| Variable | Independent record | Grid | Access |
|---|---|---|---|
| Precipitation | GPCP Monthly Analysis v2.3: satellite estimates merged with rain gauges (Adler et al. 2018) | 2.5° | NOAA PSL, OPeNDAP |
| Air temperature | NASA GISTEMP v4, 1200 km smoothing, land and ocean: stations, ships and buoys (Lenssen et al. 2019) | 2° | NOAA PSL, OPeNDAP |

The regional series is the mean of the grid cells that overlap the box, weighted by overlap area
and the cosine of latitude. GISTEMP is distributed as anomalies from 1951–1980; anomalies are
recomputed against 1981–2025 calendar-month means like every other series, which does not change
a trend. The result is one of:

| Second opinion | Rule ("significant" = both tests p < 0.05, as for the verdict) |
|---|---|
| Supported | Both significant, same sign, and the two 95% ranges overlap |
| Direction only | Both significant, same sign, ranges do not overlap |
| Not confirmed | Significant here, not significant in the independent record |
| Second record finds a trend this one does not | Not significant here, significant in the independent record |
| Also no trend | Not significant in either |
| Contradicted | Both significant, opposite signs |
| No second dataset checked | Humidity, wind speed, soil wetness and NDVI |

Results in the current snapshot: of the eight temperature trends, six are supported, one is
supported in direction only (southwestern Amazon, where MERRA-2 warms about twice as fast) and one
is a warming GISTEMP sees and MERRA-2 does not (Punjab box). Of the eight rainfall trends, two are
supported, two more agree on no trend, one is supported in direction only (southwestern Amazon,
where MERRA-2's decline is about twice GPCP's), one is a small decline GPCP sees and MERRA-2 does
not (Colorado), and **two are not confirmed** (the increases in the Malay Peninsula and Punjab
boxes). Overlapping 95% ranges is a simple, lenient test of agreement, and both independent records
are coarse next to the boxes: agreement is support, not proof, and disagreement shows that at
least one record is wrong without saying which.

**Years needed to detect (Weatherhead et al. 1998).** The record length that gives a 90% chance of
detecting a real trend of size ω per year at the 95% confidence level is

    n* = [ (3.3 σ / |ω|) · sqrt((1 + φ) / (1 − φ)) ]^(2/3)

with σ the standard deviation and φ the lag-1 autocorrelation of the monthly residuals. The
plausible range is n*·exp(±B), B = (4 / (3 √M)) · sqrt((1 + φ)/(1 − φ)), M the number of months.
TerraPulse evaluates this at the estimated slope. It answers "if the true trend were this size, how
long a record would be needed", which is not a prediction that the trend will continue.

## 6. Verdicts

| Verdict | Rule |
|---|---|
| Holds across dates | Both tests significant, at least 90% of windows share the full-record sign, and no window is significant in the opposite direction |
| Depends on dates | Both tests significant but the window rule fails; or neither is significant while at least 25% of windows are significant on their own |
| Tests disagree | Exactly one of the two tests is significant |
| Not detected yet | Neither test is significant and fewer than 25% of windows are |

The thresholds (90%, 25%, 15-year minimum window, 24-month lag limit) are judgment calls made for
clarity. They are constants in `analysis.py` and `stats.py` and can be changed and re-run.

## 7. Limitations

- **Reanalysis, not observation.** MERRA-2 is a model constrained by observations. The mix of
  observations it assimilates changed over 1981–2025 (new satellites, changes in the rain-gauge
  network used to correct precipitation). Such changes can create or mask trends. The second
  opinions in section 5 show this is not hypothetical: MERRA-2's rainfall increases in the Malay
  Peninsula and Punjab boxes are not confirmed by GPCP, its rainfall decline and warming in the
  southwestern Amazon box are about twice the size the independent records show, and it shows no
  warming in the Punjab box where GISTEMP does. Those MERRA-2 trends should not be cited as findings.
- **Independent validation is partial.** Only rainfall and temperature have a second dataset.
  Humidity, wind speed, soil wetness (which depends on the same rainfall) and NDVI have none, and
  nothing has been compared with station data or published regional trends. In the boxes where
  MERRA-2's rainfall or temperature disagrees with the independent record, its humidity and soil
  wetness trends deserve the same doubt.
- **Linear trends only.** A straight line can be a poor description of a series with steps, cycles
  or regime shifts. The date-window heat map exposes this but does not model it.
- **AR(1) only.** The t-test adjustment assumes persistence is described by lag-1 autocorrelation.
  Long-memory behaviour would make the intervals too narrow.
- **Skewed variables.** Precipitation anomalies are far from normally distributed, and in regions
  with a dry season most of the change sits in the wet months. There the least-squares slope (a
  change in the mean) and Sen's slope (a change in the typical month) can differ by an order of
  magnitude, as in the Central Sahel. The headline rate is the change in the mean.
- **Coarse boxes.** Rectangles average over different land covers, elevations and, in places, ocean.
  A regional mean can hide opposing local trends.
- **Association, not cause.** A significant trend says the series changed. It does not identify
  why. Region descriptions in the app are context, not explanations.
- **Thresholds.** p < 0.05 is a convention. The app reports intervals and both p-values so readers
  can judge for themselves.

## 8. Verification

`backend/tests` (79 tests, run with `uv run pytest`):

| Check | Reference |
|---|---|
| OLS slope, intercept, standard error, interval, p-value, R² | statsmodels `OLS` |
| Mann–Kendall S, tau, Z, p, with and without ties | pymannkendall `original_test` |
| Hamed–Rao corrected Z and p (all lags, and 24 lags) | pymannkendall `hamed_rao_modification_test` |
| Sen's slope | pymannkendall `sens_slope` |
| Years-to-detect formula | hand calculation |
| False-positive rate on trendless AR(1) noise (400 simulations) | naive > 25%, adjusted < 9% |
| Known slope recovered within the interval; seasonal cycle removed | synthetic series |
| Area weighting and fill-value handling | hand calculation |
| Committed NASA series complete and within physical limits | — |
| API payload consistency and error codes | FastAPI test client |
| The static JSON served by the public site equals what the code computes from the committed data | all 40 series |
| NDVI files: 11 kinds of malformed file rejected (raw integers, fill averaged in, skipped months, ...) | synthetic fixtures in temporary folders |
| NDVI regional reduction: cos-latitude weighting, fill removal, south-to-north and 0–360° grids, yearly NetCDF stacks | hand calculation |
| NDVI as a sixth variable end to end; partial years; seasonal gaps; MERRA-2 results unchanged alongside it | synthetic fixtures |
| Gap-aware lag-1 autocorrelation equals the standard estimator on complete data and beats it on gappy AR(1) noise | simulation |
| NDVI is absent from the API and the static export unless real, validated files exist | — |
| The delivered NDVI files pass every format rule, stay within the valid range and leave enough months for a trend in every region | committed files |
| Second opinions: grid-cell overlap weighting, the agreement rule, completeness of the committed GPCP and GISTEMP series | hand calculation; committed files |
| The second-opinion results quoted in the README match the data | committed files |
| Each region's stated land share matches the NDVI grid | delivered NDVI files |

## References

- Adler, R. F., et al. (2018). The Global Precipitation Climatology Project (GPCP) Monthly Analysis (New Version 2.3) and a review of 2017 global precipitation. *Atmosphere*, 9(4), 138.
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. *J. R. Stat. Soc. B*, 57, 289–300.
- Didan, K. (2021). *MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061*. NASA LP DAAC. https://doi.org/10.5067/MODIS/MOD13C2.061
- Gelaro, R., et al. (2017). MERRA-2. *J. Climate*, 30, 5419–5454.
- Hamed, K. H., & Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data. *J. Hydrol.*, 204, 182–196.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Griffin.
- Lenssen, N., et al. (2019). Improvements in the GISTEMP uncertainty model. *J. Geophys. Res. Atmos.*, 124, 6307–6326.
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13, 245–259.
- Santer, B. D., et al. (2008). Consistency of modelled and observed temperature trends in the tropical troposphere. *Int. J. Climatol.*, 28, 1703–1722.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *J. Am. Stat. Assoc.*, 63, 1379–1389.
- Weatherhead, E. C., et al. (1998). Factors affecting the detection of trends. *J. Geophys. Res.*, 103, 17149–17161.
