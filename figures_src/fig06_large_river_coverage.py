"""Figure 6: large rivers (more than 50,000 km² upstream), coloured by whether a gauge is at or below them.

Reads:  out/fig05_river_translation.csv            (from fig05_translate_river_ids.py)
        <GEOGLOWS_V3_DIR>/global/metadata.parquet  v3 river network
Writes: latex/figures/fig06_large_river_coverage.png

GEOGLOWS_V3_DIR defaults to ../gauge-paper/hydrography_v3 (RFS / GEOGLOWS v3 hydrography).

A river counts as gauged if any gauge is at or downstream of it, the same rule as Figure 5. Each
reach is drawn as a line from its own point to the point of the river it flows into, with the line
width growing with upstream area.
"""
import os
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

REPO_DIR = Path(__file__).resolve().parent.parent
V3_DIR = Path(os.environ.get("GEOGLOWS_V3_DIR", REPO_DIR.parent / "gauge-paper" / "hydrography_v3"))
TRANSLATION = REPO_DIR / "out" / "fig05_river_translation.csv"
OUTPUT = REPO_DIR / "latex" / "figures" / "fig06_large_river_coverage.png"

MIN_AREA_KM2 = 50_000
GAUGED_COLOR = '#1f77b4'    # same blue as Figure 5
UNGAUGED_COLOR = '#d95f02'

# --- Which rivers have a gauge at or below them: the riverIndex block ending at each gauged river ---
network = pd.read_parquet(V3_DIR / "global" / "metadata.parquet",
                          columns=['riverId', 'nextRiverId', 'riverIndex', 'upstreamCount',
                                   'USContArea', 'Length', 'lat', 'lon'])
network = network.sort_values('riverIndex').reset_index(drop=True)
gauged = pd.read_csv(TRANSLATION)['v3_river_id'].dropna().astype('int64').unique()
at_gauge = network[network['riverId'].isin(gauged)]
marks = np.zeros(len(network) + 1, dtype=np.int64)
np.add.at(marks, (at_gauge['riverIndex'] - at_gauge['upstreamCount']).to_numpy(), 1)
np.add.at(marks, (at_gauge['riverIndex'] + 1).to_numpy(), -1)
network['gauged'] = np.cumsum(marks[:-1]) > 0

# --- Large rivers, each drawn to the point of the river it flows into ---
large = network[network['USContArea'] / 1e6 > MIN_AREA_KM2].copy()
points = network.set_index('riverId')[['lat', 'lon']]
downstream = points.reindex(large['nextRiverId'])
large['next_lat'] = downstream['lat'].to_numpy()
large['next_lon'] = downstream['lon'].to_numpy()
large = large.dropna(subset=['next_lat'])                     # outlets: nothing downstream to draw to
large = large[(large['next_lon'] - large['lon']).abs() < 5]  # skip jumps across 180°

length_km = large['Length'] / 1e3
share = 100 * length_km[large['gauged']].sum() / length_km.sum()
print(f"Large rivers (> {MIN_AREA_KM2:,} km²): {length_km.sum():,.0f} km, "
      f"{share:.1f}% with a gauge at or below")

# Line width grows with log upstream area: ~0.3 at 50,000 km², ~1.6 at 5 million km²
area_km2 = large['USContArea'] / 1e6
large['width'] = 0.3 + 1.3 * np.log10(area_km2 / MIN_AREA_KM2) / 2

# --- Plot with basemap ---
fig = plt.figure(figsize=(14, 7))
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

# Basemap features
ax.set_global()
ax.add_feature(cfeature.LAND, facecolor='#f0f0f0', edgecolor='none')
ax.add_feature(cfeature.OCEAN, facecolor='#d4eaf7')
ax.add_feature(cfeature.COASTLINE, linewidth=0.4, color='#888888', zorder=1)
ax.add_feature(cfeature.BORDERS, linewidth=0.2, color='#bbbbbb', zorder=1)

# Ungauged first so gauged rivers sit on top where they meet
for is_gauged, color in [(False, UNGAUGED_COLOR), (True, GAUGED_COLOR)]:
    rivers = large[large['gauged'] == is_gauged]
    segments = np.stack([rivers[['lon', 'lat']].to_numpy(),
                         rivers[['next_lon', 'next_lat']].to_numpy()], axis=1)
    ax.add_collection(LineCollection(segments, colors=color, linewidths=rivers['width'].to_numpy(),
                                     capstyle='round', transform=ccrs.PlateCarree(), zorder=2))

ax.legend(handles=[Line2D([], [], color=GAUGED_COLOR, linewidth=2, label='Gauge at or downstream'),
                   Line2D([], [], color=UNGAUGED_COLOR, linewidth=2, label='No gauge at or downstream')],
          title=f'Rivers draining more than {MIN_AREA_KM2:,} km²', loc='lower left', fontsize=10,
          title_fontsize=10, frameon=True, framealpha=0.9)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
