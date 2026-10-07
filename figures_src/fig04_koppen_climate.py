"""Figure 4: share of gauges vs share of land area in each Köppen climate group.

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
        data/koppen_geiger/1991_2020/koppen_geiger_0p00833333.tif
Writes: latex/figures/fig04_koppen_climate.png

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.

Köppen-Geiger classes are from Beck et al. (2023), present-day 1991-2020 map at 1 km.
Class numbers follow data/koppen_geiger/legend.txt; 0 is ocean. Land area includes Antarctica.
"""
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
KOPPEN_TIF = REPO_DIR / "data" / "koppen_geiger" / "1991_2020" / "koppen_geiger_0p00833333.tif"
OUTPUT = REPO_DIR / "latex" / "figures" / "fig04_koppen_climate.png"

# Main Köppen groups and the class numbers (legend.txt) that belong to each
GROUPS = {
    'Tropical': range(1, 4),     # Af, Am, Aw
    'Arid': range(4, 8),         # BWh, BWk, BSh, BSk
    'Temperate': range(8, 17),   # Cs*, Cw*, Cf*
    'Cold': range(17, 29),       # Ds*, Dw*, Df*
    'Polar': range(29, 31),      # ET, EF
}
CLASS_TO_GROUP = {code: group for group, codes in GROUPS.items() for code in codes}

SEARCH_RADIUS = 5      # pixels (~5 km) to look for land around gauges on an ocean pixel
EARTH_RADIUS_KM = 6371.0


def nearest_land_class(src, row, col):
    """Class of the nearest land pixel within SEARCH_RADIUS, or 0 if there is none."""
    r0, c0 = max(row - SEARCH_RADIUS, 0), max(col - SEARCH_RADIUS, 0)
    r1, c1 = min(row + SEARCH_RADIUS + 1, src.height), min(col + SEARCH_RADIUS + 1, src.width)
    block = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
    land_rows, land_cols = np.nonzero(block)
    if len(land_rows) == 0:
        return 0
    distance = (land_rows + r0 - row) ** 2 + (land_cols + c0 - col) ** 2
    best = np.argmin(distance)
    return int(block[land_rows[best], land_cols[best]])


def land_area_by_class(src, strip_rows=1000):
    """Area in km² of every class, weighting each pixel by its true size (shrinks with latitude)."""
    area = np.zeros(256)
    pixel_deg = src.res[0]
    pixel_km = np.radians(pixel_deg) * EARTH_RADIUS_KM
    for top in range(0, src.height, strip_rows):
        height = min(strip_rows, src.height - top)
        strip = src.read(1, window=Window(0, top, src.width, height))
        lat = src.bounds.top - (np.arange(top, top + height) + 0.5) * pixel_deg
        pixel_area = pixel_km ** 2 * np.cos(np.radians(lat))
        for code in CLASS_TO_GROUP:
            area[code] += ((strip == code).sum(axis=1) * pixel_area).sum()
    return area


gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
gauges['latitude'] = pd.to_numeric(gauges['latitude'], errors='coerce')
gauges['longitude'] = pd.to_numeric(gauges['longitude'], errors='coerce')
located = gauges.dropna(subset=['latitude', 'longitude'])

with rasterio.open(KOPPEN_TIF) as src:
    # --- Köppen class at each gauge ---
    codes = np.array([value[0] for value in src.sample(zip(located['longitude'], located['latitude']))])

    # --- Gauges on an ocean pixel (coastal): use the nearest land pixel ---
    on_ocean = np.flatnonzero(codes == 0)
    for i in on_ocean:
        row, col = src.index(located['longitude'].iloc[i], located['latitude'].iloc[i])
        codes[i] = nearest_land_class(src, row, col)

    # --- Land area of each class ---
    area = land_area_by_class(src)

unclassified = (codes == 0).sum()
gauge_groups = pd.Series(codes[codes > 0]).map(CLASS_TO_GROUP)

summary = pd.DataFrame({
    'gauges': gauge_groups.value_counts().reindex(list(GROUPS), fill_value=0),
    'area_km2': pd.Series({group: area[list(codes_)].sum() for group, codes_ in GROUPS.items()}),
})
summary['pct_gauges'] = 100 * summary['gauges'] / summary['gauges'].sum()
summary['pct_area'] = 100 * summary['area_km2'] / summary['area_km2'].sum()

print(f"Gauges in catalog: {len(gauges):,}")
print(f"Skipped (no coordinates): {len(gauges) - len(located):,}")
print(f"On an ocean pixel, moved to nearest land: {len(on_ocean) - unclassified:,}")
print(f"No land within {SEARCH_RADIUS} pixels (not counted): {unclassified:,}")
print(f"Gauges classified: {summary['gauges'].sum():,}")
print(f"Total land area: {summary['area_km2'].sum():,.0f} km² (includes Antarctica)")
print()
print(summary.round({'area_km2': 0, 'pct_gauges': 1, 'pct_area': 1}).to_string())

# --- Plot: % of gauges next to % of land area for each group ---
x = np.arange(len(GROUPS))
width = 0.38

fig, ax = plt.subplots(figsize=(9, 5))
gauge_bars = ax.bar(x - width / 2, summary['pct_gauges'], width, label='% of gauges', color='#1f77b4')
ax.bar(x + width / 2, summary['pct_area'], width, label='% of land area', color='#bbbbbb')

# Gauge count above each gauge bar
for bar, count in zip(gauge_bars, summary['gauges']):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{count:,}",
            ha='center', fontsize=8)

ax.set_xticks(x, list(GROUPS))
ax.set_xlabel("Köppen climate group")
ax.set_ylabel("Percent")
ax.legend(frameon=False)
ax.spines[['top', 'right']].set_visible(False)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
