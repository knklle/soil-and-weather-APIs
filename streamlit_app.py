import streamlit as st

import pandas as pd

import numpy as np

import requests

import json

import hashlib

import time

import plotly.express as px

import plotly.graph_objects as go

from datetime import date

from pathlib import Path

from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry

# ============================================================

# PAGE CONFIGURATION

# ============================================================

st.set_page_config(

    page_title="ITD112 Laboratory Exercise 1: API Integration",

    layout="wide"

)

from ui.dashboard import header, controls, empty_state, results

header()

# ============================================================

# 1. CONFIGURATION

# ============================================================

SITES = pd.DataFrame(

    [

        ("Iligan City", 8.200, 124.300),

        ("Malaybalay", 8.150, 125.130),

        ("Valencia", 7.91145, 125.07746),

        ("Davao (Calinan)", 7.190, 125.460),

        ("General Santos", 6.150, 125.150),

    ],

    columns=["site", "lat", "lon"],

)

SOIL_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

SOIL_PROPERTIES = [

    "clay",

    "sand",

    "silt",

    "phh2o",

    "soc",

]

SOIL_DEPTH = "0-5cm"

DAILY_VARS = [

    "temperature_2m_mean",

    "precipitation_sum",

    "et0_fao_evapotranspiration",

]

TIMEZONE = "Asia/Manila"

CACHE_DIR = Path("cache")

SOILGRIDS_PAUSE_S = 12

MONTHS = [

    "Jan", "Feb", "Mar", "Apr",

    "May", "Jun", "Jul", "Aug",

    "Sep", "Oct", "Nov", "Dec"

]

COLORS = {

    "sky": "#3563A8",

    "sky_pale": "#A9BDDA",

    "sun": "#64748B",

    "clay": "#53677F",

    "sand": "#B8CBE3",

    "silt": "#8A9AAF",

}

# ============================================================

# 2. BUILD THE REQUEST

# ============================================================

def full_url(url, params):

    return requests.Request(

        "GET",

        url,

        params=params

    ).prepare().url

def build_weather_request(sites, start, end):

    params = {

        "latitude": ",".join(str(v) for v in sites["lat"]),

        "longitude": ",".join(str(v) for v in sites["lon"]),

        "start_date": start,

        "end_date": end,

        "daily": ",".join(DAILY_VARS),

        "timezone": TIMEZONE,

    }

    return {

        "api": "Open-Meteo",

        "label": "All sites",

        "url": WEATHER_URL,

        "params": params,

        "full_url": full_url(WEATHER_URL, params),

    }

def build_soil_request(site, lat, lon):

    params = [

        ("lat", lat),

        ("lon", lon),

        ("depth", SOIL_DEPTH),

        ("value", "mean"),

    ]

    params += [

        ("property", p)

        for p in SOIL_PROPERTIES

    ]

    return {

        "api": "SoilGrids",

        "label": site,

        "url": SOIL_URL,

        "params": params,

        "full_url": full_url(SOIL_URL, params),

    }

# ============================================================

# 3. SEND THE REQUEST

# ============================================================

@st.cache_resource

def http_session():

    retry = Retry(

        total=3,

        backoff_factor=2,

        status_forcelist=(

            429,

            500,

            502,

            503,

            504

        ),

        allowed_methods=("GET",)

    )

    session = requests.Session()

    session.mount(

        "https://",

        HTTPAdapter(max_retries=retry)

    )

    session.headers["User-Agent"] = "itd112-lab1/1.0"

    return session

