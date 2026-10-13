"""Figure 5 data prep, step 1: translate the gauges' GEOGLOWS v2 river IDs to the v3 hydrography.

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv     final_river_id (v2 river IDs)
        <GEOGLOWS_V2_DIR>/v2-model-table.parquet              v2 river network
        <GEOGLOWS_V3_DIR>/global/metadata.parquet             v3 river network
        <GEOGLOWS_V3_DIR>/region=<id>/mods/*.json              edits v3 made to the v2 rivers
Writes: out/fig05_river_translation.csv    one row per gauged v2 river and v3 river, with the method
        (kept out of the repo: the river IDs show where the gauges are, including private ones)

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.
GEOGLOWS_V2_DIR defaults to ../gauge-paper and GEOGLOWS_V3_DIR to ../gauge-paper/hydrography_v3.

Methods (v3_river_id is blank when the gauge is left out):
    same id        the v2 river exists unchanged in v3
    merged reach   v3 merged the reach into a neighbour; use the river it was merged into
    lake outlet    reach inside a lake with all the lake's inlets upstream; use the lake's outlet river
    lake inlets    reach inside a lake with some inlets upstream; use those inlets (one row each)
    left out: ...  absorbed into a lake with no inlets upstream, pruned branch, zero-length reach,
                   basin not in v3, or river not in the v2 network
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
V2_DIR = Path(os.environ.get("GEOGLOWS_V2_DIR", REPO_DIR.parent / "gauge-paper"))
V3_DIR = Path(os.environ.get("GEOGLOWS_V3_DIR", REPO_DIR.parent / "gauge-paper" / "hydrography_v3"))
OUTPUT = REPO_DIR / "out" / "fig05_river_translation.csv"

UNMATCHED = [0, -1]  # final_river_id values meaning "not matched to a river"
MERGED = ['short_consolidations', 'headwater_dissolves', 'coastal_orphans']  # reach merged into a neighbour


def upstream_rivers(start, children):
    """Every river upstream of (and including) start."""
    visited, stack = set(), [start]
    while stack:
        current = stack.pop()
        if current not in visited:
            visited.add(current)
            stack.extend(children.get(current, ()))
    return visited


# --- Gauged v2 rivers and the number of gauges on each ---
gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
river_id = pd.to_numeric(gauges['final_river_id'], errors='coerce')
gauges_per_river = river_id[river_id.notna() & ~river_id.isin(UNMATCHED)].astype('int64').value_counts()

# --- River networks ---
v2 = pd.read_parquet(V2_DIR / "v2-model-table.parquet", columns=['LINKNO', 'DSLINKNO'])
v2_ids = set(v2['LINKNO'])
order = np.argsort(v2['DSLINKNO'].to_numpy(), kind='stable')
parents, first = np.unique(v2['DSLINKNO'].to_numpy()[order], return_index=True)
v2_children = dict(zip(parents, np.split(v2['LINKNO'].to_numpy()[order], first[1:])))
v3_ids = set(pd.read_parquet(V3_DIR / "global" / "metadata.parquet", columns=['riverId'])['riverId'])

# --- What the v3 edits did to each removed v2 reach ---
merged_into, in_lake, removed = {}, {}, {}
for path in sorted(V3_DIR.glob("region=*/mods/*.json")):
    edits = json.loads(path.read_text())
    if path.stem in MERGED:
        for kept, gone in edits.items():
            for reach in gone:
                merged_into.setdefault(int(reach), int(kept))
    elif path.stem == 'lake_edits':
        for outlet, lake in edits.items():
            for reach in lake['delete']:
                in_lake.setdefault(int(reach), (int(outlet), [int(i) for i in lake['inlets']]))
    elif path.stem == 'branches_to_prune':
        for _, gone in edits.items():
            for reach in gone:
                removed.setdefault(int(reach), 'left out: pruned branch')
    elif path.stem == 'zero_length_streams':
        for case in edits.values():
            for reach in case['ids']:
                removed.setdefault(int(reach), 'left out: zero-length reach')


def translate(river):
    """[(v3 river or None, method), ...] for one gauged v2 river."""
    if river in v3_ids:
        return [(river, 'same id')]
    if river not in v2_ids:
        return [(None, 'left out: not in v2 network')]
    if river in in_lake:
        outlet, inlets = in_lake[river]
        upstream = upstream_rivers(river, v2_children)
        inlets_upstream = [i for i in inlets if i in upstream]
        if inlets and len(inlets_upstream) == len(inlets) and outlet in v3_ids:
            return [(outlet, 'lake outlet')]
        if any(i in v3_ids for i in inlets_upstream):
            return [(i, 'lake inlets') for i in inlets_upstream if i in v3_ids]
        return [(None, 'left out: absorbed into a lake')]
    if river in merged_into:
        target = river
        for _ in range(50):  # a reach can be merged more than once
            target = merged_into.get(target, target)
            if target in v3_ids:
                return [(target, 'merged reach')]
        return [(None, 'left out: merged reach not in v3')]
    if river in removed:
        return [(None, removed[river])]
    return [(None, 'left out: basin not in v3')]


rows = [(river, n, v3, method)
        for river, n in gauges_per_river.items()
        for v3, method in translate(river)]
table = pd.DataFrame(rows, columns=['v2_river_id', 'gauges', 'v3_river_id', 'method'])
table['v3_river_id'] = table['v3_river_id'].astype('Int64')

# --- Summary: gauged rivers and gauges per method (a river with several lake inlets counted once) ---
per_river = table.drop_duplicates('v2_river_id')
summary = per_river.groupby('method').agg(rivers=('v2_river_id', 'size'), gauges=('gauges', 'sum'))
print(summary.sort_values('gauges', ascending=False).to_string())
left_out = per_river['method'].str.startswith('left out')
print(f"Total: {len(per_river):,} rivers, {per_river['gauges'].sum():,} gauges; "
      f"left out {left_out.sum():,} rivers, {per_river.loc[left_out, 'gauges'].sum():,} gauges")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
table.sort_values(['v2_river_id', 'v3_river_id']).to_csv(OUTPUT, index=False)
print(f"Saved {OUTPUT} ({len(table):,} rows)")
