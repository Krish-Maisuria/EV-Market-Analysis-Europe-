import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import pydeck as pdk
from pathlib import Path

st.set_page_config(page_title="EV Market Analysis (Europe)", layout="wide")

# ---------------------------
# Settings
# ---------------------------
# Europe bounding box (approximate; used as a continent proxy)
EUROPE_LAT_MIN, EUROPE_LAT_MAX = 34.0, 72.0
EUROPE_LON_MIN, EUROPE_LON_MAX = -25.0, 45.0

# Default FX: USD -> EUR (let user override in sidebar)
DEFAULT_USD_TO_EUR = 0.90

# ---------------------------
# Helpers
# ---------------------------
def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

def resolve_paths() -> tuple[Path, Path]:
    root = Path(".").resolve()
    data_dir = root / "data"
    ev_path = data_dir / "EV_cars.csv"
    stations_path = data_dir / "detailed_ev_charging_stations.csv"

    # fallback: same directory
    if not ev_path.exists():
        ev_path = root / "EV_cars.csv"
    if not stations_path.exists():
        stations_path = root / "detailed_ev_charging_stations.csv"

    return ev_path, stations_path

def clean_ev(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize common column names
    rename_map = {
        "Price.DE.": "Price_EUR",
        "acceleration..0.100.": "Accel_0_100_s",
        "Top_speed": "Top_speed_kmh",
        "Fast_charge": "FastCharge_kmh",
        "Car_name": "Car",
        "Car_name_link": "Link",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Numeric conversions (best-effort)
    for col in ["Battery", "Efficiency", "FastCharge_kmh", "Price_EUR", "Range", "Top_speed_kmh", "Accel_0_100_s"]:
        if col in df.columns:
            df[col] = _to_num(df[col])

    # Brand parsing
    if "Car" in df.columns:
        df["Brand"] = df["Car"].astype(str).str.strip().str.split().str[0]
    else:
        df["Brand"] = "Unknown"

    df = df.drop_duplicates()

    # Filter invalid values
    for col in ["Price_EUR", "Battery", "Range"]:
        if col in df.columns:
            df = df[df[col].isna() | (df[col] > 0)]

    # Derived metrics
    # Efficiency is typically Wh/km -> kWh/100km
    if "Efficiency" in df.columns:
        df["kWh_per_100km"] = (df["Efficiency"] * 100.0) / 1000.0
    else:
        df["kWh_per_100km"] = np.nan

    if "Range" in df.columns and "Battery" in df.columns:
        df["Range_per_kWh_km"] = df["Range"] / df["Battery"]
        df["Price_per_kWh_EUR"] = df["Price_EUR"] / df["Battery"] if "Price_EUR" in df.columns else np.nan
        df["Price_per_kmRange_EUR"] = df["Price_EUR"] / df["Range"] if "Price_EUR" in df.columns else np.nan
    else:
        df["Range_per_kWh_km"] = np.nan
        df["Price_per_kWh_EUR"] = np.nan
        df["Price_per_kmRange_EUR"] = np.nan

    return df

def clean_stations(df: pd.DataFrame, usd_to_eur: float) -> pd.DataFrame:
    df = df.copy()

    rename_map = {
        "Station ID": "station_id",
        "Latitude": "lat",
        "Longitude": "lon",
        "Address": "address",
        "Charger Type": "charger_type",
        "Cost (USD/kWh)": "cost_usd_per_kwh",
        "Availability": "availability",
        "Distance to City (km)": "distance_to_city_km",
        "Usage Stats (avg users/day)": "avg_users_per_day",
        "Station Operator": "operator",
        "Charging Capacity (kW)": "capacity_kw",
        "Connector Types": "connector_types",
        "Installation Year": "install_year",
        "Renewable Energy Source": "renewable_source",
        "Reviews (Rating)": "rating",
        "Parking Spots": "parking_spots",
        "Maintenance Frequency": "maintenance_freq",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    for col in ["lat", "lon", "cost_usd_per_kwh", "distance_to_city_km", "avg_users_per_day",
                "capacity_kw", "install_year", "rating", "parking_spots"]:
        if col in df.columns:
            df[col] = _to_num(df[col])

    # Basic clean + validate coords
    df = df.drop_duplicates()
    df = df.dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(-90, 90, inclusive="both") & df["lon"].between(-180, 180, inclusive="both")]

    # ✅ Europe-only filter (continent proxy)
    df = df[
        df["lat"].between(EUROPE_LAT_MIN, EUROPE_LAT_MAX, inclusive="both")
        & df["lon"].between(EUROPE_LON_MIN, EUROPE_LON_MAX, inclusive="both")
    ]

    if "address" in df.columns:
        parts = df["address"].astype(str).str.split(",")
        df["city"] = parts.str[-1].str.strip()

    if "charger_type" in df.columns:
        df["is_dc_fast"] = df["charger_type"].astype(str).str.contains("DC", case=False, na=False)

    # ✅ Convert USD/kWh -> EUR/kWh (for European-unit consistency)
    if "cost_usd_per_kwh" in df.columns:
        df["cost_eur_per_kwh"] = df["cost_usd_per_kwh"] * float(usd_to_eur)
    else:
        df["cost_eur_per_kwh"] = np.nan

    return df

@st.cache_data(show_spinner=False)
def load_and_clean(ev_path: str, stations_path: str, usd_to_eur: float):
    ev_raw = pd.read_csv(ev_path)
    stations_raw = pd.read_csv(stations_path)
    ev = clean_ev(ev_raw)
    stations = clean_stations(stations_raw, usd_to_eur=usd_to_eur)
    return ev, stations

# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.title("Filters & Settings")
usd_to_eur = st.sidebar.number_input("USD → EUR exchange rate", min_value=0.50, max_value=1.50, value=float(DEFAULT_USD_TO_EUR), step=0.01)
st.sidebar.caption("Station prices are converted to EUR/kWh using this rate.")

ev_path, stations_path = resolve_paths()

# ---------------------------
# Load
# ---------------------------
try:
    ev, stations = load_and_clean(str(ev_path), str(stations_path), usd_to_eur=usd_to_eur)
except Exception as e:
    st.error("Could not load data. Check your file paths and CSV names.")
    st.exception(e)
    st.stop()

st.title("⚡ EV Market Analysis (Europe) — Dashboard")
st.caption("EV models priced in EUR; charging stations filtered to Europe by lat/lon bounding box and converted to EUR/kWh.")

# ---------------------------
# EV filters
# ---------------------------
ev_f = ev.copy()

brand_opts = sorted([b for b in ev_f["Brand"].dropna().unique()])
brands = st.sidebar.multiselect("EV Brands", options=brand_opts, default=brand_opts[: min(8, len(brand_opts))])

if brands:
    ev_f = ev_f[ev_f["Brand"].isin(brands)]

# Price and range sliders
if "Price_EUR" in ev_f.columns:
    pmin, pmax = ev_f["Price_EUR"].dropna().min(), ev_f["Price_EUR"].dropna().max()
    if np.isfinite(pmin) and np.isfinite(pmax) and pmin < pmax:
        price_range = st.sidebar.slider("Price (EUR)", float(pmin), float(pmax), (float(pmin), float(pmax)))
        ev_f = ev_f[ev_f["Price_EUR"].between(price_range[0], price_range[1], inclusive="both")]

if "Range" in ev_f.columns:
    rmin, rmax = ev_f["Range"].dropna().min(), ev_f["Range"].dropna().max()
    if np.isfinite(rmin) and np.isfinite(rmax) and rmin < rmax:
        range_range = st.sidebar.slider("Range (km)", float(rmin), float(rmax), (float(rmin), float(rmax)))
        ev_f = ev_f[ev_f["Range"].between(range_range[0], range_range[1], inclusive="both")]

# ---------------------------
# Station filters
# ---------------------------
st_f = stations.copy()
charger_types = sorted([c for c in st_f.get("charger_type", pd.Series(dtype=str)).dropna().unique()])
selected_types = st.sidebar.multiselect("Charger types (Europe only)", options=charger_types, default=charger_types)

if selected_types and "charger_type" in st_f.columns:
    st_f = st_f[st_f["charger_type"].isin(selected_types)]

# ---------------------------
# KPI Row
# ---------------------------
k1, k2, k3, k4 = st.columns(4)

def safe_median(df, col):
    if col in df.columns:
        v = df[col].dropna()
        if len(v) > 0:
            return float(v.median())
    return np.nan

k1.metric("EV models (filtered)", f"{len(ev_f):,}")
med_price = safe_median(ev_f, "Price_EUR")
k2.metric("Median EV price (EUR)", f"{med_price:,.0f}" if np.isfinite(med_price) else "—")
med_range = safe_median(ev_f, "Range")
k3.metric("Median range (km)", f"{med_range:,.0f}" if np.isfinite(med_range) else "—")
med_station_cost = safe_median(st_f, "cost_eur_per_kwh")
k4.metric("Median station cost (EUR/kWh)", f"{med_station_cost:,.2f}" if np.isfinite(med_station_cost) else "—")

# ---------------------------
# Layout: EV charts
# ---------------------------
left, right = st.columns([1.2, 1])

with left:
    st.subheader("EV Price vs Range (Europe-priced EV dataset)")
    scatter_df = ev_f.dropna(subset=["Range", "Price_EUR"])
    fig = px.scatter(
        scatter_df,
        x="Range",
        y="Price_EUR",
        color="Brand",
        size="Battery" if "Battery" in scatter_df.columns else None,
        hover_data=["Car", "Battery", "Efficiency", "FastCharge_kmh", "Range_per_kWh_km", "Price_per_kmRange_EUR"],
        labels={"Range": "Range (km)", "Price_EUR": "Price (EUR)", "Battery": "Battery (kWh)"},
        title="Price vs Range"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Distributions")
    c1, c2 = st.columns(2)
    with c1:
        if "Price_EUR" in ev_f.columns:
            st.plotly_chart(px.histogram(ev_f, x="Price_EUR", nbins=35, title="EV Prices (EUR)"), use_container_width=True)
    with c2:
        if "Range" in ev_f.columns:
            st.plotly_chart(px.histogram(ev_f, x="Range", nbins=35, title="EV Ranges (km)"), use_container_width=True)

with right:
    st.subheader("Brand Value (lower €/km is better)")
    if {"Brand", "Price_per_kmRange_EUR"}.issubset(ev_f.columns):
        brand_summary = (ev_f.groupby("Brand", as_index=False)
            .agg(
                Models=("Car", "count"),
                Avg_EUR_per_kmRange=("Price_per_kmRange_EUR", "mean"),
                Avg_km_per_kWh=("Range_per_kWh_km", "mean"),
                AvgPrice_EUR=("Price_EUR", "mean"),
                AvgRange_km=("Range", "mean"),
            )
            .dropna(subset=["Avg_EUR_per_kmRange"])
            .sort_values("Avg_EUR_per_kmRange", ascending=True)
        )
        figv = px.bar(
            brand_summary.head(15),
            x="Brand",
            y="Avg_EUR_per_kmRange",
            hover_data=["Models", "Avg_km_per_kWh", "AvgPrice_EUR", "AvgRange_km"],
            labels={"Avg_EUR_per_kmRange": "Avg €/km of range"},
            title="Top 15 by Value (€/km)"
        )
        st.plotly_chart(figv, use_container_width=True)
    else:
        st.info("Brand value chart requires Brand + Price_per_kmRange_EUR columns.")

# ---------------------------
# Station charts + Map
# ---------------------------
st.divider()
st.subheader("Charging Stations (Europe only)")

c1, c2 = st.columns([1, 1.2])

with c1:
    if {"charger_type", "cost_eur_per_kwh"}.issubset(st_f.columns):
        fig_cost = px.box(
            st_f.dropna(subset=["cost_eur_per_kwh", "charger_type"]),
            x="charger_type",
            y="cost_eur_per_kwh",
            points="outliers",
            title="Charging Cost by Charger Type (EUR/kWh)",
            labels={"charger_type": "Charger type", "cost_eur_per_kwh": "EUR/kWh"}
        )
        st.plotly_chart(fig_cost, use_container_width=True)

    if {"install_year"}.issubset(st_f.columns) and st_f["install_year"].notna().any():
        installs = (st_f.dropna(subset=["install_year"])
            .groupby("install_year", as_index=False)
            .size()
            .rename(columns={"size": "stations_installed"})
            .sort_values("install_year")
        )
        st.plotly_chart(
            px.line(installs, x="install_year", y="stations_installed", markers=True, title="Stations Installed per Year"),
            use_container_width=True
        )

with c2:
    # Map uses lat/lon + capacity as size (if present)
    map_df = st_f.dropna(subset=["lat", "lon"]).copy()
    if len(map_df) == 0:
        st.info("No stations available after filters.")
    else:
        # Size scaling (safe): create a *column* so pydeck can serialize it
        if "capacity_kw" in map_df.columns and map_df["capacity_kw"].notna().any():
            cap = map_df["capacity_kw"].fillna(map_df["capacity_kw"].median())
            map_df["radius"] = (np.clip(cap, 10, 350) * 20).astype(float)
        else:
            map_df["radius"] = 2000.0

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[lon, lat]',
            get_radius="radius",
            pickable=True,
            auto_highlight=True,
        )

        view_state = pdk.ViewState(
            latitude=float(map_df["lat"].mean()),
            longitude=float(map_df["lon"].mean()),
            zoom=3.5,
            pitch=0,
        )

        tooltip = {
            "html": "<b>Type:</b> {charger_type}<br/>"
                    "<b>EUR/kWh:</b> {cost_eur_per_kwh}<br/>"
                    "<b>kW:</b> {capacity_kw}<br/>"
                    "<b>Users/day:</b> {avg_users_per_day}",
            "style": {"backgroundColor": "white", "color": "black"}
        }

        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip), use_container_width=True)

