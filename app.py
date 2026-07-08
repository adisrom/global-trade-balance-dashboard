"""
Global Trade Balance Dashboard
Data: UN Statistical Yearbook (SYB68) - Total Imports/Exports/Balance of Trade
      and Major Trading Partners, UN COMTRADE.

Run:
    pip install -r requirements.txt --break-system-packages   # if needed
    streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_processed"

st.set_page_config(
    page_title="Global Trade Balance Dashboard",
    page_icon="🌍",
    layout="wide",
)


@st.cache_data
def load_data():
    dim_country = pd.read_csv(DATA_DIR / "dim_country.csv")
    fact_trade = pd.read_csv(DATA_DIR / "fact_trade_balance.csv")
    fact_partners = pd.read_csv(DATA_DIR / "fact_trading_partners.csv")
    return dim_country, fact_trade, fact_partners


dim_country, fact_trade, fact_partners = load_data()

countries_only = dim_country[dim_country["is_mappable"]].sort_values("country_name")
country_names = countries_only["country_name"].tolist()

# ---------------------------------------------------------------- Sidebar --
st.sidebar.title("Filters")

years_available = sorted(fact_trade["year"].unique())
map_year = st.sidebar.selectbox(
    "Map year", years_available, index=len(years_available) - 1
)

default_countries = [
    c for c in [
        "United States of America", "China", "Germany", "Japan",
        "India", "United Kingdom",
    ] if c in country_names
]
selected_countries = st.sidebar.multiselect(
    "Countries to compare (time series)",
    options=country_names,
    default=default_countries,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Source: UN Statistical Yearbook (SYB68), UN COMTRADE, "
    "last accessed June 2025. Values in millions of current US dollars."
)

# ------------------------------------------------------------------ Title --
st.title("🌍 Global Trade Balance Dashboard")
st.caption(
    "Imports (CIF), exports (FOB) and trade balance by country, "
    f"{min(years_available)}–{max(years_available)}"
)

# --------------------------------------------------------------- KPI row --
world_row = fact_trade[fact_trade["country_code"] == 1]
latest_year = world_row["year"].max()
latest_world = world_row[world_row["year"] == latest_year].iloc[0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Latest data year", int(latest_year))
k2.metric("World exports ($M)", f"{latest_world['exports_usd_m']:,.0f}")
k3.metric("World imports ($M)", f"{latest_world['imports_usd_m']:,.0f}")
k4.metric("World balance ($M)", f"{latest_world['balance_usd_m']:,.0f}")

st.markdown("---")

# ------------------------------------------------------- Choropleth map --
st.subheader(f"Trade balance by country — {map_year}")

map_df = fact_trade[fact_trade["year"] == map_year].merge(
    countries_only[["country_code", "plotly_name"]], on="country_code", how="inner"
)

fig_map = px.choropleth(
    map_df,
    locations="plotly_name",
    locationmode="country names",
    color="balance_usd_m",
    color_continuous_scale="RdBu",
    color_continuous_midpoint=0,
    hover_name="country_name",
    hover_data={
        "plotly_name": False,
        "exports_usd_m": ":,.0f",
        "imports_usd_m": ":,.0f",
        "balance_usd_m": ":,.0f",
    },
    labels={
        "balance_usd_m": "Balance ($M)",
        "exports_usd_m": "Exports ($M)",
        "imports_usd_m": "Imports ($M)",
    },
)
fig_map.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    coloraxis_colorbar=dict(title="Balance ($M)"),
    geo=dict(showframe=False, showcoastlines=False, projection_type="natural earth"),
)
st.plotly_chart(fig_map, use_container_width=True)
st.caption(
    "Blue = trade surplus (exports > imports). Red = trade deficit. "
    "Grey = no data or territory not shown on the base map for that year."
)

st.markdown("---")

# -------------------------------------------------------- Time series ---
st.subheader("Imports vs. exports over time")

if not selected_countries:
    st.info("Pick one or more countries in the sidebar to see their trend lines.")
else:
    ts_df = fact_trade[fact_trade["country_name"].isin(selected_countries)]

    metric_choice = st.radio(
        "Metric", ["Balance", "Imports vs Exports"], horizontal=True
    )

    if metric_choice == "Balance":
        fig_ts = px.line(
            ts_df.sort_values("year"),
            x="year",
            y="balance_usd_m",
            color="country_name",
            markers=True,
            labels={"balance_usd_m": "Trade balance ($M)", "year": "Year", "country_name": "Country"},
        )
        fig_ts.add_hline(y=0, line_dash="dash", line_color="gray")
    else:
        long_df = ts_df.melt(
            id_vars=["country_name", "year"],
            value_vars=["imports_usd_m", "exports_usd_m"],
            var_name="flow",
            value_name="value_usd_m",
        )
        long_df["flow"] = long_df["flow"].map(
            {"imports_usd_m": "Imports", "exports_usd_m": "Exports"}
        )
        fig_ts = px.line(
            long_df.sort_values("year"),
            x="year",
            y="value_usd_m",
            color="country_name",
            line_dash="flow",
            markers=True,
            labels={"value_usd_m": "Value ($M)", "year": "Year", "country_name": "Country"},
        )

    fig_ts.update_layout(legend_title_text="")
    st.plotly_chart(fig_ts, use_container_width=True)

st.markdown("---")

# ------------------------------------------------------ Trading partners --
st.subheader("Top trading partners")

partner_countries = sorted(fact_partners["country_name"].unique())
default_partner_country = "United States of America" if "United States of America" in partner_countries else partner_countries[0]

pc1, pc2 = st.columns([2, 1])
with pc1:
    partner_country = st.selectbox("Country", partner_countries, index=partner_countries.index(default_partner_country))
with pc2:
    partner_year = st.selectbox(
        "Year", sorted(fact_partners["year"].unique(), reverse=True), key="partner_year"
    )

pp_df = fact_partners[
    (fact_partners["country_name"] == partner_country)
    & (fact_partners["year"] == partner_year)
].sort_values(["direction", "rank"])

pcol1, pcol2 = st.columns(2)
for direction, col in [("exports", pcol1), ("imports", pcol2)]:
    subset = pp_df[pp_df["direction"] == direction]
    with col:
        st.markdown(f"**By % of {direction}**")
        if subset.empty:
            st.caption("No data")
        else:
            fig_bar = go.Figure(
                go.Bar(
                    x=subset["pct_share"],
                    y=subset["partner_name"],
                    orientation="h",
                    text=subset["pct_share"].map(lambda v: f"{v:.1f}%"),
                    textposition="auto",
                )
            )
            fig_bar.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=220,
                xaxis_title="% share",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")
st.caption(
    "Built with Streamlit + Plotly. Data cleaned from raw UN Statistical "
    "Yearbook CSVs via pipeline.py into a small star schema "
    "(dim_country, fact_trade_balance, fact_trading_partners)."
)
