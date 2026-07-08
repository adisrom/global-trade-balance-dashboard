"""
Data pipeline for the Global Trade Balance Dashboard.

Reads the two raw UN Statistical Yearbook exports:
  - SYB68_123 ... Total Imports, Exports and Balance of Trade
  - SYB68_330 ... Major Trading Partners

Cleans them and writes out a small star schema (as CSVs, no DB needed):
  data_processed/dim_country.csv          -- one row per country/area
  data_processed/fact_trade_balance.csv   -- imports / exports / balance, one row per country-year
  data_processed/fact_trading_partners.csv-- top-3 partner shares, one row per country-year-partner-direction

Run:
    python3 pipeline.py
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data_raw"
OUT_DIR = Path(__file__).parent / "data_processed"
OUT_DIR.mkdir(exist_ok=True)

# UN M49 region / grouping codes that appear in the country_code column but are
# NOT individual countries (continents, sub-regions, economic groupings, etc).
# Kept separate so the dashboard can filter to actual countries by default.
AGGREGATE_CODES = {
    1, 2, 5, 9, 11, 13, 14, 15, 17, 18, 19, 21, 29, 30, 34, 35, 39, 53, 54, 57,
    61, 142, 143, 145, 150, 151, 154, 155, 158, 202, 419,
}

# Entities that no longer exist in their listed form (pre-split/merger states).
# Kept in the data for historical completeness but excluded from "current
# countries" views since they can't be plotted on a present-day map.
HISTORICAL_CODES = {530, 736, 891}  # Netherlands Antilles, Sudan [former], Serbia & Montenegro [former]

# UN Statistical Yearbook country names -> names Plotly's built-in
# choropleth (locationmode="country names") recognizes. Only names that
# actually differ need an entry.
PLOTLY_NAME_MAP = {
    "Bolivia (Plurin. State of)": "Bolivia",
    "Bahamas (The)": "Bahamas",
    "Brunei Darussalam": "Brunei",
    "China, Hong Kong SAR": "Hong Kong",
    "China, Macao SAR": "Macao",
    "Dem. Rep. of the Congo": "Democratic Republic of the Congo",
    "Côte dIvoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "Dem. People's Rep. Korea": "North Korea",
    "Republic of Korea": "South Korea",
    "Iran (Islamic Republic of)": "Iran",
    "Lao People's Dem. Rep.": "Laos",
    "Republic of Moldova": "Moldova",
    "Netherlands (Kingdom of the)": "Netherlands",
    "Russian Federation": "Russia",
    "Syrian Arab Republic": "Syria",
    "United Rep. of Tanzania": "Tanzania",
    "United States of America": "United States",
    "Venezuela (Boliv. Rep. of)": "Venezuela",
    "Viet Nam": "Vietnam",
    "Türkiye": "Turkey",
    "Cabo Verde": "Cape Verde",
    "State of Palestine": "Palestine",
    "Saint Vincent & Grenadines": "Saint Vincent and the Grenadines",
    "Congo": "Republic of Congo",
    "Micronesia (Fed. States of)": "Micronesia",
    "United Kingdom": "United Kingdom",
}


def load_trade_balance() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "trade_balance_raw.csv", skiprows=1, encoding="latin1")
    df.columns = [
        "country_code", "country_name", "year", "series",
        "system_of_trade", "system_footnote", "value", "footnotes", "source",
    ]
    df["value"] = (
        df["value"].astype(str).str.replace(",", "", regex=False).astype(float)
    )

    series_map = {
        "Imports CIF (millions of US dollars)": "imports_usd_m",
        "Exports FOB (millions of US dollars)": "exports_usd_m",
        "Balance imports/exports (millions of US dollars)": "balance_usd_m",
    }
    df["metric"] = df["series"].map(series_map)

    wide = df.pivot_table(
        index=["country_code", "country_name", "year"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None

    for col in ["imports_usd_m", "exports_usd_m", "balance_usd_m"]:
        if col not in wide.columns:
            wide[col] = pd.NA

    # Recompute balance where missing but both imports/exports are present
    mask = wide["balance_usd_m"].isna() & wide["imports_usd_m"].notna() & wide["exports_usd_m"].notna()
    wide.loc[mask, "balance_usd_m"] = wide.loc[mask, "exports_usd_m"] - wide.loc[mask, "imports_usd_m"]

    return wide.sort_values(["country_name", "year"])


def load_trading_partners() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "trading_partners_raw.csv", skiprows=1, encoding="latin1")
    df.columns = [
        "country_code", "country_name", "year", "series",
        "partner_name", "partner_footnote", "value", "footnotes", "source",
    ]
    df["value"] = df["value"].astype(str).str.replace(",", "", regex=False).astype(float)

    # series looks like "Major trading partner 2 (% of imports)"
    df["rank"] = df["series"].str.extract(r"partner (\d)").astype(int)
    df["direction"] = df["series"].str.extract(r"% of (imports|exports)")

    return df[[
        "country_code", "country_name", "year", "direction", "rank",
        "partner_name", "value",
    ]].rename(columns={"value": "pct_share"}).sort_values(
        ["country_name", "year", "direction", "rank"]
    )


def build_dim_country(trade_balance: pd.DataFrame, trading_partners: pd.DataFrame) -> pd.DataFrame:
    names = pd.concat([
        trade_balance[["country_code", "country_name"]],
        trading_partners[["country_code", "country_name"]],
    ]).drop_duplicates(subset="country_code").reset_index(drop=True)

    names["is_aggregate"] = names["country_code"].isin(AGGREGATE_CODES)
    names["is_historical"] = names["country_code"].isin(HISTORICAL_CODES)
    names["plotly_name"] = names["country_name"].map(PLOTLY_NAME_MAP).fillna(names["country_name"])
    names["is_mappable"] = ~(names["is_aggregate"] | names["is_historical"])

    return names.sort_values("country_name")


def main():
    trade_balance = load_trade_balance()
    trading_partners = load_trading_partners()
    dim_country = build_dim_country(trade_balance, trading_partners)

    trade_balance.to_csv(OUT_DIR / "fact_trade_balance.csv", index=False)
    trading_partners.to_csv(OUT_DIR / "fact_trading_partners.csv", index=False)
    dim_country.to_csv(OUT_DIR / "dim_country.csv", index=False)

    print(f"dim_country:            {len(dim_country):>5} rows")
    print(f"fact_trade_balance:     {len(trade_balance):>5} rows")
    print(f"fact_trading_partners:  {len(trading_partners):>5} rows")
    print(f"\nReal countries (mappable): {dim_country['is_mappable'].sum()}")
    print(f"Aggregates/regions:        {dim_country['is_aggregate'].sum()}")
    print(f"Historical entities:       {dim_country['is_historical'].sum()}")


if __name__ == "__main__":
    main()
