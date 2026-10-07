"""Figure 5 data prep, step 2: the land area upstream of every gauge (rerun when the catalog changes).

Reads:  out/fig05_river_translation.csv                    (from fig05_translate_river_ids.py)
        <GEOGLOWS_V3_DIR>/global/metadata.parquet          v3 river network
        <GEOGLOWS_V3_DIR>/region=<id>/catchments_<id>.geo.parquet
        data/koppen_geiger/1991_2020/koppen_geiger_0p00833333.tif   (total land area for coverage %)
Writes: out/fig05_watersheds.parquet                 simplified to ~1 km (kept local, out of the repo)
        out/fig05_watersheds_v3/region_<id>.parquet   full detail, local only

GEOGLOWS_V3_DIR defaults to ../gauge-paper/hydrography_v3 (RFS / GEOGLOWS v3 hydrography).

An area counts as covered if any gauge is downstream of it. The v3 network is ordered so that
everything upstream of a river is the block of riverIndex values from riverIndex - upstreamCount
to riverIndex. Catchments are merged one region at a time with the fast "coverage" union, then
repaired; only the merged area and a simplified outline are kept in memory. Per-region files in
out/ are reused when they were built from the same set of rivers.

Usage: fig05_prepare_watersheds.py [region ...]
       With no arguments, every region is processed and the outputs in data/ are written.
       With region IDs, only those regions' files in out/ are made (for testing or resuming).
"""
import gc
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from rasterio.windows import Window
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
V3_DIR = Path(os.environ.get("GEOGLOWS_V3_DIR", REPO_DIR.parent / "gauge-paper" / "hydrography_v3"))
TRANSLATION = REPO_DIR / "out" / "fig05_river_translation.csv"
KOPPEN_TIF = REPO_DIR / "data" / "koppen_geiger" / "1991_2020" / "koppen_geiger_0p00833333.tif"
FULL_DIR = REPO_DIR / "out" / "fig05_watersheds_v3"
OUTPUT = REPO_DIR / "out" / "fig05_watersheds.parquet"

SIMPLIFY_DEG = 0.01        # ~1 km; invisible at the size of a world map
CHUNK = 25_000             # catchments merged at a time (a 10,000-catchment merge needs ~1 GB)
EARTH_RADIUS_KM = 6371.0


def equal_area_km2(geom):
    """Area in km²; polygons crossing 180° are split at 0° first so they measure correctly."""
    minx, _, maxx, _ = geom.bounds
    parts = [geom]
    if minx < -179 and maxx > 179:
        parts = [geom.intersection(box(-180, -90, 0, 90)), geom.intersection(box(0, -90, 180, 90))]
    return gpd.GeoSeries(parts, crs="EPSG:4326").to_crs("ESRI:54034").area.sum() / 1e6  # World Cylindrical Equal Area


def land_area_km2(src, south_limit=-90.0, strip_rows=1000):
    """Land area (non-ocean pixels) north of south_limit, weighting pixels by their true size."""
    total = 0.0
    pixel_deg = src.res[0]
    pixel_km = np.radians(pixel_deg) * EARTH_RADIUS_KM
    for top in range(0, src.height, strip_rows):
        height = min(strip_rows, src.height - top)
        strip = src.read(1, window=Window(0, top, src.width, height))
        lat = src.bounds.top - (np.arange(top, top + height) + 0.5) * pixel_deg
        pixel_area = pixel_km ** 2 * np.cos(np.radians(lat))
        land = (strip > 0).sum(axis=1) * pixel_area
        total += land[lat > south_limit].sum()
    return total


started = time.time()
wanted = set(sys.argv[1:])

# --- Gauged v3 rivers (translated from the catalog's v2 river IDs) ---
translation = pd.read_csv(TRANSLATION)
per_river = translation.drop_duplicates('v2_river_id')
left_out = per_river['method'].str.startswith('left out')
print(f"Gauged rivers: {len(per_river):,} ({per_river['gauges'].sum():,} gauges); "
      f"left out {left_out.sum():,} ({per_river.loc[left_out, 'gauges'].sum():,} gauges)")
gauged = translation['v3_river_id'].dropna().astype('int64').unique()

# --- Everything upstream of a gauged river: the riverIndex block ending at each one ---
network = pd.read_parquet(V3_DIR / "global" / "metadata.parquet",
                          columns=['riverId', 'riverIndex', 'upstreamCount', 'TDXHydroRegion'])
if not np.array_equal(np.sort(network['riverIndex'].to_numpy()), np.arange(len(network))):
    sys.exit("riverIndex is not 0..n-1; the upstream blocks below would be wrong")
