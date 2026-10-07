"""Figure 5 data prep: the land area upstream of every gauge (slow; rerun when the catalog changes).

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
        <GEOGLOWS_DIR>/v2-model-table.parquet               GEOGLOWS v2 river network
        <GEOGLOWS_DIR>/hydrography/vpu=<VPU>/catchments_<VPU>.parquet
        data/koppen_geiger/1991_2020/koppen_geiger_0p00833333.tif   (total land area for coverage %)
Writes: data/fig05_watersheds.parquet       simplified to ~1 km, small enough for the repo
        out/fig05_watersheds/vpu_<VPU>.parquet   full detail, local only

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.
GEOGLOWS_DIR defaults to ../gauge-paper (a local copy of the GEOGLOWS v2 data).

An area counts as covered if any gauge is downstream of it: starting from every gauged river
(final_river_id), walk upstream through the network and merge the catchments of every river found.
Per-VPU files in out/ are reused when they were built from the same set of rivers.

To keep memory down, only one VPU is processed at a time: only its upstream catchments are read,
and once its merged area is saved, only the area and a simplified outline are kept.
"""
import gc
import os
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import rasterio
from rasterio.windows import Window
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
GEOGLOWS_DIR = Path(os.environ.get("GEOGLOWS_DIR", REPO_DIR.parent / "gauge-paper"))
KOPPEN_TIF = REPO_DIR / "data" / "koppen_geiger" / "1991_2020" / "koppen_geiger_0p00833333.tif"
FULL_DIR = REPO_DIR / "out" / "fig05_watersheds"
OUTPUT = REPO_DIR / "data" / "fig05_watersheds.parquet"

SIMPLIFY_DEG = 0.01        # ~1 km; invisible at the size of a world map
UNMATCHED = [0, -1]        # final_river_id values meaning "not matched to a river"
EARTH_RADIUS_KM = 6371.0


def upstream_rivers(start_ids, links, downstream):
    """Every river upstream of (and including) the start rivers."""
    order = np.argsort(downstream, kind='stable')
    parents, first = np.unique(downstream[order], return_index=True)
    children = dict(zip(parents, np.split(links[order], first[1:])))

    visited = set()
    stack = list(start_ids)
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(children.get(current, ()))
    return visited


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

# --- Gauged rivers ---
gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
river_id = pd.to_numeric(gauges['final_river_id'], errors='coerce')
matched = river_id.notna() & ~river_id.isin(UNMATCHED)
gauged_rivers = set(river_id[matched].astype('int64'))

# --- River network ---
network = pd.read_parquet(GEOGLOWS_DIR / "v2-model-table.parquet",
                          columns=['LINKNO', 'DSLINKNO', 'VPUCode'])
in_network = gauged_rivers & set(network['LINKNO'])

print(f"Gauges in catalog: {len(gauges):,}")
print(f"  Not matched to a river (final_river_id 0/-1/blank): {(~matched).sum():,}")
print(f"  Matched: {matched.sum():,} gauges on {len(gauged_rivers):,} rivers")
print(f"  Rivers not found in the GEOGLOWS v2 network: {len(gauged_rivers - in_network):,}")

upstream = upstream_rivers(in_network, network['LINKNO'].to_numpy(), network['DSLINKNO'].to_numpy())
upstream_network = network[network['LINKNO'].isin(upstream)]
print(f"Upstream rivers: {len(upstream_network):,} in {upstream_network['VPUCode'].nunique()} VPUs "
      f"({time.time() - started:.0f}s)")
del gauges, network, upstream
gc.collect()

# --- Merge the upstream catchments in each VPU ---
FULL_DIR.mkdir(parents=True, exist_ok=True)
kept = []
covered_km2 = 0.0
for vpu, rivers in upstream_network.groupby('VPUCode')['LINKNO']:
    full_path = FULL_DIR / f"vpu_{vpu}.parquet"
    reuse = (full_path.exists() and
             pd.read_parquet(full_path, columns=['n_rivers'])['n_rivers'].iloc[0] == len(rivers))
    if reuse:
        vpu_area = gpd.read_parquet(full_path)
        print(f"VPU {vpu}: reused")
    else:
        catchment_path = GEOGLOWS_DIR / "hydrography" / f"vpu={vpu}" / f"catchments_{vpu}.parquet"
        if not catchment_path.exists():
            print(f"VPU {vpu}: no catchment file, skipped")
            continue

        # The river id column is 'LINKNO' in some files and 'linkno' in others
        link_col = next(name for name in pq.read_schema(catchment_path).names if name.lower() == 'linkno')
        # Read only the upstream catchments, not the whole VPU
        catchments = gpd.read_parquet(catchment_path, columns=[link_col, 'geometry'],
                                      filters=[(link_col, 'in', rivers.tolist())])
        vpu_area = catchments[['geometry']].dissolve()
        vpu_area['VPU'] = vpu
        vpu_area['n_rivers'] = len(rivers)
        vpu_area = vpu_area.to_crs("EPSG:4326")
        vpu_area.to_parquet(full_path)
        print(f"VPU {vpu}: {len(catchments):,} catchments merged ({time.time() - started:.0f}s)")
        del catchments

    # Keep only the area and a simplified outline; free the full-detail shape before the next VPU
    outline = vpu_area.geometry.iloc[0]
    covered_km2 += equal_area_km2(outline)
    kept.append({'VPU': vpu, 'geometry': outline.simplify(SIMPLIFY_DEG, preserve_topology=True)})
    del vpu_area, outline
    gc.collect()

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