# ---------------------------
# Combined insight (EUR)
# ---------------------------
st.divider()
st.subheader("Combined Insight: Estimated Energy Cost per 100km (EUR)")

median_cost_eur = safe_median(st_f, "cost_eur_per_kwh")
combo = ev_f.copy()
combo["EnergyCost_per_100km_EUR"] = combo["kWh_per_100km"] * float(median_cost_eur) if np.isfinite(median_cost_eur) else np.nan

c1, c2 = st.columns(2)

with c1:
    plot_df = combo.dropna(subset=["Price_EUR", "EnergyCost_per_100km_EUR"])
    if len(plot_df) > 0:
        st.plotly_chart(
            px.scatter(
                plot_df,
                x="Price_EUR",
                y="EnergyCost_per_100km_EUR",
                color="Brand",
                hover_data=["Car", "Range", "Battery", "Efficiency", "kWh_per_100km"],
                labels={"Price_EUR": "Price (EUR)", "EnergyCost_per_100km_EUR": "EUR per 100km"},
                title="Price vs Estimated Energy Cost (EUR/100km)"
            ),
            use_container_width=True
        )
    else:
        st.info("Not enough data to plot combined cost (check if station cost values exist).")

with c2:
    if "EnergyCost_per_100km_EUR" in combo.columns:
        brand_energy = (combo.groupby("Brand", as_index=False)
            .agg(
                Models=("Car", "count"),
                AvgEnergyCost_EUR_100km=("EnergyCost_per_100km_EUR", "mean"),
                AvgkWh_100km=("kWh_per_100km", "mean"),
                AvgPrice_EUR=("Price_EUR", "mean"),
            )
            .dropna(subset=["AvgEnergyCost_EUR_100km"])
            .sort_values("AvgEnergyCost_EUR_100km", ascending=True)
        )
        if len(brand_energy) > 0:
            st.plotly_chart(
                px.bar(
                    brand_energy.head(15),
                    x="Brand",
                    y="AvgEnergyCost_EUR_100km",
                    hover_data=["Models", "AvgkWh_100km", "AvgPrice_EUR"],
                    labels={"AvgEnergyCost_EUR_100km": "EUR per 100km"},
                    title="Avg Estimated Energy Cost per 100km (by Brand)"
                ),
                use_container_width=True
            )
        else:
            st.info("Brand energy table is empty after filtering.")
