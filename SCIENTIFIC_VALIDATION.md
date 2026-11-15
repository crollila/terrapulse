# Scientific validation review

An independent review of TerraPulse's results by a team member (GitHub `DerekKered044`, scientific
research and validation), 15 November 2026. The full seven-page report is attached to
[pull request #12](https://github.com/crollila/terrapulse/pull/12). The reviewer's summary follows,
unchanged:

> Scientific validation review (15 Nov 2026): Southwestern Amazon rainfall decrease is supported in direction by TerraPulse
> MERRA-2/GPCP and external Rondônia/southern Amazon literature, but the -0.541 mm/day/decade MERRA-2 magnitude is not
> independently verified. NASA documents a wider-Amazon corrected-precipitation discontinuity near 2005 related to the CPC
> gauge processing transition. Recommend examining exact-box series across that breakpoint and comparing with CHIRPS.
> MERRA-2 rainfall increases in the Malay and Punjab boxes are not confirmed by GPCP; Punjab temperature disagrees with
> GISTEMP. Northern Alaska warming is a better-supported demonstration. Also, overview computes FDR-corrected p-values but
> RegionMap.tsx colors boxes using uncorrected p-values, which merits clearer display wording or correction. See citations
> [R1-R13] below.

The sections below were added when the review was merged. They record what was done about each
finding, the same-box test the review recommended, and the references the summary points to. They
were written with the SI coding assistant described in the README.

## What was done about each finding

| Finding in the review | Status in the tool |
|---|---|
| The MERRA-2 rate for south-western Amazon rainfall (−0.541 mm/day per decade) is not independently verified | The second opinion reads "agrees on direction, not size". No text presents the MERRA-2 rate as confirmed. |
| NASA documents a discontinuity in corrected MERRA-2 precipitation over the wider Amazon near 2005; examine the exact-box series across it | **Done.** See the next section. The result is shown in the app as a known data issue, with sources. |
| Compare with CHIRPS for the same box | **Not done.** Stated as an open item in the app's documentation. |
| MERRA-2 rainfall increases in the Malay Peninsula and Punjab boxes are not confirmed by GPCP | Shown as "Not confirmed by a second dataset". The region comparison repeats each region's second opinion and says the contrast is not established. |
| Punjab temperature disagrees with GISTEMP | Shown as "Second dataset finds a trend this one does not". |
| Northern Alaska warming is the better-supported demonstration | It is the first case file and part of the demo script (docs/DEMO.md). |
| The map colours use uncorrected p-values while the overview applies a false-discovery-rate correction | The map legend now says the colours use each region's own tests, before the correction. In the current data, for all six variables, the coloured regions are exactly the ones that survive the correction. |
| "Not detected yet" implies a trend will emerge; an insignificant result is not "no change" (full report) | Now "No significant trend detected" and "also finds no significant trend". |
| Soil wetness depends on the corrected precipitation and may inherit the artifact (full report) | Amazon soil wetness now carries that caveat, marked as untested. |

Not done, and not claimed: the CHIRPS comparison, a comparison of soil wetness with SMAP, a second
vegetation index, seasonal sub-analyses, and a pixel-level check of the NDVI quality filtering.

## The same-box test of the 2005 break

Region box 66°W–60°W, 13°S–8°S; monthly rainfall, 1981–2025; MERRA-2 `PRECTOTCORR` against GPCP v2.3.
The break year comes from the publication (R5), not from the data. Method and code:
[docs/METHODOLOGY.md](docs/METHODOLOGY.md) section 5, `backend/terrapulse/stats.py` (`level_shift`)
and `backend/terrapulse/crosscheck.py` (`known_issue`). A test pins these numbers.

| Quantity (mm/day) | Value |
|---|---|
| Mean MERRA-2 minus GPCP, 1981–2004 | −0.13 |
| Mean MERRA-2 minus GPCP, 2005–2025 | −0.99 |
| Step at 2005, with a steady drift allowed | −1.07 (95% range −1.51 to −0.63) |
| Drift left between the two records | not significant (+0.10 per decade, 95% range −0.07 to +0.26) |
| Best-fitting single break year | 2005 |
| Trend 1981–2004, MERRA-2 against GPCP (per decade) | −0.14 against −0.14; neither significant |
| Trend 2005–2025, MERRA-2 against GPCP (per decade) | −0.59 against −0.83; both significant |

The review's concern is confirmed for this box: the two records differ by a jump in 2005, the
documented year, and agree within their ranges on either side of it. Much of MERRA-2's faster
full-record decline therefore probably comes from how the dataset was built. The direction of the
change is supported by both records. Its size is not confirmed, and its cause is not addressed.

## References

Numbering follows the full report. Citation details for R4–R13 were checked against Crossref and
the publishers' pages on 15 November 2026. For this follow-up, R4 (slide 12 and its figure) and the
abstracts of R6, R7, R9, R12 and R13 were read; R5 was seen only through its figure on R4's slide;
R8, R10 and R11 were confirmed to exist but not read. What each source says is summarised by the
reviewer in the full report.

- [R1] TerraPulse README, results tables and region definitions. https://github.com/crollila/terrapulse
- [R2] TerraPulse methodology. https://github.com/crollila/terrapulse/blob/main/docs/METHODOLOGY.md
- [R3] TerraPulse source, map colouring. https://github.com/crollila/terrapulse/blob/main/frontend/src/components/RegionMap.tsx
- [R4] Reichle, R. (2023). *The Land Surface in Earth System Reanalysis*. ECMWF Annual Seminar on Earth System Reanalysis, Reading, UK, 4–8 September 2023. NASA NTRS 20230012995, slide 12. https://ntrs.nasa.gov/citations/20230012995
- [R5] Reichle, R. H., Liu, Q., Koster, R. D., Draper, C. S., Mahanama, S. P. P., & Partyka, G. S. (2017). Land Surface Precipitation in MERRA-2. *Journal of Climate*, 30(5), 1643–1664. https://doi.org/10.1175/JCLI-D-16-0570.1
- [R6] Moreira, R. M., dos Santos, B. C., Sanches, R. G., Bourscheidt, V., de Sales, F., Sieber, S., & de Souza, P. H. (2023). Precipitation Variability for Protected Areas of Primary Forest and Pastureland in Southwestern Amazônia. *Climate*, 11(2), 27. https://doi.org/10.3390/cli11020027
- [R7] Cui, Piao, Huntingford, Wang, & Spracklen (2026). Historical deforestation drives strong rainfall decline across the southern Amazon basin. *Nature Communications*, 17, 1642. https://doi.org/10.1038/s41467-026-68361-z
- [R8] Polasky, Sapkota, Forest, & Fuentes (2025). Discrepancies in precipitation trends between observational and reanalysis datasets in the Amazon Basin. *Scientific Reports*, 15, 7268. https://doi.org/10.1038/s41598-025-87418-5
- [R9] Mu, Biggs, & Jones (2023). Importance in Shifting Circulation Patterns for Dry Season Moisture Sources in the Brazilian Amazon. *Geophysical Research Letters*, 50(9), e2023GL103167. https://doi.org/10.1029/2023GL103167
- [R10] NOAA Arctic Report Card 2025: Tundra Greenness. https://arctic.noaa.gov/report-card/report-card-2025/tundra-greenness-2025/
- [R11] NOAA Arctic Report Card 2025. https://arctic.noaa.gov/report-card/report-card-2025/
- [R12] Guo, Xie, Myhre, Shindell, et al. (2024). Increased Asian Sulfate Aerosol Emissions Remarkably Enhance Sahel Summer Precipitation. *Earth's Future*, 12(11), e2024EF004745. https://doi.org/10.1029/2024EF004745
- [R13] Zeng, Jia, Menenti, Jiang, Barnieh, Bennour, & Lv (2023). Changes in vegetation greenness related to climatic and non-climatic factors in the Sudano-Sahelian region. *Regional Environmental Change*, 23, 92. https://doi.org/10.1007/s10113-023-02084-5
- [R14] TerraPulse source, multiple-testing correction. https://github.com/crollila/terrapulse/blob/main/backend/terrapulse/analysis.py
