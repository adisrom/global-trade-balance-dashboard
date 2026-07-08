# Global Trade Balance Dashboard

Interactive dashboard built on UN Statistical Yearbook (SYB68) trade data:
imports (CIF), exports (FOB), and trade balance for ~216 countries/areas
(1995–2024), plus each country's top-3 trading partners by export/import
share (2015, 2020, 2024).

## Architecture

```
data_raw/          raw UN CSVs (as downloaded)
pipeline.py         pandas ETL -> star schema
data_processed/
  dim_country.csv           -- country dimension (name, ISO mapping, flags)
  fact_trade_balance.csv    -- imports/exports/balance, 1 row per country-year
  fact_trading_partners.csv -- partner shares, 1 row per country-year-partner
app.py               Streamlit app (choropleth + time series + partner charts)
```

This is a deliberately "flat file" star schema: `dim_country` is the
dimension table, `fact_trade_balance` / `fact_trading_partners` are the
fact tables, joined on `country_code`. No database required, but the same
model would drop straight into DuckDB/Snowflake/dbt if you want to extend it.

## Setup (macOS)

```bash
cd trade_dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If you hit an externally-managed-environment error without a venv:
```bash
pip install -r requirements.txt --break-system-packages
```

## Run

```bash
# 1. Rebuild the processed tables from raw data (only needed once, or after editing pipeline.py)
python3 pipeline.py

# 2. Launch the dashboard
streamlit run app.py
```

This opens the dashboard at `http://localhost:8501`.

## What's in the app

- **KPI row** — latest-year world imports/exports/balance.
- **Choropleth map** — trade balance by country for a selected year
  (blue = surplus, red = deficit). Uses Plotly's built-in country-name
  matching; a handful of small territories (e.g. Macao) may not render
  a color if Plotly's base map doesn't include them, but they still show
  up everywhere else in the app.
- **Time series** — pick any countries and compare balance, or imports
  vs. exports, over 1995–2024.
- **Trading partners** — top-3 export/import partners and their % share
  for a selected country/year, from the Major Trading Partners dataset.

## Known data notes (handled in pipeline.py)

- The raw files mix real countries with continent/region aggregates
  (e.g. "Africa", "Sub-Saharan Africa") and a few now-defunct entities
  (Netherlands Antilles, Sudan [former], Serbia and Montenegro [former]).
  These are flagged via `is_aggregate` / `is_historical` in `dim_country`
  rather than silently dropped, so you can decide what to include.
- UN naming doesn't always match Plotly's map naming (e.g. "Russian
  Federation" vs "Russia", "Viet Nam" vs "Vietnam") — resolved via
  `PLOTLY_NAME_MAP` in `pipeline.py`.
- Trade balance years available: 1995, 2005, 2010, 2015, 2022, 2023, 2024
  (not every year — this is what the UN Yearbook publishes).
- Trading partner years available: 2015, 2020, 2024 only.

## Extending this for a resume writeup

- Swap the flat-file star schema for DuckDB or Snowflake + dbt models
  (staging → marts) if you want to show SQL/dbt skills explicitly.
- Add a `dim_year` table and pre-aggregate regional rollups instead of
  excluding them, to show handling of hierarchical dimensions.
- Add YoY growth % and CAGR calculations as derived fact columns.
