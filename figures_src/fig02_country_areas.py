"""Figure 2: distribution of the areas of countries and territories with and without gauges.

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

# --- Countries and territories with and without gauges ---
iso_with_gauges = set(gauges['ISO_A3'].dropna())
countries['has_gauges'] = countries['ISO_A3'].isin(iso_with_gauges)

# --- Area: World Bank land area, falling back to the polygon area ---
wb_area = fetch_wb_land_area()
countries['area_km2'] = countries['ISO_A3'].map(wb_area)
missing_area = countries['area_km2'].isna()
countries.loc[missing_area, 'area_km2'] = (
    countries.loc[missing_area, 'geometry'].apply(equal_area_km2)
)
no_gauges = countries[~countries['has_gauges']]
from_shapefile = missing_area[~countries['has_gauges']]

print(f"Countries and territories: {len(countries)}")
print(f"With gauges: {countries['has_gauges'].sum()}")
print(f"With no gauges: {len(no_gauges)}")
print(f"  Area from World Bank: {(~from_shapefile).sum()}")
print(f"  Area from shapefile: {from_shapefile.sum()}")
print("    " + ", ".join(sorted(no_gauges.loc[from_shapefile, 'NAM_0'])))
print(f"  Smaller than Rhode Island ({RHODE_ISLAND_KM2:,} km²): "
      f"{(no_gauges['area_km2'] < RHODE_ISLAND_KM2).sum()}")

# --- Drop non-positive values ---
countries = countries[countries['area_km2'] > 0]
areas_without = countries.loc[~countries['has_gauges'], 'area_km2']
areas_with = countries.loc[countries['has_gauges'], 'area_km2']

# --- Logarithmic bins spanning both groups ---
log_bins = np.logspace(np.log10(countries['area_km2'].min()),
                       np.log10(countries['area_km2'].max()), 30)
counts_without, _ = np.histogram(areas_without, log_bins)
counts_with, _ = np.histogram(areas_with, log_bins)

# --- Side-by-side bars: each bin split in half (in log space), with a small gap at each edge ---
log_left, log_right = np.log10(log_bins[:-1]), np.log10(log_bins[1:])
log_width = log_right - log_left
bar_start = 10 ** (log_left + 0.05 * log_width)
bar_middle = 10 ** (log_left + 0.5 * log_width)
bar_end = 10 ** (log_left + 0.95 * log_width)

fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(bar_start, counts_without, width=bar_middle - bar_start, align='edge',
       color='#2a78d6', label=f"No gauges ({len(areas_without)})")
ax.bar(bar_middle, counts_with, width=bar_end - bar_middle, align='edge',
       color='#eb6834', label=f"With gauges ({len(areas_with)})")
ax.set_xscale('log')
ax.set_xlabel("Area (km², log scale)")
ax.set_ylabel("Number of Countries and Territories")
ax.legend(frameon=False)
ax.spines[['top', 'right']].set_visible(False)
ax.grid(axis='y', color='#e1e0d9', linewidth=0.6)
ax.set_axisbelow(True)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
