"""Table: gauges, people, and land area per gauge by World Bank income group (excluding the USA).

Reads:  <GAUGE_DATA_DIR>/master_catalog_with_metadata.csv
        <GAUGE_DATA_DIR>/country_shapefile/WB_GAD_ADM0.shp
        World Bank API -- needs internet:
          official income classification (current)
          total population (SP.POP.TOTL), most recent year
          land area (AG.LND.TOTL.K2), most recent year
Writes: latex/tables/tab_income_groups.tex   (the tabular only; caption and label stay in the paper)

GAUGE_DATA_DIR defaults to the repo's gauge_tables/ folder.

Gauges are matched to countries by the catalog's ISO_A3 column. Countries and territories come
from the World Bank shapefile; those without an income classification are left out. French
overseas departments (GLP, MTQ, GUF, REU, MYT) are counted as France, as the World Bank does. Per-gauge
values are group totals divided by the group's total gauges, so countries with no gauges add
to the people and area but not to the gauges.
"""
import json
import os
import urllib.request
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GAUGE_DATA_DIR", REPO_DIR / "gauge_tables"))
OUTPUT = REPO_DIR / "latex" / "tables" / "tab_income_groups.tex"

INCOME_GROUPS = ['Low income', 'Lower middle income', 'Upper middle income', 'High income']
EXCLUDED = ['USA']  # its gauge count dominates the high-income group
# French overseas departments: own ISO codes in the catalog and shapefile, but the World Bank
# has no data for them and counts them as part of France
PART_OF = {'GLP': 'FRA', 'MTQ': 'FRA', 'GUF': 'FRA', 'REU': 'FRA', 'MYT': 'FRA'}
CLASSIFICATION_YEAR = 'FY2027'
NEXT_RECLASSIFICATION = date(2027, 7, 1)


def fetch_wb_income_groups():
    """Current World Bank income group for every country code."""
    url = "https://api.worldbank.org/v2/country?format=json&per_page=500"
    data = json.loads(urllib.request.urlopen(url).read())
    return {item['id']: item['incomeLevel']['value'] for item in data[1]}


def fetch_wb_indicator(indicator):
    """Most recent value of a World Bank indicator for every country code, plus the years used."""
    url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
           "?format=json&per_page=20000&mrv=1")
    data = json.loads(urllib.request.urlopen(url).read())
    rows = [item for item in data[1] if item['value'] is not None]
    values = {item['countryiso3code']: item['value'] for item in rows}
    years = sorted({item['date'] for item in rows})
    return values, years


def equal_area_km2(geom):
    """Polygon area in km², split at 0° so polygons crossing 180° measure correctly."""
    halves = gpd.GeoSeries(
        [geom.intersection(box(-180, -90, 0, 90)), geom.intersection(box(0, -90, 180, 90))],
        crs="EPSG:4326",
    )
    return halves.to_crs("ESRI:54034").area.sum() / 1e6  # World Cylindrical Equal Area


if date.today() >= NEXT_RECLASSIFICATION:
    print(f"WARNING: the World Bank reclassifies every 1 July. The API has probably moved past "
          f"{CLASSIFICATION_YEAR}; update tab:gni-categories in the paper to match.\n")

gauges = pd.read_csv(DATA_DIR / "master_catalog_with_metadata.csv", low_memory=False)
countries = gpd.read_file(DATA_DIR / "country_shapefile" / "WB_GAD_ADM0.shp")

# --- One row per country/territory (some are split across several polygons) ---
countries = countries.dissolve(by='ISO_A3', as_index=False)

# --- Count French overseas departments as France ---
countries = countries[~countries['ISO_A3'].isin(PART_OF)]
gauge_country = gauges['ISO_A3'].replace(PART_OF)

# --- Gauges per country ---
countries['gauges'] = countries['ISO_A3'].map(gauge_country.value_counts()).fillna(0).astype(int)

# --- Income group, population, and area from the World Bank ---
countries['income_group'] = countries['ISO_A3'].map(fetch_wb_income_groups())
population, population_years = fetch_wb_indicator('SP.POP.TOTL')
land_area, area_years = fetch_wb_indicator('AG.LND.TOTL.K2')
countries['population'] = countries['ISO_A3'].map(population)
countries['area_km2'] = countries['ISO_A3'].map(land_area)
from_shapefile = countries['area_km2'].isna()
countries.loc[from_shapefile, 'area_km2'] = (
    countries.loc[from_shapefile, 'geometry'].apply(equal_area_km2)
)

classified = countries[countries['income_group'].isin(INCOME_GROUPS)]
unclassified = countries[~countries['income_group'].isin(INCOME_GROUPS)]
included = classified[~classified['ISO_A3'].isin(EXCLUDED)]

print(f"Income classification retrieved: {date.today().isoformat()} ({CLASSIFICATION_YEAR})")
print(f"Population year(s): {', '.join(population_years)}; land area year(s): {', '.join(area_years)}")
print(f"Countries and territories: {len(countries)} "
      f"(after counting {', '.join(PART_OF)} as France: "
      f"{gauges['ISO_A3'].isin(PART_OF).sum()} gauges)")
print(f"  Left out, no income classification: {len(unclassified)} "
      f"({unclassified['gauges'].sum()} gauges)")
print(f"  Left out, excluded: {', '.join(EXCLUDED)} "
      f"({classified.loc[classified['ISO_A3'].isin(EXCLUDED), 'gauges'].sum():,} gauges)")
print(f"  Included: {len(included)} ({included['gauges'].sum():,} gauges)")
print(f"  Included but missing population: "
      f"{', '.join(sorted(included.loc[included['population'].isna(), 'NAM_0'])) or 'none'}")

# --- Summary by income group ---
grouped = included.groupby('income_group')
summary = pd.DataFrame({
    'avg_gauges_per_country': grouped['gauges'].mean(),
    'people_per_gauge_1000': grouped['population'].sum() / grouped['gauges'].sum() / 1000,
    'area_per_gauge_1000km2': grouped['area_km2'].sum() / grouped['gauges'].sum() / 1000,
    'countries_with_gauges': grouped['gauges'].apply(lambda g: (g > 0).sum()),
    'countries': grouped.size(),
}).reindex(INCOME_GROUPS)

print()
print(summary.round(2).to_string())

# --- LaTeX tabular ---
lines = [
    r"\begin{tabular}{@{}lC{0.14\textwidth}C{0.14\textwidth}C{0.14\textwidth}C{0.14\textwidth}@{}}",
    r"\toprule",
    r"Income Group & Average gauges per country & People per gauge (thousands) & "
    r"Land area per gauge (1000 km\textsuperscript{2}) & Countries with gauges \\",
    r"\midrule",
]
for group, row in summary.iterrows():
    lines.append(
        f"{group.title()} & {row['avg_gauges_per_country']:,.2f} & "
        f"{row['people_per_gauge_1000']:,.2f} & {row['area_per_gauge_1000km2']:,.2f} & "
        f"{int(row['countries_with_gauges'])} \\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    "% Generated by figures_src/tab_income_groups.py -- do not edit by hand.\n"
    + "\n".join(lines) + "\n"
)
print(f"Saved {OUTPUT}")