def send(req):

    key = hashlib.sha1(

        (

            req["url"]

            + json.dumps(

                req["params"],

                sort_keys=True,

                default=str

            )

        ).encode()

    ).hexdigest()

    path = CACHE_DIR / f"{key}.json"

    if path.exists():

        text = path.read_text(

            encoding="utf-8"

        )

        return {

            "status": None,

            "from_cache": True,

            "data": json.loads(text),

            "elapsed_s": None,

            "size_bytes": len(

                text.encode("utf-8")

            ),

        }

    started = time.perf_counter()

    response = http_session().get(

        req["url"],

        params=req["params"],

        timeout=60

    )

    elapsed = (

        time.perf_counter()

        - started

    )

    response.raise_for_status()

    data = response.json()

    CACHE_DIR.mkdir(

        exist_ok=True

    )

    text = json.dumps(data)

    path.write_text(

        text,

        encoding="utf-8"

    )

    return {

        "status": response.status_code,

        "from_cache": False,

        "data": data,

        "elapsed_s": elapsed,

        "size_bytes": len(

            response.content

        ),

    }

# ============================================================

# 4. PARSE JSON

# ============================================================

def parse_weather(data, sites):

    results = (

        data

        if isinstance(data, list)

        else [data]

    )

    frames = []

    for site, res in zip(

        sites["site"],

        results

    ):

        df = pd.DataFrame(

            res["daily"]

        )

        df.insert(

            0,

            "site",

            site

        )

        frames.append(

            df

        )

    return pd.concat(

        frames,

        ignore_index=True

    )

def parse_soil(data, site):

    rows = []

    for layer in data["properties"]["layers"]:

        raw = (

            layer["depths"][0]

            ["values"]["mean"]

        )

        unit = layer["unit_measure"]

        rows.append(

            {

                "site": site,

                "property": layer["name"],

                "raw_mean": raw,

                "mapped_units": unit.get("mapped_units"),

                "d_factor": unit["d_factor"],

                "value": (

                    np.nan

                    if raw is None

                    else raw / unit["d_factor"]

                ),

                "target_units": unit.get("target_units"),

            }

        )

    return pd.DataFrame(rows)

def soil_table(

    soil_long,

    sites

):

    wide = (

        soil_long

        .pivot(

            index="site",

            columns="property",

            values="value"

        )

        .reindex(

            columns=SOIL_PROPERTIES

        )

        .reset_index()

    )

    wide.columns.name = None

    return sites.merge(

        wide,

        on="site",

        how="left"

    )

# ============================================================

# 5. INTEGRATE

# ============================================================

def integrate(

    weather,

    soil

):

    daily = weather.merge(

        soil,

        on="site",

        how="left"

    )

    daily["time"] = pd.to_datetime(

        daily["time"]

    )

    daily["month"] = (

        daily["time"].dt.month

    )

    daily["water_balance_mm"] = (

        daily["precipitation_sum"]

        - daily["et0_fao_evapotranspiration"]

    )

    summary = (

        daily

        .groupby(

            "site",

            sort=False

        )

        .agg(

            rain_mm=(

                "precipitation_sum",

                "sum"

            ),

            et0_mm=(

                "et0_fao_evapotranspiration",

                "sum"

            ),

            water_balance_mm=(

                "water_balance_mm",

                "sum"

            ),

            temp_mean_c=(

                "temperature_2m_mean",

                "mean"

            )

        )

        .reset_index()

        .merge(

            soil,

            on="site"

        )

    )

    return daily, summary

# ============================================================

# 6. CHARTS

# ============================================================

def chart_q1(

    daily,

    site

):

    d = daily[

        daily["site"] == site

    ].copy()

    d = d.sort_values("time")

    d["temp_7day"] = (

        d["temperature_2m_mean"]

        .rolling(

            window=7,

            min_periods=1

        )

        .mean()

    )

    fig = px.line(

        d,

        x="time",

        y="temp_7day",

        title=f"Q1 — Temperature Over Time: {site}",

        labels={

            "time": "Date",

            "temp_7day": "7-day mean temperature (°C)"

        }

    )

    fig.update_yaxes(

        title="Temperature (°C)"

    )

    return fig

