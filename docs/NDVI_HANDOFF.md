# NDVI handoff: MOD13C2 v6.1 to TerraPulse

TerraPulse is ready to show **vegetation greenness (NDVI)** as a sixth variable. It needs eight small
CSV files, one per region, plus one provenance file. The global maps themselves stay out of git.

**Status: delivered on 2026-11-14** (pull request #8). This document is kept as the specification
for the files and for any later re-processing.

Whenever the files in `backend/data/ndvi/` are missing or fail validation, NDVI is not listed
anywhere in the app. With valid files on `main`, CI checks them and the dashboard shows NDVI.

## 1. What to deliver

```
backend/data/ndvi/
  upper-colorado.csv
  north-slope.csv
  rondonia.csv
  moroccan-atlas.csv
  central-sahel.csv
  punjab-plain.csv
  malay-peninsula.csv
  murray-darling.csv
  provenance.json
```

Total size is under 200 KB.

## 2. The easy way: run the script on your yearly files

The script reads gridded monthly NDVI on a regular latitude/longitude grid (NetCDF or HDF5, one
file per year with the monthly maps stacked in time) and writes all nine files in the right format.

```bash
git clone https://github.com/crollila/terrapulse
cd terrapulse/backend
uv sync
```

Check what it detects first. This writes nothing:

```bash
uv run python -m terrapulse.ndvi_regions --input "PATH/TO/YOUR/FILES/*.nc" --processed-by "Your Name" --resampling "HOW YOU MADE THE 0.2 DEGREE GRID" --quality-filter "WHICH PIXELS YOU EXCLUDED" --dry-run
```

Read the printout. It should say:

- `values treated as: stored integers, multiplied by 0.0001` if your files hold the original
  integers (for example 4521), or `NDVI units` if you already converted them (0.4521);
- the grid size (900 x 1800 for 0.2°) and latitude/longitude ranges;
- `record: 2000-02 to 2026-10 (321 months)`;
- for each region, an NDVI range that looks right (deserts near 0.1, rainforest above 0.7).

If it looks right, run it again without `--dry-run`, then:

```bash
uv run pytest
uv run python -m terrapulse.export
```

`pytest` must pass. `export` writes the dashboard's JSON. Commit `backend/data/ndvi/` and
`frontend/public/data/` on a branch and open a pull request.

Options if the script cannot work things out on its own:

| Problem | Option |
|---|---|
| More than one variable in the file | `--var NAME_OF_NDVI_VARIABLE` |
| It guesses the units wrongly | `--scale raw` (integers) or `--scale physical` (NDVI units) |
| No dates inside the file | Put the year in each file name (`ndvi_2000.nc`); maps are then taken as January onward, except an 11-map 2000 file, which is taken as February to December |

If your files are not NetCDF/HDF5 (GeoTIFF, `.npy`, ...), either convert them with xarray or
produce the CSVs yourself to the specification below.

## 3. CSV specification

One file per region, named exactly `<region-id>.csv`, comma-separated, with this header:

```
year,month,NDVI,NDVI_cells,NDVI_cells_total
2000,2,0.23145,688,700
2000,3,0.24410,700,700
2000,4,,0,700
```

| Column | Type | Meaning |
|---|---|---|
| `year` | integer | Calendar year |
| `month` | integer 1–12 | Calendar month |
| `NDVI` | decimal, 4 or more places | Area-weighted mean NDVI of the valid pixels in the region box, in NDVI units (−0.2 to 1.0). Leave empty if no pixel is valid that month. |
| `NDVI_cells` | integer | Number of valid pixels that went into the mean (0 if none) |
| `NDVI_cells_total` | integer | Number of land pixels of your grid inside the box: pixels that are valid in at least one month. The same number in every row. |

Rules the loader enforces (a file that breaks one is rejected with a message saying which):

1. **One row per calendar month, in order, none skipped or repeated**, from the first month to the
   last. A month with no valid pixel still gets a row, with `NDVI` empty and `NDVI_cells` 0.
2. The first row is February 2000 or later (Terra MOD13C2 begins 2000-02).
3. All eight files cover exactly the same months.
4. `NDVI` is in NDVI units: **stored integer ÷ 10000**. A value such as 4521 is rejected.
5. `NDVI` stays within −0.2 to 1.0. A value below −0.2 means the fill value (−3000) was averaged in.
6. `0 ≤ NDVI_cells ≤ NDVI_cells_total`, and `NDVI` is present exactly when `NDVI_cells > 0`.

How the regional mean is formed:

- Use the pixels whose **centre** lies inside the box (table in section 6).
- Weight each pixel by the cosine of its latitude.
- Leave out invalid pixels (section 4) from both the mean and the count.

`provenance.json` (the script writes it; by hand, these keys are required):

```json
{
  "product": "MOD13C2",
  "version": "061",
  "first_month": "2000-02",
  "last_month": "2026-10",
  "downloaded_from": "NASA LP DAAC (Earthdata)",
  "downloaded_utc": "2026-11-14",
  "processed_by": "Your Name",
  "processing": {
    "resampling": "how the 0.05 degree product became your grid",
    "quality_filter": "which pixels were excluded and how"
  }
}
```

## 4. What counts as a valid pixel

MOD13C2 v6.1, layer `CMG 0.05 Deg Monthly NDVI` (NASA LP DAAC product page and file specification):

| Property | Value |
|---|---|
| Stored type | 16-bit signed integer |
| Fill value | −3000 |
| Valid range | −2000 to 10000 |
| Conversion | NDVI = stored value ÷ 10000 |

Two traps:

- The file attribute says `scale_factor = 10000`. It is a **divisor**. Tools that follow the CF
  convention (xarray with default settings, some GDAL paths) multiply by it and give values up to
  100,000,000. The script reads the stored numbers untouched to avoid this.
- **Averaging the fill value in.** If 0.05° pixels were averaged to 0.2° without first removing
  −3000 (ocean, missing), coastal and partly missing cells get values that look plausible but are
  wrong. The loader cannot detect this after the fact.

The companion layer `CMG 0.05 Deg Monthly pixel reliability` grades every pixel:

| Code | Meaning | Use for trends? |
|---|---|---|
| −1 | Fill / no data | No |
| 0 | Good data | Yes |
| 1 | Marginal data | Yes |
| 2 | Snow / ice | No |
| 3 | Cloudy | No |
| 4 | Estimated from the MODIS historical record | **No** |

Code 4 matters most. The monthly CMG product fills cloudy or missing cells with the long-term
average for that month, so the map has no holes. A filled cell carries no information about that
particular month and pulls trends toward zero. Cloudy regions (the southwestern Amazon, the Malay Peninsula) are
the most affected.

## 5. Questions to answer in the pull request

1. How did you go from 0.05° to 0.2°? Was −3000 removed **before** averaging?
2. Did you keep or use the pixel reliability layer? If not, the regional means include snow, cloud
   and historically filled values. We can still show them, with that stated in the app, but
   re-running with reliability 0–1 only is better if time allows.
3. What format are the yearly files, and are the values integers or already divided by 10000?
4. On what date did you download the data?

## 6. Region boxes

`[west, south, east, north]` in degrees. These are the same boxes the other five variables use
(`backend/terrapulse/catalog.py`).

| Region id | West | South | East | North |
|---|---|---|---|---|
| `upper-colorado` | −109 | 37 | −102 | 41 |
| `north-slope` | −160 | 66 | −150 | 71 |
| `rondonia` | −66 | −13 | −60 | −8 |
| `moroccan-atlas` | −10 | 30 | −2 | 35 |
| `central-sahel` | 0 | 12 | 10 | 17 |
| `punjab-plain` | 71 | 28 | 78 | 33 |
| `malay-peninsula` | 99 | 1 | 105 | 7 |
| `murray-darling` | 140 | −37 | 149 | −30 |

## 7. What the app does with the files

- A month is used only if at least half of the region's land pixels are valid; otherwise it is
  treated as missing (the mean would describe an unrepresentative part of the region).
- A calendar month that has data in fewer than 80% of the years is left out for that region
  (for example polar-night months in northern Alaska).
- The record runs February 2000 to October 2026, so trend windows for NDVI span 2000–2026 and the
  first and last years are partial. Annual means are shown only for complete years.
- Everything else (seasonal-cycle removal, slope, both significance tests, date-window check) is
  identical to the other variables. See [METHODOLOGY.md](METHODOLOGY.md).

## 8. Citation

Didan, K. (2021). *MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061* [Data set].
NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MOD13C2.061
