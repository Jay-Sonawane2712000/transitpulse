from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "warehouse" / "transitpulse.duckdb"


st.set_page_config(
    page_title="TransitPulse Dashboard",
    page_icon="TP",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.7rem 0.8rem;
        background: #111827;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] p {
        color: #cbd5e1;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.45rem;
        color: #f8fafc;
        font-weight: 700;
    }
    div[data-testid="stMetricDelta"] {
        color: #cbd5e1;
    }
    .note-panel {
        border-left: 4px solid #38bdf8;
        background: #0f172a;
        border-top: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        border-bottom: 1px solid #1e293b;
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 0.9rem;
        margin: 0.35rem 0 1rem 0;
        color: #e2e8f0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def run_query(database_path: str, sql: str) -> pd.DataFrame:
    with duckdb.connect(database_path, read_only=True) as connection:
        return connection.execute(sql).df()


def query(sql: str) -> pd.DataFrame:
    return run_query(str(st.session_state["database_path"]), sql)


def scalar(sql: str, default=None):
    df = query(sql)
    if df.empty:
        return default
    value = df.iloc[0, 0]
    if pd.isna(value):
        return default
    return value


def format_number(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{int(value):,}"


def format_percent(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def format_minutes(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f} min"


def display_label(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    label = str(value).replace("_", " ")
    replacements = {
        "duplicate trip update entity": "duplicate trip updates",
        "extreme delay outlier": "extreme delay outliers",
        "feed quality warning": "feed quality warning",
        "feed freshness issue": "freshness issue",
        "active with both feeds": "both feeds",
        "active vehicle only": "vehicle only",
        "active trip updates only": "trip updates only",
        "inactive or missing": "inactive/missing",
        "early more than 5 min": "early >5 min",
        "early 1 to 5 min": "early 1-5 min",
        "late 5 to 15 min": "late 5-15 min",
        "late 15 to 30 min": "late 15-30 min",
        "late 30 to 60 min": "late 30-60 min",
        "late over 60 min": "late >60 min",
        "within expected interval": "within interval",
        "insufficient data": "insufficient",
        "highly variable": "high variable",
    }
    return replacements.get(label, label.title())


def leading_labels(df: pd.DataFrame, label_column: str, limit: int = 2) -> str:
    if df.empty:
        return "no current findings"
    labels = [display_label(value).lower() for value in df[label_column].head(limit)]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def render_bar(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str | None = None):
    if df.empty:
        st.info("No records available for this view.")
        return
    chart_df = df.copy()
    display_x = f"{x}_display"
    chart_df[display_x] = chart_df[x].map(display_label)
    labels = {
        display_x: x.replace("_", " ").title(),
        y: y.replace("_", " ").title(),
    }
    if color:
        labels[color] = color.replace("_", " ").title()
    fig = px.bar(chart_df, x=display_x, y=y, color=color, title=title, labels=labels)
    fig.update_xaxes(tickangle=-25, automargin=True)
    fig.update_yaxes(automargin=True)
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=55, b=80), legend_title_text="")
    st.plotly_chart(fig, width="stretch")


def render_line(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str | None = None):
    if df.empty:
        st.info("No records available for this view.")
        return
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        markers=True,
        title=title,
        labels={x: x.replace("_", " ").title(), y: y.replace("_", " ").title()},
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=55, b=55), legend_title_text="")
    st.plotly_chart(fig, width="stretch")


def render_overview():
    st.caption("A compact readout of capture health, anomaly volume, delay performance, and static/realtime schedule alignment.")
    feed_snapshots = scalar("select count(*) from fct_feed_quality", 0)
    anomaly_findings = scalar("select count(*) from fct_anomaly_findings", 0)
    high_priority = scalar(
        """
        select count(*)
        from fct_anomaly_findings
        where anomaly_severity in ('critical', 'high')
        """,
        0,
    )
    avg_delay = scalar(
        """
        select avg(estimated_delay_minutes)
        from fct_on_time_performance
        where delay_sanity_status = 'plausible'
        """,
    )
    match_rate = scalar(
        """
        select
            sum(case when schedule_match_status = 'matched_to_static_schedule' then 1 else 0 end)::double
            / nullif(count(*), 0)
        from fct_on_time_performance
        """,
    )

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Feed snapshots", format_number(feed_snapshots))
    kpi_cols[1].metric("Anomaly findings", format_number(anomaly_findings))
    kpi_cols[2].metric("Critical/high findings", format_number(high_priority))
    kpi_cols[3].metric("Avg plausible delay", format_minutes(avg_delay))
    kpi_cols[4].metric(
        "Schedule match",
        format_percent(match_rate),
        help="Trip updates are matched against the version-aligned archived C6 static schedule, which is why this can cleanly reach 100%.",
    )

    anomaly_df = query(
        """
        select anomaly_type, count(*) as finding_count
        from fct_anomaly_findings
        group by 1
        order by finding_count desc
        """
    )
    st.caption(
        f"Current run shows {format_percent(match_rate)} schedule matching against the aligned static feed; "
        f"the leading anomaly categories are {leading_labels(anomaly_df, 'anomaly_type')}."
    )

    st.markdown(
        '<div class="note-panel">TransitPulse is reading dbt-built marts from the local DuckDB warehouse. '
        "Raw captures and the warehouse database stay local and are ignored by Git.</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        status_df = query(
            """
            select feed_quality_status, count(*) as snapshot_count
            from fct_feed_quality
            group by 1
            order by snapshot_count desc
            """
        )
        render_bar(status_df, "feed_quality_status", "snapshot_count", title="Feed Quality Status")
    with right:
        render_bar(anomaly_df, "anomaly_type", "finding_count", title="Anomaly Findings by Type")


