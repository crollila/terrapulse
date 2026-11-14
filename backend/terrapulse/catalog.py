"""Supported regions, variables and data sources.

Regions are latitude/longitude boxes no larger than 10 x 10 degrees (the NASA
POWER regional API limit). A box is not a basin, a state or a country: each
``name`` and ``setting`` says what the rectangle really covers, including sea.
The ``land_share`` is the share of the box that is land, counted on the 0.2
degree MODIS grid (pixels with at least one valid NDVI value); region ids are
kept stable because data files are named after them.

Every variable names its data source and its own analysis period:

- ``merra2``: NASA POWER monthly parameters from the MERRA-2 reanalysis,
  1981-2025, fetched by ``power.py``.
- ``mod13c2``: MODIS/Terra NDVI (MOD13C2 v6.1), February 2000 onward, supplied
  as regional CSV files and read by ``ndvi.py``. NDVI is listed here but is only
  served once real regional files are present (see ``data.available``).
"""

from __future__ import annotations

# Period of the MERRA-2 variables (kept as module constants for power.py).
START_YEAR = 1981
END_YEAR = 2025

# bbox = [lon_min, lat_min, lon_max, lat_max]
REGIONS: dict[str, dict] = {
    "upper-colorado": {
        "name": "Colorado",
        "short_name": "Colorado",
        "country": "United States",
        "bbox": [-109.0, 37.0, -102.0, 41.0],
        "setting": "A box matching the state of Colorado: the Rocky Mountains, where the Colorado, Rio Grande, "
        "Arkansas and South Platte rivers rise, and the high plains to the east.",
        "land_share": 1.0,
    },
    "north-slope": {
        "name": "Northern Alaska",
        "short_name": "N. Alaska",
        "country": "United States",
        "bbox": [-160.0, 66.0, -150.0, 71.0],
        "setting": "Arctic tundra and permafrost: the North Slope and the Brooks Range, with a strip of interior "
        "Alaska to the south and a little of the Arctic Ocean.",
        "land_share": 0.97,
    },
    "rondonia": {
        "name": "Southwestern Amazon (Rondônia)",
        "short_name": "SW Amazon",
        "country": "Brazil / Bolivia",
        "bbox": [-66.0, -13.0, -60.0, -8.0],
        "setting": "Tropical rainforest with extensive land clearing since the 1980s. The box covers the Brazilian "
        "state of Rondônia and neighbouring parts of Bolivia and of other Brazilian states.",
        "land_share": 1.0,
    },
    "moroccan-atlas": {
        "name": "Northern Morocco",
        "short_name": "N. Morocco",
        "country": "Morocco",
        "bbox": [-10.0, 30.0, -2.0, 35.0],
        "setting": "Mediterranean-to-desert transition across the Atlas Mountains and the Atlantic plains. "
        "About a sixth of the box is sea.",
        "land_share": 0.83,
    },
    "central-sahel": {
        "name": "Central Sahel",
        "short_name": "Sahel",
        "country": "Niger / Nigeria / Burkina Faso / Mali",
        "bbox": [0.0, 12.0, 10.0, 17.0],
        "setting": "Semi-arid belt between the Sahara and the West African savanna, from eastern Burkina Faso "
        "across southern Niger and northern Nigeria.",
        "land_share": 1.0,
    },
    "punjab-plain": {
        "name": "Punjab and the north-west Indian plains",
        "short_name": "Punjab",
        "country": "Pakistan / India",
        "bbox": [71.0, 28.0, 78.0, 33.0],
        "setting": "Intensively irrigated farmland of the upper Indus plain and north-west India, with part of "
        "the Thar Desert in the south and Himalayan foothills in the north-east.",
        "land_share": 1.0,
    },
    "malay-peninsula": {
        "name": "Malay Peninsula and Strait of Malacca",
        "short_name": "Malay Pen.",
        "country": "Malaysia / Indonesia / Thailand / Singapore",
        "bbox": [99.0, 1.0, 105.0, 7.0],
        "setting": "Humid equatorial land and sea with two monsoon seasons: Peninsular Malaysia, eastern Sumatra "
        "and the waters around them. About half of the box is sea.",
        "land_share": 0.52,
    },
    "murray-darling": {
        "name": "Southern Murray–Darling Basin",
        "short_name": "Murray–Darling",
        "country": "Australia",
        "bbox": [140.0, -37.0, 149.0, -30.0],
        "setting": "Australia's main agricultural river basin, prone to multi-year drought. The box covers its "
        "southern half and some land just outside it.",
        "land_share": 1.0,
    },
}