def chart_q2(

    daily,

    site

):

    m = (

        daily[

            daily["site"] == site

        ]

        .groupby("month")[

            [

                "precipitation_sum",

                "et0_fao_evapotranspiration"

            ]

        ]

        .sum()

        .reindex(

            range(1, 13),

            fill_value=0

        )

    )

    deficit = (

        m["precipitation_sum"]

        <

        m["et0_fao_evapotranspiration"]

    )

    fig = go.Figure()

    fig.add_bar(

        x=MONTHS,

        y=m["precipitation_sum"],

        name="Rainfall",

        marker_color=np.where(

            deficit,

            COLORS["sky_pale"],

            COLORS["sky"]

        )

    )

    fig.add_scatter(

        x=MONTHS,

        y=m["et0_fao_evapotranspiration"],

        name="Reference ET0",

        mode="lines+markers",

        line=dict(

            color=COLORS["sun"],

            width=2.5

        )

    )

    fig.update_layout(

        title=f"Q2 — Rainfall vs Evaporative Demand: {site}"

    )

    fig.update_yaxes(

        title="mm per month",

        rangemode="tozero"

    )

    return fig

def chart_q3(

    daily,

    site

):

    d = daily[

        daily["site"] == site

    ].copy()

    d["month_name"] = (

        d["month"]

        .map(

            dict(

                zip(

                    range(1, 13),

                    MONTHS

                )

            )

        )

    )

    fig = px.box(

        d,

        x="month_name",

        y="precipitation_sum",

        category_orders={

            "month_name": MONTHS

        },

        title=f"Q3 — Daily Rainfall Variability: {site}",

        labels={

            "month_name": "Month",

            "precipitation_sum": "Daily rainfall (mm)"

        }

    )

    return fig

def chart_q4(

    summary

):

    tex = (

        summary

        .set_index("site")[

            [

                "sand",

                "silt",

                "clay"

            ]

        ]

        .dropna()

    )

    tex = (

        tex

        .div(

            tex.sum(axis=1),

            axis=0

        )

        .mul(100)

        .sort_values("clay")

    )

    tex = (

        tex

        .reset_index()

        .melt(

            id_vars="site",

            value_vars=[

                "sand",

                "silt",

                "clay"

            ],

            var_name="Texture",

            value_name="Percent"

        )

    )

    fig = px.bar(

        tex,

        x="site",

        y="Percent",

        color="Texture",

        barmode="stack",

        title="Q4 — Topsoil Texture by Site",

        labels={

            "site": "Site",

            "Percent": "Normalized soil texture (%)"

        },

        color_discrete_map={

            "sand": COLORS["sand"],

            "silt": COLORS["silt"],

            "clay": COLORS["clay"],

        }

    )

    fig.update_yaxes(

        range=[0, 100]

    )

    return fig

def chart_q5(

    summary

):

    s = summary.dropna(

        subset=[

            "clay",

            "soc",

            "water_balance_mm"

        ]

    ).copy()

    fig = go.Figure()

    if len(s) == 0:

        return fig

    max_soc = s["soc"].max()

    if (

        pd.isna(max_soc)

        or max_soc == 0

    ):

        bubble_size = np.repeat(

            20,

            len(s)

        )

    else:

        bubble_size = (

            14

            + 26

            * s["soc"]

            / max_soc

        )

    fig.add_scatter(

        x=s["clay"],

        y=s["water_balance_mm"],

        mode="markers+text",

        text=s["site"],

        textposition="top center",

        marker=dict(

            size=bubble_size

        ),

        name="Sites"

    )

    if len(s) >= 5:

        slope, intercept = np.polyfit(

            s["clay"],

            s["water_balance_mm"],

            1

        )

        r = np.corrcoef(

            s["clay"],

            s["water_balance_mm"]

        )[0, 1]

        xs = np.linspace(

            s["clay"].min(),

            s["clay"].max(),

            100

        )

        fig.add_scatter(

            x=xs,

            y=slope * xs + intercept,

            mode="lines",

            name=(

                f"Linear fit "

                f"(r = {r:.2f}, n = {len(s)})"

            )

        )

    fig.add_hline(

        y=0,

        annotation_text="rainfall = ET0"

    )

    fig.update_layout(

        title="Q5 — Does Soil Moderate Water Stress?",

        xaxis_title="Clay content (%)",

        yaxis_title="Water balance (mm)"

    )

    return fig

