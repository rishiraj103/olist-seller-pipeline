"""Olist seller performance app: overview, seller scorecard, AI insight.

Run: streamlit run app/streamlit_app.py      (WAREHOUSE=app in .env reads RDS as app_reader; default local)
"""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for loader/ and genai/
from genai.insights import explain_seller  # noqa: E402
from loader.curated_to_warehouse import connect  # noqa: E402

load_dotenv()
BLUE = "#2a78d6"
STATUS = {"SUCCESS": "✅ Success", "FAILED": "❌ Failed", "RUNNING": "⏳ Running"}


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = connect(os.getenv("WAREHOUSE", "local"))
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    finally:
        conn.close()


def numeric(df: pd.DataFrame) -> pd.DataFrame:
    """PostgreSQL numeric arrives as Decimal; plotting and sums want floats."""
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


def style(fig, y_title: str):
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320, xaxis_title=None, yaxis_title=y_title,
                      hovermode="x unified", barcornerradius=4)
    return fig


def overview():
    st.title("Overview")
    kpi = numeric(query("SELECT * FROM analytics.kpi_monthly"))
    months = sorted(kpi["month"].unique())
    by_month = kpi.groupby("month")["orders"].sum()
    full = by_month[by_month >= 500].index  # the first and last months have only a handful of orders
    c1, c2 = st.columns([2, 1])
    start, end = c1.select_slider("Purchase months", options=months, value=(full.min(), full.max()),
                                  format_func=lambda m: m.strftime("%b %Y"))
    states = c2.multiselect("Customer state", sorted(kpi["customer_state"].unique()), placeholder="All states")
    sel = kpi[(kpi["month"] >= start) & (kpi["month"] <= end)]
    if states:
        sel = sel[sel["customer_state"].isin(states)]

    k = sel.sum(numeric_only=True)
    cols = st.columns(4)
    cols[0].metric("Revenue (BRL)", f"{k['revenue']:,.0f}")
    cols[1].metric("Orders", f"{k['orders']:,.0f}")
    cols[2].metric("On-time delivery", f"{100 * k['on_time_orders'] / max(k['delivered_orders'], 1):.1f}%")
    cols[3].metric("Average rating", f"{k['rating_sum'] / max(k['rated_orders'], 1):.2f} / 5")

    trend = numeric(query("SELECT * FROM analytics.on_time_delivery"))
    trend = trend[(trend["month"] >= start) & (trend["month"] <= end)]
    if states:
        trend = trend[trend["customer_state"].isin(states)]
    trend = trend.groupby("month", as_index=False)[["on_time_orders", "delivered_orders"]].sum()
    trend["on_time_pct"] = (100 * trend["on_time_orders"] / trend["delivered_orders"]).round(1)
    st.subheader("On-time delivery % by purchase month")
    fig = px.line(trend, x="month", y="on_time_pct", markers=True, color_discrete_sequence=[BLUE],
                  hover_data={"delivered_orders": True})
    fig.update_traces(line_width=2, marker_size=8)
    st.plotly_chart(style(fig, "On-time %"), width="stretch")

    st.subheader("Latest pipeline batch")
    batch = query("SELECT batch_id, status, started_at, ended_at, message FROM audit.batch_log "
                  "ORDER BY run_id DESC LIMIT 1")
    if batch.empty:
        st.info("No batch loaded yet.")
    else:
        b = batch.iloc[0]
        when = f"finished {b.ended_at:%Y-%m-%d %H:%M}" if b.ended_at else f"started {b.started_at:%Y-%m-%d %H:%M}"
        st.write(f"**{b.batch_id}** · {STATUS.get(b.status, b.status)} · {when} · {b.message or ''}")


