# Data notes

Issues found in `master_catalog_with_metadata.csv` (37,528 rows, checked 2026-10-06).

## ⚠️ Metadata columns belong to the wrong gauge (93% of rows that have them)
- In 16,669 of 17,928 rows, `samplingFeatureCode` is a different station than the row's own gauge
  (`excel_Gauge Name/Number` = `jorge_samplingFeatureCode`, which always agree). All providers:
  100% wrong except GRDC (69%). Likely the metadata was joined on the wrong key or by row order.
- Example: row for USGS 01112500 Blackstone River at Woonsocket, RI (coordinates match) has the
  metadata of 01087000 Blackwater River near Webster, NH.
- Affected columns: `samplingFeatureCode`, `name`, `River`, `elevation_m`, `county`, `country_name`,
  `country_id`, `samplingFeatureType`, `siteType`, `elevationDatum`, `description`, `dataDisclaimer`,
  `isVisible`, `GEOGloWS_v1_region`, `GEOGloWS_v2_vpu`, `matching_column_v2`.
- Probably not affected (also filled in rows without metadata, so from another source):
  coordinates, `discharge`, `water_level`, `final_river_id`, `ISO_A3`, `start_date`, `end_date`.

## Missing coordinates
- 1,760 gauges have no latitude/longitude, so they cannot appear on maps.
  Mexico 1,565 · India 170 · Bhutan 12 · Afghanistan 4 · UK 4 · China 2 · Nepal, Russia, USA 1 each
- All of them still have an ISO_A3 code, so they are counted in per-country analyses.

## Duplicates: Caravan copies of agency gauges (kept for now, pending discussion)
- 4,056 Caravan rows are copies of a gauge already in the catalog from the national agency
  (the Caravan ID contains the agency ID, e.g. `hysets_06091700` = USGS `06091700`):
  USGS 3,265 · HYDAT 470 · BoM 119 · ANA 71.
- Without them: 33,472 gauges instead of 37,528 (USA 8,504 instead of 11,806; Canada 2,623
  instead of 3,089). Would change the counts in the text, Figure 1 legend, Figure 4 and income table.
- Other checks: no identical rows (`hash` is unique); `gauge_id` is not unique (473 IDs reused by
  different gauges in different countries); 2,786 extra rows share coordinates and name with
  another row, mostly these Caravan copies. (An earlier count of 367 used the `name` column,
  which belongs to the wrong gauge in most rows.)

## Shared locations
- 3,040 locations (rounded to 5 decimal places) are shared by more than one gauge,
  6,447 gauges in total. This includes the same-name duplicates above.
- Mostly USA (4,888), Canada (580), UK (342), Mexico (249), France (206).
- Some are genuinely co-located gauges; others may be rounded coordinates
  (e.g. GRDC uses 2 decimal places) or errors
  (e.g. Ecuador H0854 and H0961 are different stations with identical coordinates).

## Open questions
- **Where did the `ISO_A3` column come from?** Need to confirm how it was created before relying on it.
  - It matches a spatial join against the World Bank `WB_GAD_ADM0` shapefile for all 35,564 gauges
    that fall inside a country polygon, so it was probably made that way.
  - But it is also filled for the 1,760 gauges with no coordinates and the 204 gauges that fall
    outside every polygon (e.g. on coastlines), so those must have been assigned some other way
    (country name columns? manually?).
- **Where did the `Koppen Group (as of 2024)` column come from?** Unknown, so it is NOT used.
  - Filled for 35,478 gauges (Temperate 17,406 · Continental 8,464 · Arid 5,012 ·
    Tropical 4,528 · Polar 68); 2,050 missing (1,760 without coordinates + 290 others).
  - Disagrees with the old Figure 4 notebook (e.g. polar 68 vs 327).
  - Not produced by `2b_koppen_tdxhydro.py` (that labels TDX-Hydro catchments, not gauges).