def render_feed_quality():
    st.subheader("Feed Quality")
    st.caption("Shows whether each captured snapshot has complete, fresh, and internally consistent realtime feed records.")
    trend_df = query(
        """
        select
            snapshot_timestamp_utc,
            snapshot_folder,
            feed_quality_status,
            null_gps_rate,
            duplicate_trip_update_rate,
            unmatched_realtime_trip_rate,
            vehicle_record_count,
            trip_update_record_count
        from fct_feed_quality
        order by snapshot_timestamp_utc
        """
    )

    left, right, third = st.columns(3)
    left.metric("Avg null GPS rate", format_percent(trend_df["null_gps_rate"].mean() if not trend_df.empty else None))
    right.metric(
        "Avg duplicate trip update rate",
        format_percent(trend_df["duplicate_trip_update_rate"].mean() if not trend_df.empty else None),
    )
    third.metric(
        "Avg unmatched trip rate",
        format_percent(trend_df["unmatched_realtime_trip_rate"].mean() if not trend_df.empty else None),
    )

    render_line(trend_df, "snapshot_timestamp_utc", "duplicate_trip_update_rate", title="Duplicate Trip Update Rate by Snapshot")
    st.dataframe(trend_df, width="stretch", hide_index=True)


def render_anomalies():
    st.subheader("Anomaly Findings")
    st.caption("Lists explainable findings generated by deterministic rules and summarizes synthetic benchmark performance.")
    st.markdown(
        '<div class="note-panel">The production anomaly mart uses deterministic rules. '
        "It is not an ML model. Synthetic evaluation validates the same rule families, while production output remains explainable findings.</div>",
        unsafe_allow_html=True,
    )

    counts_df = query(
        """
        select anomaly_type, anomaly_severity, count(*) as finding_count
        from fct_anomaly_findings
        group by 1, 2
        order by finding_count desc
        """
    )
    render_bar(counts_df, "anomaly_type", "finding_count", "anomaly_severity", "Findings by Type and Severity")

    benchmark_df = query(
        """
        select
            anomaly_type,
            true_positive,
            false_positive,
            false_negative,
            true_negative,
            precision,
            recall,
            f1_score
        from int_anomaly_detection_metrics
        order by case when metric_scope = 'overall' then 0 else 1 end, anomaly_type
        """
    )
    st.markdown("#### Detector Benchmark")
    st.dataframe(benchmark_df, width="stretch", hide_index=True)

    top_findings = query(
        """
        select
            anomaly_type,
            anomaly_severity,
            anomaly_score,
            snapshot_folder,
            route_id,
            trip_id,
            entity_id,
            detector_rule_id,
            anomaly_reason
        from fct_anomaly_findings
        order by anomaly_score desc, anomaly_severity, anomaly_type
        limit 50
        """
    )
    st.markdown("#### Top Findings")
    st.dataframe(top_findings, width="stretch", hide_index=True)


def render_route_activity():
    st.subheader("Route Activity")
    st.caption("Compares realtime vehicle positions and trip updates by route so active and under-reported routes stand out.")
    status_df = query(
        """
        select route_activity_status, count(*) as route_snapshot_count
        from fct_route_realtime_activity
        group by 1
        order by route_snapshot_count desc
        """
    )
    render_bar(status_df, "route_activity_status", "route_snapshot_count", title="Route Activity Status")

    top_routes = query(
        """
        select
            route_id,
            sum(total_realtime_records) as total_realtime_records,
            sum(vehicle_position_count) as vehicle_positions,
            sum(trip_update_count) as trip_updates,
            max(distinct_vehicle_count) as peak_distinct_vehicles
        from fct_route_realtime_activity
        group by 1
        order by total_realtime_records desc
        limit 25
        """
    )
    render_bar(top_routes.head(10), "route_id", "total_realtime_records", title="Top 10 Routes by Realtime Records")
    st.dataframe(top_routes, width="stretch", hide_index=True)