def scorecard():
    st.title("Seller scorecard")
    top = numeric(query("SELECT * FROM analytics.top_sellers_monthly"))
    months = sorted(top["month"].unique(), reverse=True)
    sizes = top.groupby("month").size()
    default = next(i for i, m in enumerate(months) if sizes[m] >= 10)  # latest month with a full top 10
    month = st.selectbox("Month", months, index=default, format_func=lambda m: m.strftime("%B %Y"))
    table = top[top["month"] == month].drop(columns="month")
    st.caption("Top 10 sellers by revenue in the month (click a column to sort).")
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"revenue": st.column_config.NumberColumn("revenue (BRL)", format="%.2f"),
                                "late_pct": st.column_config.NumberColumn("late %", format="%.1f")})

    seller = st.selectbox("Seller", table["seller_id"])
    hist = numeric(query("SELECT * FROM analytics.seller_monthly WHERE seller_id = %s ORDER BY month", (seller,)))
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Monthly revenue")
        fig = px.bar(hist, x="month", y="revenue", color_discrete_sequence=[BLUE], hover_data=["orders"])
        st.plotly_chart(style(fig, "BRL"), width="stretch")
    with c2:
        st.subheader("Average rating")
        fig = px.line(hist, x="month", y="avg_rating", markers=True, color_discrete_sequence=[BLUE],
                      hover_data=["orders", "late_orders"])
        fig.update_traces(line_width=2, marker_size=8).update_yaxes(range=[0.8, 5.2])
        st.plotly_chart(style(fig, "Stars"), width="stretch")

    st.subheader("Location history (SCD Type 2)")
    st.dataframe(query("SELECT city, state, effective_start, effective_end, is_current FROM dw.dim_seller "
                       "WHERE seller_id = %s ORDER BY effective_start", (seller,)), hide_index=True)


@st.cache_data(ttl=3600, show_spinner=False)
def insight(seller_id: str, start: date, end: date) -> dict:
    conn = connect(os.getenv("WAREHOUSE", "local"))
    try:
        return explain_seller(seller_id, start, end, conn=conn)
    finally:
        conn.close()


def ai_insight():
    st.title("AI insight")
    st.caption("Why did a seller's rating change? The answer may only use the metrics shown beside it; "
               "answers with numbers not found in the data are replaced by a warning.")
    sellers = query("SELECT DISTINCT seller_id FROM analytics.top_sellers_monthly ORDER BY seller_id")["seller_id"]
    c1, c2, c3 = st.columns([2, 1, 1])
    seller = c1.selectbox("Seller (top-10 sellers of any month)", sellers)
    start = c2.date_input("From", date(2018, 1, 1), min_value=date(2016, 9, 1), max_value=date(2018, 10, 31))
    end = c3.date_input("To", date(2018, 8, 31), min_value=date(2016, 9, 1), max_value=date(2018, 10, 31))
    if not st.button("Explain", type="primary"):
        return
    with st.spinner("Reading the metrics and reviews (local model, up to a minute)..."):
        result = insight(seller, start, end)

    left, right = st.columns(2)
    with left:
        st.subheader("Metrics")
        st.dataframe(pd.DataFrame(result["metrics"]).drop(columns="category"), hide_index=True,
                     column_config={"late_pct": "late %", "avg_delay_vs_estimate_days": "days vs estimate",
                                    "avg_rating": "rating"})
        if result["metrics"]:
            st.caption(f"Category: {result['metrics'][0]['category']} · {result['review_count']} low-star reviews used")
    with right:
        st.subheader("Explanation")
        if result["warning"]:
            st.warning(result["warning"])
        if result["answer"]:
            st.markdown(result["answer"])
        if result.get("rejected_answer"):
            with st.expander("Rejected AI text"):
                st.text(result["rejected_answer"])
        if result.get("llm"):
            st.caption(f"{result['llm']['model']} · {result['llm']['seconds']} s")


st.set_page_config(page_title="Olist seller performance", layout="wide")
st.navigation([st.Page(overview, title="Overview", icon="📊"),
               st.Page(scorecard, title="Seller scorecard", icon="🏪"),
               st.Page(ai_insight, title="AI insight", icon="💬")]).run()