- **When was the gauge data collected?** Need the date the catalog was assembled (and/or the
  date range of each source) to compare with the World Bank data year (FY2027 groups, based on
  2025 GNI per capita).

## Gauges in the ocean
- 145 gauges are more than ~5 km from any land pixel in the Köppen map, so they are left out of
  Figure 4. They still appear as dots in the ocean in Figure 1.
- 140 of them are French (ISO_A3 = FRA). Their coordinates look scrambled: latitudes like
  metropolitan France (43–50°N) paired with Caribbean / French Guiana longitudes (around -61° and -54°).
  Names include French Guiana rivers (La Mana, Le Maroni, L'Oyapock) and metropolitan rivers
  (La Meuse, La Serre). Likely lat/lon taken from different sources or rows when merging.
  Examples: gauge_id 1015000101 (44.78, -61.69), 5220000101 (45.43, -54.05).
- The other 5: Mexico B12753 and PTGVC (in the Gulf of Mexico), Russia 71035, 71188, 71199
  (White Sea / Barents Sea coast).
- French station names also have garbled characters (text encoding problem), e.g. "La C???re".

## Gauges not matched to a river
- 11,834 gauges (32%) have `final_river_id` = -1 (11,639) or 0 (195), meaning they were not
  matched to a GEOGLOWS v2 river. They cannot contribute to the watershed coverage in Figure 5.
- ~3,640 of them are copies of a gauge that IS matched (3,521 Caravan copies of agency gauges, plus
  117 same-name, same-location copies: CEDEX 55, EA 37, SIH 17, …). So ~8,200 are genuinely unmatched.
- The older `master_catalog.csv` (used for the original Figure 5) had 8,417 unmatched.
- Most affected: USA 4,302 (36% of its gauges) · UK 2,401 (67%) · Mexico 2,272 (79%) ·
  France 1,267 (30%) · India 712 (75%) · Canada 368 (12%) · Spain 175 (11%).
- Likely explains the Word comment on Figure 5: "Something is wrong because I think we do
  have gauges in a couple spots that aren't showing."
- Need to find out why these were not matched (and who did the matching).

## Translating gauge river IDs from v2 to v3 (Figure 5)
`final_river_id` holds GEOGLOWS **v2** river IDs; Figure 5 now uses the **v3** hydrography
(see Decisions). Checked 2026-10-07:
- 24,405 gauged v2 rivers (25,694 gauges). **20,250 have the same ID in v3**, and where IDs match
  the upstream areas agree within 5%, so they are the same rivers.
- 7 gauged rivers are not in the v2 network at all → left out.
- 4,148 rivers (4,331 gauges) were changed by the v3 edits recorded in each region's `mods/` folder:
  - **3,509 rivers (3,660 gauges): short reach merged into a neighbour** (`short_consolidations`)
    → mapped to the river it was merged into. Upstream area +2% (median); 156 over +25%, 7 over 2×.
  - **147 rivers (154 gauges): reach inside a lake** (`lake_edits`). v3 deletes in-lake reaches and
    turns each lake into one outlet river with its inlets flowing straight into it. All 154 are
    discharge gauges (none lake-level only); mostly Canada (104) and USA (23), e.g. Great Lakes.
    - 12 gauges with **all** the lake's inlets upstream (≈ at the outlet, ~5 km away)
      → mapped to the lake outlet.
    - 77 gauges with **some** inlets upstream (~3 km from an inlet, ~83 km from the outlet)
      → mapped to those inlets (their own river where it enters the lake).
    - 65 gauges with **no** inlets upstream (small rivers whose whole reach v3 absorbed into the lake)
      → **left out**. Mapping them to the outlet would claim ~8,000× their area (median).
      Example: Welland River near Binbrook → outlet would be 10,000× its own area.
  - 1 river (1 gauge): pruned side branch (`branches_to_prune`) → **left out**.
  - **491 rivers (516 gauges): in no edit file; their whole basin is missing from v3** → **left out**.
    For 434 of the 516 gauges there is no v3 river within ~5 km. Mostly small coastal basins
    (median 101 km²) in Canada, France, UK, USA, Spain, Chile, but also two large inland basins in
    Australia's Lake Eyre region (226,772 and 108,737 km²) and three large northern Quebec rivers
    (49,000–110,000 km²), which will show as gaps in Figure 5.
- **In total 589 gauges (561 rivers) are left out of Figure 5**, 2.3% of the 25,694 gauges matched
  to a river: 516 basin not in v3 · 65 absorbed into a lake · 7 river not in the v2 network ·
  1 pruned branch. Used: 21,356 same id · 3,660 merged reach · 77 lake inlets · 12 lake outlet.
- The translation is written by `figures_src/fig05_translate_river_ids.py` to
  `out/fig05_river_translation.csv` (one row per gauged river and v3 river, with the reason).
  It is kept out of the repo (`out/` is gitignored) because the river IDs show where the gauges
  are, including private ones; anyone building Figure 5 regenerates it with that script.

## ⚠️ No USGS gauges on large rivers (Figure 5 gaps in the Mississippi), checked 2026-10-13
- All 7,599 USGS rows (`archive-gauge-data/jorge_20250909/North_America/USA`) drain at most
  ~55,500 km² (v2 upstream area; 99th percentile 37,000 km²). Looks like the USGS list was cut off
  at ~50,000 km² drainage area where it was assembled. Unknown why; ask who built the archive.
- So the catalog has no gauges on the Mississippi below Minnesota, the Missouri below Montana, the
  Ohio, or the Arkansas below Colorado. No St. Louis, Vicksburg, Hermann or Metropolis.
  (`gauge_id` 6934500 is a GRDC station in Denmark, not Missouri River at Hermann.)
  The Caravan rows near these rivers are tributaries or copies of USGS rows.
- Effect on Figure 5: the largest gauged river in the Mississippi drains 49,103 km², and none of the
  3,892 v3 reaches draining > 50,000 km² is covered. The white streaks are the land draining straight
  into the main stems (Mississippi, Missouri, Platte, Kansas, Arkansas, Red, Ohio, Tennessee, ...).
  Coverage of the Mississippi basin is 78.8%.
- The figure is correct for the catalog: the merged polygon is within 1.3% of the summed catchment
  areas. The gaps come from the catalog, not the method.
- Other big US rivers are also uncovered at their main gauges: Columbia (The Dalles), Snake,
  Susquehanna (Harrisburg), Sacramento (Freeport), Yukon. Colorado at Lees Ferry and Rio Grande at
  El Paso are covered only by gauges further downstream (outside the USGS list).
- The old `master_catalog.csv` (original Figure 5) has the same 7,599 USGS rows, the same ceiling, and
  the same 78.8% Mississippi coverage (on v2). The original figure had the same gaps; at its low
  resolution, the thick dark outlines made them look like lines.
- The local copy `../gauge-paper/master_catalog_with_metadata.csv` gives exactly the same gauges per
  river as `out/fig05_river_translation.csv`, so it matches what Figure 5 was built from.

## Other data quality issues
- 3 rows have Vietnamese province names in ISO_A3 instead of `VNM`.

## Decisions
- All gauges are used throughout the paper (no PublicFree filter).
- Figure images have no titles; captions are in LaTeX.
- Gauges are matched to countries by the catalog's `ISO_A3` column
  (see Open questions about where it came from).
- "Countries" means all countries and territories in the World Bank `WB_GAD_ADM0`
  shapefile (244 after merging rows that share an ISO_A3 code).
- Country area is World Bank land area (`AG.LND.TOTL.K2`, most recent year, fetched live).
  Places without a World Bank value use the polygon area from the shapefile in an
  equal-area projection. Note: World Bank land area for Greenland is ice-free land only
  (410,450 km² vs 2.16 million km² total).
- Income groups use the World Bank's official classification (fetched live from the
  World Bank API, current as of 2026), not 2019 GNI with thresholds. Places with no
  classification are shown hatched as "No data" in Figure 3.
  - The API currently returns the **FY2027** classification: effective 1 July 2026, based on
    2025 GNI per capita (current US$, Atlas method). Thresholds:
    Low ≤ 1,175 · Lower middle 1,176–4,635 · Upper middle 4,636–14,375 · High > 14,375.
    Table `tab:gni-categories` has these values typed in by hand.
  - Source: World Bank, "FY27 Updated Country Income Classification for Analytical Purposes",
    https://documents.worldbank.org/en/publication/documents-reports/documentdetail/099063026190549947
  - July 2026 changes: Jordan, Micronesia, Philippines, Sri Lanka, Viet Nam moved up to upper
    middle; Togo moved up to lower middle; none moved down.
  - Places with no World Bank income classification (23 small territories, e.g. Jersey, Niue,
    Tokelau, Vatican City; all have no gauges) are left out of the income-group table
    `tab:income-groups`. They are still counted in Figures 2 and 3 (hatched "No data" in Fig 3).
  - **French overseas departments counted as France (for now)** in `tab:income-groups`:
    Guadeloupe (GLP, 56 gauges), Martinique (MTQ, 50), French Guiana (GUF, 35), Réunion (REU, 18),
    Mayotte (MYT, 9) = 168 gauges. They have their own ISO_A3 codes in the catalog and shapefile,
    but the World Bank API has no data for them (it counts them as part of France). Unconfirmed:
    whether World Bank population / land area for France include them. Revisit if needed.
    Figures 1–5 still treat them as separate places (they have gauges, so this doesn't change Figs 2–3).
  - Population for `tab:income-groups` is World Bank total population (`SP.POP.TOTL`), most
    recent year, fetched live from the API.
  - **The World Bank reclassifies every 1 July.** If the scripts are rerun after 1 July 2027 the
    API will return FY2028 groups, and `tab:gni-categories` (and the text) must be updated to
    the FY2028 thresholds so the table matches the groups used in the figures and tables.
- Köppen climate classes come from Beck et al. (2023), present-day 1991–2020 map at 1 km
  (`koppen_geiger_0p00833333.tif`), looked up at each gauge's coordinates.
  The old Figure 4 used a 2026–2050 A1FI *future projection* shapefile instead.
  Citation: Beck, H.E., T.R. McVicar, N. Vergopolan, A. Berg, N.J. Lutsko, A. Dufour, Z. Zeng,
  X. Jiang, A.I.J.M. van Dijk, D.G. Miralles. High-resolution (1 km) Köppen-Geiger maps for
  1901–2099 based on constrained CMIP6 projections, Scientific Data 10, 724,
  doi:10.1038/s41597-023-02549-6 (2023).
- Figure 5 uses the **RFS / GEOGLOWS v3 hydrography** (switched from v2 on 2026-10-07; faster,
  smaller, and complete where v2 was not).
  - Source: public S3 bucket `river-forecast-system-v3` (us-west-2), folder `hydrography/`,
    published 2026-09-26. Browse at https://v3.s3.riverforecastsystem.com/#hydrography/
  - Local copy (7.8 GB, sizes checked against the bucket): `../gauge-paper/hydrography_v3/`
    with `global/metadata.parquet` (river network), `region=<id>/catchments_<id>.geo.parquet`
    (47 regions, stored in Web Mercator) and `region=<id>/mods/*.json` (edits relative to v2).
  - Everything upstream of a river = rows with `riverIndex` from `riverIndex − upstreamCount`
    to `riverIndex` (`upstreamCount` excludes the river itself). Checked against a full
    network walk for 200 rivers.
  - An area is covered if any gauge is downstream of it. Catchments are merged per region in chunks
    of 25,000 neighbouring catchments (to keep memory down), then the chunk outlines are merged.
    Each chunk uses the fast "coverage" merge (repaired with `make_valid(method='structure')`),
    falling back to the standard merge where catchment edges don't line up exactly (v3 is not
    perfectly clean everywhere). 
  - Gauge river IDs are translated from v2 to v3 first (see "Translating gauge river IDs").
  - A ~1 km simplified copy of the result (`out/fig05_watersheds.parquet`) is what the map is
    drawn from. 
