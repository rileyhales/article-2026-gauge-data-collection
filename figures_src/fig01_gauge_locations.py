"""Figure 1: locations of all gauges, marked by discharge, water level, or both.

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
Writes: latex/figures/fig01_gauge_locations.png

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.
"""
import os
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
OUTPUT = REPO_DIR / "latex" / "figures" / "fig01_gauge_locations.png"

gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)

# --- Clean columns ---
gauges['latitude'] = pd.to_numeric(gauges['latitude'], errors='coerce')
gauges['longitude'] = pd.to_numeric(gauges['longitude'], errors='coerce')
gauges['discharge'] = pd.to_numeric(gauges['discharge'], errors='coerce').fillna(0)
gauges['water_level'] = pd.to_numeric(gauges['water_level'], errors='coerce').fillna(0)

# --- Drop gauges without coordinates (they cannot be mapped) ---
located = gauges.dropna(subset=['latitude', 'longitude'])
print(f"Gauges in catalog: {len(gauges):,}")
print(f"Skipped (no coordinates): {len(gauges) - len(located):,}")

# --- Categorize by data type ---
both = located[(located['discharge'] == 1) & (located['water_level'] == 1)]
discharge_only = located[(located['discharge'] == 1) & (located['water_level'] != 1)]
waterlevel_only = located[(located['discharge'] != 1) & (located['water_level'] == 1)]
neither = len(located) - len(both) - len(discharge_only) - len(waterlevel_only)

print(f"Discharge only: {len(discharge_only):,}")
print(f"Water level only: {len(waterlevel_only):,}")
print(f"Both: {len(both):,}")
print(f"Neither (not plotted): {neither:,}")

# --- Plot with basemap ---
fig = plt.figure(figsize=(14, 7))
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

# Basemap features
ax.set_global()
ax.add_feature(cfeature.LAND, facecolor='#f0f0f0', edgecolor='none')
ax.add_feature(cfeature.OCEAN, facecolor='#d4eaf7')
ax.add_feature(cfeature.COASTLINE, linewidth=0.4, color='#888888')
ax.add_feature(cfeature.BORDERS, linewidth=0.2, color='#cccccc')
ax.add_feature(cfeature.RIVERS, linewidth=0.2, color='#a8d0e6')
ax.add_feature(cfeature.LAKES, facecolor='#d4eaf7', edgecolor='#a8d0e6', linewidth=0.2)

# Plot each category (plot "both" last so it's on top)
ax.scatter(
    discharge_only['longitude'], discharge_only['latitude'],
    s=1.5, color='#1f77b4', alpha=0.6, transform=ccrs.PlateCarree(),
    label=f'Discharge ({len(discharge_only):,})', zorder=3,
)
ax.scatter(
    waterlevel_only['longitude'], waterlevel_only['latitude'],
    s=1.5, color='#ff7f0e', alpha=0.6, transform=ccrs.PlateCarree(),
    label=f'Water Level ({len(waterlevel_only):,})', zorder=3,
)
ax.scatter(
    both['longitude'], both['latitude'],
    s=1.5, color='#2ca02c', alpha=0.6, transform=ccrs.PlateCarree(),
    label=f'Both ({len(both):,})', zorder=4,
)

ax.legend(loc='lower left', fontsize=9, markerscale=6, framealpha=0.9)

plt.savefig(OUTPUT, dpi=600, bbox_inches='tight')
print(f"Saved {OUTPUT}")
