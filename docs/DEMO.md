# Demo script

For the "Link to project demo" field. The Space Apps rules allow **one** of:

- a video of **30 seconds or less**, or
- a slide deck of **at most 7 slides, title slide included**.

Going over either limit makes the project ineligible for Global Judging. The link must open
without a login. Use English, or English subtitles. Do not show anyone under 18. Images or video
made by an SI tool need a visible watermark; a screen recording of the live tool is not SI-made.

Everything below matches the live tool as frozen on 15 November 2026:
https://crollila.github.io/terrapulse/

## Option A: 30-second video

Record the browser at 1280 × 720 or larger, desktop layout. Reload the page first so the map is
drawn. The narration is 68 words, about 27 seconds at a normal speaking pace; do not add to it.
Record the screen first, then fit the voice (or captions) to it, and cut the final file to 0:30
or less.

| Time | On screen, with the exact clicks | Narration |
|---|---|---|
| 0:00–0:05 | Top of the page: the title and the four case-file cards. **Click the second card, "A real trend, the wrong size?"** | "TerraPulse finds trends in NASA Earth data, then tries to break them." |
| 0:05–0:12 | Scroll down until the card **"2 · The verdict"** fills the right side. It reads "Significant falling trend that holds across date ranges", −0.541 mm/day per decade. | "MERRA-2 says Amazon rainfall is falling fast: significant, across nearly every choice of dates." |
| 0:12–0:21 | Same card, scroll a little further to the amber box: **"Second opinion: Second dataset agrees on direction, not size"** and below it **"Known data issue: MERRA-2 rainfall shifts in 2005"**. Hold on that heading. | "But GPCP shows half that rate. We traced the gap to a 2005 rain-gauge change NASA documented, and the tool tests for it." |
| 0:21–0:26 | Scroll back to the top. **Click the first card, "How fast is the Arctic warming?"**, then scroll to "2 · The verdict": green box, "Supported by a second dataset". | "Arctic warming passes every check we run: two NASA records agree." |
| 0:26–0:30 | Scroll to the top and hold on the title. | "Detected is not validated. TerraPulse shows the difference." |

If the scrolling costs too much time, record the Amazon part and the Arctic part as two takes and
join them.

### What each line rests on

| Line | Evidence in the tool |
|---|---|
| "falling fast: significant" | MERRA-2 trend −0.541 mm/day per decade, 95% range −0.641 to −0.441; both tests p < 0.001 |
| "nearly every choice of dates" | 494 of 496 start/end-year windows point the same way |
| "GPCP shows half that rate" | GPCP v2.3: −0.282 mm/day per decade, 95% range −0.372 to −0.192 |
| "a 2005 rain-gauge change NASA documented" | Reichle et al. (2017), *Journal of Climate*; found by the team's validation review |
| "the tool tests for it" | Step at 2005 of −1.07 mm/day (95% range −1.51 to −0.63); no significant drift left; pinned by an automated test |
| "Arctic warming passes every check we run" | Northern Alaska box: +0.51 °C per decade in MERRA-2, both tests significant, 98% of date windows agree, survives the multiple-region correction |
| "two NASA records agree" | NASA GISTEMP v4: +0.41 °C per decade, ranges overlap |

### Do not say

- That the Amazon lost a stated amount of rain. Both records show a decline; the size is not confirmed.
- Why rainfall or temperature changed. The tool never attributes a cause (no "because of deforestation", no "because of climate change").
- "Validated", "proven" or "confirmed" about any single number.
- "The Arctic" for more than this one box in northern Alaska, or "the Amazon" for more than this one box.
- That MERRA-2 is wrong everywhere. One documented problem was tested in one box.

## Option B: 7 slides

Use this instead of the video, not as well as it.

1. **Title.** TerraPulse: find a trend in NASA Earth data, then find out whether to believe it. Team Orbital Alpha. Live link.
2. **The problem.** A trend line and "p < 0.05" are easy to make and easy to get wrong.
3. **What it does.** Screenshot of the map and verdict card. Six variables, eight region boxes, rate of change with a 95% range, two significance tests.
4. **It tries to break its own answer.** Screenshot of the date-window heat map. Every start and end year, a multiple-region correction, years of data needed, a second dataset.
5. **Case 1: a trend that survives.** Northern Alaska warming, +0.51 °C per decade in MERRA-2 and +0.41 in NASA GISTEMP.
6. **Case 2: a trend that does not survive as stated.** Amazon rainfall: −0.54 in MERRA-2, −0.28 in GPCP, and a documented 2005 jump of −1.07 mm/day between them. Detected is not validated.
7. **How it was built and checked.** NASA MERRA-2, MODIS, GISTEMP; GPCP. 84 automated tests. Open source, MIT. SI assistance disclosed in the README.

## Before recording

- Open the live link in a private window to confirm it loads without a login.
- Check the two case files still show the wording quoted above.
- Other features worth a still image if there is room: comparing two regions on one chart, the CSV download, the data provenance panel, vegetation greenness (NDVI) from MODIS.