## Paper text and tables to update
Because of the decisions above (all gauges, corrected areas, official income classification):
- `3_analysis.tex` line 6: "data from 135 countries" -> now 131.
- `3_analysis.tex` line 16: "129 countries without any gauge data" -> now 113 countries and territories.
- `3_analysis.tex` line 26: describes using 2019 GNI and names Venezuela, Monaco, and
  Liechtenstein as lacking GNI. Needs rewriting for the official classification.
- ~~Table `tab:gni-categories`~~: DONE (2026-10-07) — replaced with the FY2027 thresholds.
  (Old values 1,035 / 4,085 / 12,615 never matched the code, which used 1,025 / 3,995 / 12,375.)
- Table `tab:income-groups`: recompute with all gauges, official classification, and
  corrected areas (old areas were measured in Web Mercator, which inflates high latitudes).
- `3_analysis.tex` line 65: check the Iceland / Finland / Norway discussion still matches Figure 3.
- Figure 1 caption: says "publicly available gauges"; now all gauges.
- State when the income classifications were retrieved (date and World Bank fiscal year,
  e.g. FY2027). They are fetched live and the World Bank updates them every July;
  between the Feb 2026 CSV and the live API (Oct 2026), Micronesia, Jordan, and
  Sri Lanka moved from lower middle to upper middle income.
