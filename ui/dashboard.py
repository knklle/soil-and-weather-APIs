"""Streamlit layout only; API requests and calculations live in streamlit_app.py."""
from datetime import date
from pathlib import Path
import streamlit as st


def header():
    stylesheet = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.html(f"<style>{stylesheet}</style>")
    st.caption("ITD112 · LABORATORY EXERCISE 1")
    st.title("Soil & weather explorer")
    st.write("Explore local weather, compare topsoil, and download your integrated dataset.")


def controls(all_sites):
    with st.sidebar:
        st.header("Your study area")
        st.caption("1. Choose sites and dates.  2. Run.  3. Explore the results.")
        with st.form("study_settings"):
            chosen = st.multiselect("Sites", all_sites["site"].tolist(),
                                    default=all_sites["site"].tolist()[:3])
            start = st.date_input("Start date", date(2025, 1, 1))
            end = st.date_input("End date", date(2025, 12, 31))
            st.caption("Historical weather · Topsoil depth: 0–5 cm")
            fetch = st.form_submit_button("Run integration", type="primary", width="stretch")
        st.info("First runs can take a few minutes. Saved API responses make repeat runs faster.")
        with st.expander("What do these values mean?"):
            st.write("**ET0:** reference evapotranspiration, a measure of evaporative demand.")
            st.write("**Water balance:** rainfall minus ET0. Negative values indicate a climatic deficit.")
            st.write("**SOC:** soil organic carbon, measured in g/kg.")
    return all_sites[all_sites["site"].isin(chosen)].reset_index(drop=True), start, end, fetch


def empty_state():
    with st.container(border=True):
        st.subheader("Start with a study area")
        st.write("Select one or more sites in the sidebar, choose your date range, then click **Run integration**.")
        st.caption("Your results will include a site overview, six analysis charts, data tables, and CSV exports.")


def plot(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f4f7fb",
        font=dict(color="#243449"),
        colorway=["#3563a8", "#7892b5", "#53677f", "#a9bdd8", "#8b84ad"],
        margin=dict(l=20, r=20, t=65, b=30),
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def results(result, charts):
    daily, summary = result["daily"], result["summary"]
    st.caption(f"Showing completed run · {result['start']:%d %b %Y} – {result['end']:%d %b %Y} · "
               f"{len(summary)} sites")
    overview, analysis, data, requests, export = st.tabs(
        ["Overview", "Analysis", "Data tables", "API details", "Downloads"])
    with overview:
        st.subheader("Your study at a glance")
        cols = st.columns(3)
        cols[0].metric("Sites", len(summary))
        cols[1].metric("Daily records", f"{len(daily):,}")
        cols[2].metric("Days per site", daily["time"].nunique())
        st.dataframe(summary, width="stretch", hide_index=True)
        st.caption("Rainfall, ET0, and water balance are totals for the selected period; temperature is a mean.")
        missing = summary.loc[summary["clay"].isna(), "site"].tolist()
        if missing:
            st.warning("Missing soil values: " + ", ".join(missing) + ". Some charts omit these sites.")
        st.info("Use Analysis to explore charts, Data tables to inspect the join, or Downloads to save CSV files.")
    with analysis:
        climate, soil = st.tabs(["Weather at a site · Q1–Q3", "Compare sites · Q4–Q6"])
        with climate:
            names = summary["site"].tolist()
            if st.session_state.get("analysis_site") not in names:
                st.session_state["analysis_site"] = names[0]
            site = st.selectbox("Explore a site", names, key="analysis_site")
            for chart, note in zip(charts[:3], [
                "Q1 · Temperature smoothed with a 7-day rolling mean.",
                "Q2 · Monthly rainfall compared with reference ET0. Pale bars indicate a deficit.",
                "Q3 · Distribution of daily rainfall in each month.",
            ]):
                st.caption(note)
                plot(chart(daily, site))
        with soil:
            st.caption("Q4 · Sand, silt, and clay normalized to 100%.")
            plot(charts[3](summary))
            st.caption("Q5 · Clay versus climatic water balance; bubble size represents SOC.")
            plot(charts[4](summary))
            st.info("This comparison is exploratory. Water balance uses rainfall and ET0; it does not measure soil water stress. A trend appears with at least five valid sites.")
            fig = charts[5](summary)
            if fig is not None:
                plot(fig)
            else:
                st.warning("No valid SOC, rainfall, and coordinates are available for the map.")
    with data:
        st.subheader("Inspect the integration")
        st.success("Join verified: the daily weather row count was preserved.")
        table = st.selectbox("Table", ["Joined daily records", "Site summary", "Weather records", "Soil by site", "Soil unit conversion audit"])
        tables = dict(zip(["Joined daily records", "Site summary", "Weather records", "Soil by site", "Soil unit conversion audit"],
                          [daily, summary, result["weather"], result["soil"], result["soil_long"]]))
        frame = tables[table]
        st.dataframe(frame, width="stretch", hide_index=True)
        st.caption(f"{len(frame):,} rows × {len(frame.columns)} columns")
        if table == "Soil unit conversion audit":
            st.caption("Each raw SoilGrids value is divided by its property's d_factor.")
    with requests:
        st.subheader("Request and response audit")
        st.dataframe(result["log"], width="stretch", hide_index=True)
        with st.expander("View request URLs"):
            for req in result["requests"]:
                st.write(f"**{req['api']} · {req['label']}**")
                st.code(req["full_url"], language=None)
    with export:
        st.subheader("Take your data with you")
        st.write("CSV files open in Excel, Google Sheets, and other analysis tools.")
        a, b = st.columns(2)
        with a:
            st.download_button("Download site summary", summary.to_csv(index=False),
                               "site_summary.csv", "text/csv", width="stretch")
            st.caption("One row per site: weather totals and soil properties.")
        with b:
            st.download_button("Download daily records", daily.drop(columns="month").to_csv(index=False),
                               "integrated_daily.csv", "text/csv", width="stretch")
            st.caption("Every weather day joined with its site's soil properties.")
    st.divider()
    st.caption("Sources: SoilGrids 2.0 (ISRIC, CC BY 4.0), 0–5 cm mean; Open-Meteo Historical Weather API (CC BY 4.0). Soil values are modelled estimates.")
