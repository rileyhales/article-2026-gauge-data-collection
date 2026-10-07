"""Figure 2: distribution of the areas of countries and territories with no gauges.

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
        <GAUGE_DATA_DIR>/country_shapefile/WB_GAD_ADM0.shp
        World Bank API, land area (AG.LND.TOTL.K2), most recent year -- needs internet
Writes: latex/figures/fig02_country_areas.png

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.

Gauges are matched to countries by the catalog's ISO_A3 column. Area comes from
World Bank land area; places without a World Bank value fall back to the area of
their boundary polygon in an equal-area projection.
"""
import json
import os
import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
OUTPUT = REPO_DIR / "latex" / "figures" / "fig02_country_areas.png"

RHODE_ISLAND_KM2 = 3000  # size comparison used in the paper text


def fetch_wb_land_area():
    """Most recent World Bank land area (km²) for every country code."""
    url = ("https://api.worldbank.org/v2/country/all/indicator/AG.LND.TOTL.K2"
           "?format=json&per_page=20000&mrv=1")
    data = json.loads(urllib.request.urlopen(url).read())
    return {item['countryiso3code']: item['value']
            for item in data[1] if item['value'] is not None}


def equal_area_km2(geom):
    """Polygon area in km², split at 0° so polygons crossing 180° measure correctly."""
    halves = gpd.GeoSeries(
        [geom.intersection(box(-180, -90, 0, 90)), geom.intersection(box(0, -90, 180, 90))],
        crs="EPSG:4326",
    )
    return halves.to_crs("ESRI:54034").area.sum() / 1e6  # World Cylindrical Equal Area


gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
countries = gpd.read_file(DATA_DIR / "country_shapefile" / "WB_GAD_ADM0.shp")

# --- One row per country/territory (some are split across several polygons) ---
countries = countries.dissolve(by='ISO_A3', as_index=False)

# --- Countries and territories with no gauges ---
iso_with_gauges = set(gauges['ISO_A3'].dropna())
no_gauges = countries[~countries['ISO_A3'].isin(iso_with_gauges)].copy()

# --- Area: World Bank land area, falling back to the polygon area ---
wb_area = fetch_wb_land_area()
no_gauges['area_km2'] = no_gauges['ISO_A3'].map(wb_area)
from_shapefile = no_gauges['area_km2'].isna()
no_gauges.loc[from_shapefile, 'area_km2'] = (
    no_gauges.loc[from_shapefile, 'geometry'].apply(equal_area_km2)
)

print(f"Countries and territories: {len(countries)}")
print(f"With no gauges: {len(no_gauges)}")
print(f"  Area from World Bank: {(~from_shapefile).sum()}")
print(f"  Area from shapefile: {from_shapefile.sum()}")
print("    " + ", ".join(sorted(no_gauges.loc[from_shapefile, 'NAM_0'])))
print(f"  Smaller than Rhode Island ({RHODE_ISLAND_KM2:,} km²): "
      f"{(no_gauges['area_km2'] < RHODE_ISLAND_KM2).sum()}")

# --- Drop non-positive values ---
areas = no_gauges['area_km2']
areas = areas[areas > 0]

# --- Create logarithmic bins ---
log_bins = np.logspace(np.log10(areas.min()), np.log10(areas.max()), 30)

plt.figure(figsize=(10, 6))
plt.hist(areas, bins=log_bins, edgecolor='white', linewidth=0.5)
plt.xscale('log')
plt.xlabel("Area (km², log scale)")
plt.ylabel("Number of Countries and Territories")

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