- Cite Beck et al. (2023) for the Köppen classes: added to `references.bib` as `beck2023`;
  still needs `\cite{beck2023}` in the text.
- `3_analysis.tex` line 78: "temperate ... despite being the smallest percentage of land area"
  is based on the old notebook, which measured area in degrees (inflating polar to 36%).
  Rechecked with the corrected Figure 4: the claim HOLDS (temperate 50.2% of gauges,
  12.1% of land), but only because Antarctica is included (polar 14.1%). Without Antarctica,
  polar would be the smallest. Text should say Antarctica is included.
- `3_analysis.tex` line 78: "this is the climate with the greatest population of people" has no
  data or citation behind it. Add a citation or reword.
- Figure 4 caption: says "Total number of gauges per Koppen climate category"; figure now shows
  % of gauges vs % of land area per Köppen group (Beck et al. 2023), with gauge counts on the bars.
- Polar now has 71 gauges (old figure: 327, from the 2026–2050 future-climate map).
- Figure 5 is rebuilt from the current catalog, so it shows less coverage than the old figure
  (more gauges are unmatched; see "Gauges not matched to a river"). Text should say how many
  gauges were matched to rivers and that unmatched gauges are excluded.
- `3_analysis.tex` after Figure 5: "The map highlights" is unfinished. Use the coverage %
  printed by `fig05_prepare_watersheds.py` (% of all land and % excluding Antarctica).
- Figure 5: says matched to "RFS streams"; name the hydrography (RFS / GEOGLOWS v3) and cite it.
  Methods should explain that gauges were matched to v2 rivers and translated to v3, and that
  589 gauges were left out (basins not in v3, reaches absorbed into lakes, rivers not in the
  v2 network, a pruned branch).
  Figure 5 will show gaps in the Lake Eyre basin (Australia) and northern Quebec.
- `3_analysis.tex` lines 74–75 (Word comment) and `2_building.tex` lines 69–75: the old
  Figure 4 did NOT use the same Köppen source as the methods section describes. Methods
  text needs to match the Beck et al. (2023) approach.