def render_on_time():
    st.subheader("On-Time Performance")
    st.caption("Summarizes schedule-derived delay estimates for matched trips, with sanity bands separating plausible values from outliers.")
    cols = st.columns(3)
    on_time_rate = scalar(
        """
        select
            sum(case when on_time_flag then 1 else 0 end)::double
            / nullif(sum(case when on_time_flag is not null then 1 else 0 end), 0)
        from fct_on_time_performance
        """
    )
    plausible_delay = scalar(
        """
        select avg(estimated_delay_minutes)
        from fct_on_time_performance
        where delay_sanity_status = 'plausible'
        """
    )
    extreme_count = scalar(
        """
        select count(*)
        from fct_on_time_performance
        where delay_sanity_status in ('extreme_early', 'extreme_late')
        """,
        0,
    )
    cols[0].metric("On-time rate", format_percent(on_time_rate))
    cols[1].metric("Avg plausible delay", format_minutes(plausible_delay))
    cols[2].metric("Extreme delay rows", format_number(extreme_count))

    band_df = query(
        """
        select delay_band, count(*) as trip_snapshot_count
        from fct_on_time_performance
        group by 1
        order by trip_snapshot_count desc
        """
    )
    render_bar(band_df, "delay_band", "trip_snapshot_count", title="Delay Band Distribution")

    top_delayed = query(
        """
        select
            route_id,
            count(*) as trip_snapshot_count,
            avg(estimated_delay_minutes) as avg_estimated_delay_minutes,
            max(estimated_delay_minutes) as max_estimated_delay_minutes
        from fct_on_time_performance
        where delay_sanity_status = 'plausible'
        group by 1
        having count(*) >= 5
        order by avg_estimated_delay_minutes desc
        limit 25
        """
    )
    render_bar(top_delayed.head(10), "route_id", "avg_estimated_delay_minutes", title="Top 10 Routes by Avg Plausible Delay")
    st.dataframe(top_delayed, width="stretch", hide_index=True)


def render_headway():
    st.subheader("Headway and Reliability")
    st.caption("Approximates route-level vehicle spacing inside each snapshot using vehicle report timestamps.")
    st.markdown(
        '<div class="note-panel">Headway is currently a route-level vehicle timestamp-spread proxy within each snapshot. '
        "It is useful for spotting uneven realtime vehicle reporting, but it is not true stop-level passenger headway.</div>",
        unsafe_allow_html=True,
    )

    status_df = query(
        """
        select headway_reliability_status, count(*) as route_snapshot_count
        from fct_headway
        group by 1
        order by route_snapshot_count desc
        """
    )
    render_bar(status_df, "headway_reliability_status", "route_snapshot_count", title="Headway Reliability Status")

    spacing = scalar(
        """
        select avg(avg_vehicle_spacing_minutes)
        from fct_headway
        where avg_vehicle_spacing_minutes is not null
        """
    )
    st.metric("Avg vehicle timestamp spacing", format_minutes(spacing))

    variable_routes = query(
        """
        select
            route_id,
            snapshot_folder,
            distinct_vehicle_count,
            avg_vehicle_spacing_minutes,
            headway_variance_minutes,
            headway_reliability_status
        from fct_headway
        where headway_variance_minutes is not null
        order by headway_variance_minutes desc
        limit 25
        """
    )
    st.dataframe(variable_routes, width="stretch", hide_index=True)


def main():
    st.title("TransitPulse")
    st.caption("Bus service data quality, delay intelligence, and anomaly findings from validated DuckDB/dbt marts.")

    with st.sidebar:
        st.header("Data Source")
        database_path = Path(st.text_input("DuckDB warehouse", str(DEFAULT_DATABASE_PATH))).expanduser()
        st.session_state["database_path"] = str(database_path)
        page = st.radio(
            "View",
            [
                "Executive Overview",
                "Feed Quality",
                "Anomaly Findings",
                "Route Activity",
                "On-Time Performance",
                "Headway / Reliability",
            ],
        )
        st.caption("Uses the local DuckDB warehouse generated by the ingestion and dbt pipeline. Raw captures and warehouse files are ignored by Git.")

    if not database_path.exists():
        st.error(f"DuckDB warehouse not found: {database_path}")
        st.stop()

    snapshot_range = query(
        """
        select
            min(snapshot_timestamp_utc) as first_snapshot,
            max(snapshot_timestamp_utc) as latest_snapshot
        from fct_feed_quality
        """
    )
    if not snapshot_range.empty:
        st.sidebar.caption(
            f"Snapshots: {snapshot_range.loc[0, 'first_snapshot']} to {snapshot_range.loc[0, 'latest_snapshot']}"
        )

    if page == "Executive Overview":
        render_overview()
    elif page == "Feed Quality":
        render_feed_quality()
    elif page == "Anomaly Findings":
        render_anomalies()
    elif page == "Route Activity":
        render_route_activity()
    elif page == "On-Time Performance":
        render_on_time()
    else:
        render_headway()


if __name__ == "__main__":
    main()
