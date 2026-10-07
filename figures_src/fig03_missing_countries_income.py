"""Figure 3: countries and territories with no gauges, by World Bank income group.

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
        <GAUGE_DATA_DIR>/country_shapefile/WB_GAD_ADM0.shp
        World Bank API, official income classification (current) -- needs internet
Writes: latex/figures/fig03_missing_countries_income.png

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.

Gauges are matched to countries by the catalog's ISO_A3 column.
"""
import json
import os
import urllib.request
from datetime import date
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
OUTPUT = REPO_DIR / "latex" / "figures" / "fig03_missing_countries_income.png"

# Color map for income groups
COLORS = {
    'Low income': '#e41a1c',
    'Lower middle income': '#ff7f00',
    'Upper middle income': '#377eb8',
    'High income': '#4daf4a',
}
GAUGED_COLOR = 'lightgray'
NO_DATA_COLOR = '#f7f7f7'
NO_DATA_HATCH = '////'
CLASSIFICATION_YEAR = 'FY2027'
NEXT_RECLASSIFICATION = date(2027, 7, 1)


def fetch_wb_income_groups():
    """Current World Bank income group for every country code."""
    url = "https://api.worldbank.org/v2/country?format=json&per_page=500"
    data = json.loads(urllib.request.urlopen(url).read())
    return {item['id']: item['incomeLevel']['value'] for item in data[1]}


def split_at_prime_meridian(geom):
    """Split polygons crossing 180° into west and east halves so they project cleanly."""
    minx, _, maxx, _ = geom.bounds
    if not (minx < -179 and maxx > 179):
        return [geom]
    halves = [geom.intersection(box(-180, -90, 0, 90)), geom.intersection(box(0, -90, 180, 90))]
    return [h for h in halves if not h.is_empty]


def draw(ax, geoms, **kwargs):
    pieces = [piece for geom in geoms for piece in split_at_prime_meridian(geom)]
    ax.add_geometries(pieces, crs=ccrs.PlateCarree(), linewidth=0.3, **kwargs)


if date.today() >= NEXT_RECLASSIFICATION:
    print(f"WARNING: the World Bank reclassifies every 1 July. The API has probably moved past "
          f"{CLASSIFICATION_YEAR}; update tab:gni-categories in the paper to match.\n")

gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
countries = gpd.read_file(DATA_DIR / "country_shapefile" / "WB_GAD_ADM0.shp")

# --- One row per country/territory (some are split across several polygons) ---
countries = countries.dissolve(by='ISO_A3', as_index=False)

# --- Countries and territories with no gauges, with income group ---
iso_with_gauges = set(gauges['ISO_A3'].dropna())
has_gauges = countries[countries['ISO_A3'].isin(iso_with_gauges)]
no_gauges = countries[~countries['ISO_A3'].isin(iso_with_gauges)].copy()

income = fetch_wb_income_groups()
no_gauges['income_group'] = no_gauges['ISO_A3'].map(income)
no_gauges.loc[~no_gauges['income_group'].isin(COLORS), 'income_group'] = 'No data'

print(f"Income classification retrieved: {date.today().isoformat()} ({CLASSIFICATION_YEAR})")
print(f"Countries and territories with no gauges: {len(no_gauges)}")
for group in [*COLORS, 'No data']:
    print(f"  {group}: {(no_gauges['income_group'] == group).sum()}")

# --- Plot ---
fig = plt.figure(figsize=(15, 8))
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
ax.set_global()

draw(ax, has_gauges.geometry, facecolor=GAUGED_COLOR, edgecolor='black')
for group, color in COLORS.items():
    subset = no_gauges[no_gauges['income_group'] == group]
    draw(ax, subset.geometry, facecolor=color, edgecolor='black', alpha=0.7)
no_data = no_gauges[no_gauges['income_group'] == 'No data']
draw(ax, no_data.geometry, facecolor=NO_DATA_COLOR, edgecolor='black', hatch=NO_DATA_HATCH)

legend_patches = [Patch(facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.7, label=group.title())
                  for group, color in COLORS.items()]
legend_patches.append(Patch(facecolor=NO_DATA_COLOR, edgecolor='black', linewidth=0.5,
                            hatch=NO_DATA_HATCH, label='No Data'))
ax.legend(handles=legend_patches, loc='lower left', fontsize=10, title='Income Group', framealpha=0.9)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
