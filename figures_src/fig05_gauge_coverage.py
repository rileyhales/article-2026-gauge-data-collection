"""Figure 5: land area upstream of at least one gauge.

Reads:  out/fig05_watersheds.parquet    (made by fig05_prepare_watersheds.py; kept local, out of the repo)
Writes: latex/figures/fig05_gauge_coverage.png
"""
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
WATERSHEDS = REPO_DIR / "out" / "fig05_watersheds.parquet"
OUTPUT = REPO_DIR / "latex" / "figures" / "fig05_gauge_coverage.png"


def split_at_prime_meridian(geom):
    """Split polygons crossing 180° into west and east halves so they project cleanly."""
    minx, _, maxx, _ = geom.bounds
    if not (minx < -179 and maxx > 179):
        return [geom]
    halves = [geom.intersection(box(-180, -90, 0, 90)), geom.intersection(box(0, -90, 180, 90))]
    return [h for h in halves if not h.is_empty]


watersheds = gpd.read_parquet(WATERSHEDS)
pieces = [piece for geom in watersheds.geometry for piece in split_at_prime_meridian(geom)]

# --- Plot with basemap ---
fig = plt.figure(figsize=(14, 7))
ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

# Basemap features
ax.set_global()
ax.add_feature(cfeature.LAND, facecolor='#f0f0f0', edgecolor='none')
ax.add_feature(cfeature.OCEAN, facecolor='#d4eaf7')

# Watersheds draining to a gauge
ax.add_geometries(pieces, crs=ccrs.PlateCarree(), facecolor='#1f77b4', edgecolor='none',
                  alpha=0.7, zorder=2)

ax.add_feature(cfeature.COASTLINE, linewidth=0.4, color='#888888', zorder=3)
ax.add_feature(cfeature.BORDERS, linewidth=0.2, color='#888888', zorder=3)

plt.savefig(OUTPUT, dpi=300, bbox_inches='tight')
print(f"Saved {OUTPUT}")
