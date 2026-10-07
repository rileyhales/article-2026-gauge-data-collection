# Data notes

Issues found in `master_catalog_with_metadata.csv` (37,528 rows, checked 2026-10-06).

## Missing coordinates
- 1,760 gauges have no latitude/longitude, so they cannot appear on maps.
  Mexico 1,565 · India 170 · Bhutan 12 · Afghanistan 4 · UK 4 · China 2 · Nepal, Russia, USA 1 each
- All of them still have an ISO_A3 code, so they are counted in per-country analyses.

## Possible duplicates
- No identical rows; `hash` is unique.
- `gauge_id` is NOT unique: 473 IDs are reused by different gauges in different countries.
- 367 extra rows share the same coordinates and name with another row (mostly USA).
  Examples: Rwanda "Nyundo" (196501, 196501_1, 196501_2); Togo "Koumongou" (two copies).

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

## Other data quality issues
- 3 rows have Vietnamese province names in ISO_A3 instead of `VNM`.
- Some USGS rows have `name` and `excel_Station_name` pointing to different rivers
  (e.g. gauge_id 1112500: "Blackwater River near Webster - NH" vs "Blackstone River at Woonsocket - RI").

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
- Köppen climate classes come from Beck et al. (2023), present-day 1991–2020 map at 1 km
  (`koppen_geiger_0p00833333.tif`), looked up at each gauge's coordinates.
  The old Figure 4 used a 2026–2050 A1FI *future projection* shapefile instead.
  Citation: Beck, H.E., T.R. McVicar, N. Vergopolan, A. Berg, N.J. Lutsko, A. Dufour, Z. Zeng,
  X. Jiang, A.I.J.M. van Dijk, D.G. Miralles. High-resolution (1 km) Köppen-Geiger maps for
  1901–2099 based on constrained CMIP6 projections, Scientific Data 10, 724,
  doi:10.1038/s41597-023-02549-6 (2023).

## Paper text and tables to update
Because of the decisions above (all gauges, corrected areas, official income classification):
- `3_analysis.tex` line 6: "data from 135 countries" -> now 131.
- `3_analysis.tex` line 16: "129 countries without any gauge data" -> now 113 countries and territories.
- `3_analysis.tex` line 26: describes using 2019 GNI and names Venezuela, Monaco, and
  Liechtenstein as lacking GNI. Needs rewriting for the official classification.
- Table `tab:gni-categories`: GNI thresholds no longer used directly. Remove, or replace
  with the thresholds behind the official classification. (Its numbers also never matched
  the code, which used 1,025 / 3,995 / 12,375.)
- Table `tab:income-groups`: recompute with all gauges, official classification, and
  corrected areas (old areas were measured in Web Mercator, which inflates high latitudes).
- `3_analysis.tex` line 65: check the Iceland / Finland / Norway discussion still matches Figure 3.
- Figure 1 caption: says "publicly available gauges"; now all gauges.
- State when the income classifications were retrieved (date and World Bank fiscal year,
  e.g. FY2027). They are fetched live and the World Bank updates them every July;
  between the Feb 2026 CSV and the live API (Oct 2026), Micronesia, Jordan, and
  Sri Lanka moved from lower middle to upper middle income.
- Cite Beck et al. (2023) for the Köppen classes (not yet in `references.bib`).
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
- `3_analysis.tex` lines 74–75 (Word comment) and `2_building.tex` lines 69–75: the old
  Figure 4 did NOT use the same Köppen source as the methods section describes. Methods
  text needs to match the Beck et al. (2023) approach.