VARIABLES: dict[str, dict] = {
    "T2M": {
        "name": "Air temperature",
        "long_name": "Temperature at 2 Meters",
        "units": "°C",
        "definition": "Average air temperature two meters above the ground, about head height.",
        "decimals": 2,
        "source": "merra2",
        "period": [START_YEAR, END_YEAR],
    },
    "PRECTOTCORR": {
        "name": "Precipitation",
        "long_name": "Precipitation Corrected",
        "units": "mm/day",
        "definition": "Average rain and melted snow reaching the surface each day. "
        "MERRA-2 adjusts its modelled precipitation toward gauge and satellite observations.",
        "decimals": 3,
        "source": "merra2",
        "period": [START_YEAR, END_YEAR],
    },
    "QV2M": {
        "name": "Humidity",
        "long_name": "Specific Humidity at 2 Meters",
        "units": "g/kg",
        "definition": "Grams of water vapor in each kilogram of air near the ground.",
        "decimals": 3,
        "source": "merra2",
        "period": [START_YEAR, END_YEAR],
    },
    "WS10M": {
        "name": "Wind speed",
        "long_name": "Wind Speed at 10 Meters",
        "units": "m/s",
        "definition": "Average wind speed ten meters above the ground.",
        "decimals": 3,
        "source": "merra2",
        "period": [START_YEAR, END_YEAR],
    },
    "GWETROOT": {
        "name": "Root-zone soil wetness",
        "long_name": "Root Zone Soil Wetness",
        "units": "fraction (0-1)",
        "definition": "How full of water the top meter of soil is: 0 is completely dry, 1 is saturated.",
        "decimals": 4,
        "source": "merra2",
        "period": [START_YEAR, END_YEAR],
    },
    "NDVI": {
        "name": "Vegetation greenness",
        "long_name": "Normalized Difference Vegetation Index (NDVI)",
        "units": "NDVI",
        "definition": "A satellite measure of how much green, leafy vegetation covers the ground. "
        "It runs from about 0 (bare soil, snow, rock) to nearly 1 (dense green vegetation).",
        "decimals": 4,
        "source": "mod13c2",
        # Calendar years that may contain data. The record starts in February 2000,
        # so 2000 is a partial year, and the latest year may be partial too. The
        # period actually served is read from the delivered files (ndvi.py).
        "period": [2000, 2026],
    },
}

SOURCES: dict[str, dict] = {
    "merra2": {
        "id": "merra2",
        "short_name": "NASA MERRA-2 reanalysis",
        "dataset": "MERRA-2 (Modern-Era Retrospective analysis for Research and Applications, Version 2)",
        "producer": "NASA Global Modeling and Assimilation Office (GMAO)",
        "access": "NASA POWER Monthly and Annual API (NASA Langley Research Center)",
        "access_short": "NASA POWER API",
        "access_url": "https://power.larc.nasa.gov/",
        "api_endpoint": "https://power.larc.nasa.gov/api/temporal/monthly/regional",
        "native_grid": "0.5° latitude x 0.625° longitude",
        "kind": "Reanalysis: a global model constrained by satellite and ground observations. "
        "Values are model-based estimates, not direct instrument readings.",
        "caveat": "MERRA-2 is a reanalysis: a model constrained by satellite and ground observations, not a direct "
        "measurement. Changes in the observing system over time (new satellites, fewer rain gauges) can create or "
        "hide trends, especially for precipitation and soil wetness. Check important results against an "
        "independent dataset.",
        "credit": "NASA GMAO MERRA-2 via NASA POWER",
    },
    "mod13c2": {
        "id": "mod13c2",
        "short_name": "NASA MODIS/Terra vegetation index (MOD13C2 v6.1)",
        "dataset": "MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG, Version 6.1 (MOD13C2)",
        "producer": "NASA MODIS Land Science Team; distributed by NASA LP DAAC",
        "access": "NASA LP DAAC (Earthdata); regional means computed by the team",
        "access_short": "NASA LP DAAC",
        "access_url": "https://doi.org/10.5067/MODIS/MOD13C2.061",
        "doi": "10.5067/MODIS/MOD13C2.061",
        "native_grid": "0.05° latitude x 0.05° longitude (climate modeling grid)",
        "kind": "Satellite observation: a vegetation index computed from red and near-infrared reflectance "
        "measured by the MODIS instrument on NASA's Terra satellite.",
        "caveat": "NDVI is a satellite measurement of greenness, not a direct measure of plant health or biomass. "
        "Clouds, snow, smoke and low sun angles lower it, and it saturates over dense forest. The record starts "
        "in 2000, so it is shorter than the 1981-2025 weather variables and trends are harder to detect. "
        "The Terra satellite's overpass time has drifted earlier since 2020, which NASA reports is affecting "
        "recent data, so treat changes after about 2022 with extra care.",
        "credit": "NASA MODIS/Terra MOD13C2 v6.1 via NASA LP DAAC",
    },
}

# Backward-compatible name: the MERRA-2 source record.
SOURCE = SOURCES["merra2"]


def variable_period(variable: str) -> tuple[int, int]:
    """Declared calendar-year bounds of a variable's record."""
    start, end = VARIABLES[variable]["period"]
    return int(start), int(end)


def variable_source(variable: str) -> dict:
    return SOURCES[VARIABLES[variable]["source"]]