at_gauge = network[network['riverId'].isin(gauged)]
marks = np.zeros(len(network) + 1, dtype=np.int64)
np.add.at(marks, (at_gauge['riverIndex'] - at_gauge['upstreamCount']).to_numpy(), 1)
np.add.at(marks, (at_gauge['riverIndex'] + 1).to_numpy(), -1)
covered = np.cumsum(marks[:-1]) > 0
upstream_network = network[covered[network['riverIndex'].to_numpy()]]
print(f"Gauged v3 rivers: {len(at_gauge):,} of {len(gauged):,}; upstream rivers: {len(upstream_network):,} "
      f"in {upstream_network['TDXHydroRegion'].nunique()} regions ({time.time() - started:.0f}s)")
del network, at_gauge, marks, covered
gc.collect()

# --- Merge the upstream catchments in each region ---
FULL_DIR.mkdir(parents=True, exist_ok=True)
kept = []
covered_km2 = 0.0
for region, rivers in upstream_network.groupby('TDXHydroRegion')['riverIndex']:
    region = str(region)
    if wanted and region not in wanted:
        continue
    full_path = FULL_DIR / f"region_{region}.parquet"
    reuse = (full_path.exists() and
             pd.read_parquet(full_path, columns=['n_rivers'])['n_rivers'].iloc[0] == len(rivers))
    if reuse:
        region_area = gpd.read_parquet(full_path)
        print(f"Region {region}: reused")
    else:
        catchment_path = V3_DIR / f"region={region}" / f"catchments_{region}.geo.parquet"
        if not catchment_path.exists():
            print(f"Region {region}: no catchment file, skipped")
            continue
        # Merge CHUNK neighbouring catchments at a time (consecutive riverIndex values are
        # neighbours), reading only those, then merge the chunk outlines. Keeps memory down in
        # the largest regions; the result is the same as merging everything at once.
        rivers = rivers.sort_values()
        pieces, standard_merges = [], 0
        for start in range(0, len(rivers), CHUNK):
            catchments = gpd.read_parquet(catchment_path, columns=['riverIndex', 'geometry'],
                                          filters=[('riverIndex', 'in', rivers.iloc[start:start + CHUNK].tolist())])
            crs = catchments.crs
            try:
                # Fast merge, for catchments that tile exactly without overlapping
                merged = catchments.union_all(method='coverage')
            except shapely.errors.GEOSException:
                # Some catchment edges don't line up exactly; use the standard (slower) merge
                merged = catchments.union_all()
                standard_merges += 1
            if not merged.is_valid:
                # The fast merge can leave shapes nested inside each other; this repairs them
                # without changing the area
                merged = shapely.make_valid(merged, method='structure', keep_collapsed=False)
            pieces.append(merged)
            del catchments, merged
            gc.collect()
        outline = shapely.union_all(pieces)
        region_area = gpd.GeoDataFrame({'region': [region], 'n_rivers': [len(rivers)]},
                                       geometry=[outline], crs=crs).to_crs("EPSG:4326")
        region_area.to_parquet(full_path)
        print(f"Region {region}: {len(rivers):,} catchments merged in {len(pieces)} chunk(s), "
              f"{standard_merges} needing the standard merge ({time.time() - started:.0f}s)")
        del pieces, outline

    # Keep only the area and a simplified outline; free the full-detail shape before the next region
    outline = region_area.geometry.iloc[0]
    covered_km2 += equal_area_km2(outline)
    kept.append({'region': region, 'geometry': outline.simplify(SIMPLIFY_DEG, preserve_topology=True)})
    del region_area, outline
    gc.collect()

if wanted:
    print(f"Done with region(s) {', '.join(sorted(wanted))}; run without arguments to write the outputs in data/")
    sys.exit(0)

# --- Coverage: share of the world's land area that drains to a gauge ---
with rasterio.open(KOPPEN_TIF) as src:
    land_all = land_area_km2(src)
    land_no_antarctica = land_area_km2(src, south_limit=-60.0)

print(f"Area draining to a gauge: {covered_km2:,.0f} km²")
print(f"  {100 * covered_km2 / land_all:.1f}% of all land ({land_all:,.0f} km², includes Antarctica)")
print(f"  {100 * covered_km2 / land_no_antarctica:.1f}% of land excluding Antarctica "
      f"({land_no_antarctica:,.0f} km², north of 60°S)")

# --- Simplified copy for the repo ---
simplified = gpd.GeoDataFrame(kept, crs="EPSG:4326")
simplified.to_parquet(OUTPUT)
print(f"Saved {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB, {time.time() - started:.0f}s total)")