def chart_q6(

    summary

):

    m = summary.dropna(

        subset=[

            "lat",

            "lon",

            "soc",

            "rain_mm"

        ]

    ).copy()

    if len(m) == 0:

        return None

    try:

        fig = px.scatter_map(

            m,

            lat="lat",

            lon="lon",

            color="soc",

            size="rain_mm",

            hover_name="site",

            hover_data={

                "rain_mm": ":.1f",

                "soc": ":.1f",

                "lat": False,

                "lon": False,

            },

            zoom=5,

            center={

                "lat": float(m["lat"].mean()),

                "lon": float(m["lon"].mean()),

            },

            title="Q6 — Site Map: SOC and Rainfall",

            labels={

                "soc": "SOC (g/kg)",

                "rain_mm": "Rainfall (mm)"

            }

        )

    except AttributeError:

        fig = px.scatter_mapbox(

            m,

            lat="lat",

            lon="lon",

            color="soc",

            size="rain_mm",

            hover_name="site",

            zoom=5,

            center={

                "lat": float(m["lat"].mean()),

                "lon": float(m["lon"].mean()),

            },

            mapbox_style="open-street-map",

            title="Q6 — Site Map: SOC and Rainfall"

        )

    return fig

# ============================================================

# INPUTS

# ============================================================

sites, start, end, fetch = controls(SITES)

if fetch:
    if sites.empty:
        st.error("Select at least one site in the sidebar.")
    elif start > end:
        st.error("Start date must be on or before the end date.")
    elif end >= date.today():
        st.error("Choose an end date before today for historical weather.")
    else:
        try:
            with st.status("Integrating soil and weather…", expanded=True) as status:
                weather_req = build_weather_request(sites, start, end)
                soil_reqs = [build_soil_request(row.site, row.lat, row.lon)
                             for row in sites.itertuples()]
                st.write("Fetching weather for all selected sites…")
                weather_res = send(weather_req)
                soil_res = []
                for i, req in enumerate(soil_reqs):
                    st.write(f"Fetching topsoil for {req['label']} ({i + 1}/{len(soil_reqs)})…")
                    soil_res.append(send(req))
                    if not soil_res[-1]["from_cache"] and i < len(soil_reqs) - 1:
                        time.sleep(SOILGRIDS_PAUSE_S)
                st.write("Parsing responses and checking the join…")
                weather = parse_weather(weather_res["data"], sites)
                soil_long = pd.concat([parse_soil(res["data"], req["label"])
                                       for req, res in zip(soil_reqs, soil_res)], ignore_index=True)
                soil = soil_table(soil_long, sites)
                daily, summary = integrate(weather, soil)
                if len(daily) != len(weather):
                    raise ValueError("The join changed the weather row count.")
                log = []
                for req, res in zip([weather_req] + soil_reqs, [weather_res] + soil_res):
                    log.append({"API": req["api"], "Site": req["label"],
                                "Status": "Saved copy" if res["from_cache"] else str(res["status"]),
                                "Time (s)": None if res["from_cache"] else round(res["elapsed_s"], 3),
                                "Payload (bytes)": res["size_bytes"]})
                st.session_state["integration_result"] = dict(
                    daily=daily, summary=summary, weather=weather, soil=soil,
                    soil_long=soil_long, log=pd.DataFrame(log),
                    requests=[weather_req] + soil_reqs, start=start, end=end)
                status.update(label="Integration complete", state="complete", expanded=False)
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
            st.error("Integration could not finish. Check your dates and try again. SoilGrids may temporarily be unavailable.")
            with st.expander("Error details"):
                st.code(str(exc), language=None)
            if "integration_result" in st.session_state:
                st.info("Your previous completed results are still available below.")

if "integration_result" in st.session_state:
    results(st.session_state["integration_result"],
            [chart_q1, chart_q2, chart_q3, chart_q4, chart_q5, chart_q6])
else:
    empty_state()
