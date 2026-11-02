"""Interactive Repair and Overhaul TAT dashboard.

    streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tat_analytics import config as C  # noqa: E402
from tat_analytics import kpis as K  # noqa: E402

BLUE, ORANGE, INK_2, GRID = "#2a78d6", "#eb6834", "#52514e", "#e6e5e1"

st.set_page_config(page_title="Repair TAT Analytics", layout="wide")


@st.cache_data
def load():
    fact = C.PROCESSED_DIR / "fact_repair_orders.csv"
    if not fact.exists():
        import run_pipeline

        run_pipeline.main()
    f = pd.read_csv(fact, parse_dates=["received_ts", "shipped_ts"])
    ev = pd.read_csv(C.PROCESSED_DIR / "fact_stage_events.csv", parse_dates=["start_ts", "end_ts"])
    at_risk = pd.read_csv(C.OUTPUT_DIR / "at_risk_open_orders.csv")
    return f, ev, at_risk


def style(fig, height=360):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white",
        font=dict(color=INK_2), showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, title=None)
    fig.update_yaxes(gridcolor=GRID, title=None)
    return fig


f_all, ev_all, at_risk_all = load()

st.title("Aerospace Repair and Overhaul: Turnaround Time Analytics")
st.caption("Synthetic data for portfolio demonstration. Data as of " + C.DATA_CUTOFF)

c1, c2, c3, c4 = st.columns(4)
sites = c1.multiselect("Site", sorted(f_all.site.unique()), default=sorted(f_all.site.unique()))
fams = c2.multiselect("Part family", sorted(f_all.part_family.unique()), default=sorted(f_all.part_family.unique()))
prios = c3.multiselect("Priority", ["AOG", "Critical", "Routine"], default=["AOG", "Critical", "Routine"])
min_d, max_d = f_all.received_ts.min().date(), f_all.received_ts.max().date()
dates = c4.date_input("Received between", (min_d, max_d), min_value=min_d, max_value=max_d)

mask = f_all.site.isin(sites) & f_all.part_family.isin(fams) & f_all.priority.isin(prios)
if isinstance(dates, tuple) and len(dates) == 2:
    mask &= f_all.received_ts.dt.date.between(dates[0], dates[1])
f = f_all[mask]
ev = ev_all[ev_all.order_id.isin(f.order_id)]

if K.closed(f).empty:
    st.warning("No closed orders match these filters.")
    st.stop()

h = K.headline(f)
m = st.columns(5)
m[0].metric("On-time delivery", f"{h['on_time_pct']:.1%}", f"{h['on_time_pct'] - C.TARGETS['on_time_pct']:+.1%} vs 85% target")
m[1].metric("Avg TAT (days)", h["avg_tat_days"])
m[2].metric("First-pass test yield", f"{h['first_pass_yield']:.1%}")
m[3].metric("Penalty exposure", f"${h['total_penalty_usd']:,.0f}")
m[4].metric("Open orders past contract", h["open_past_contract"])

tab1, tab2, tab3, tab4 = st.tabs(["Performance", "Bottlenecks", "At-risk open orders", "What-if scenarios"])

with tab1:
    a, b = st.columns(2)
    t = K.monthly_trend(f, min_orders=10)
    fig = px.line(t, x="month", y="on_time_pct", markers=True, title="On-time % by ship month")
    fig.update_traces(line=dict(color=BLUE, width=2), hovertemplate="%{x}<br>On-time: %{y:.1%}<extra></extra>")
    fig.add_hline(y=C.TARGETS["on_time_pct"], line_dash="dash", line_color=INK_2, annotation_text="Target 85%")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    a.plotly_chart(style(fig), use_container_width=True)

    s = K.by_dimension(f, "site")
    fig = px.bar(s, x="on_time_pct", y="site", orientation="h", title="On-time % by site", text="on_time_pct")
    fig.update_traces(marker_color=BLUE, texttemplate="%{text:.0%}", hovertemplate="%{y}<br>On-time: %{x:.1%}<extra></extra>")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    b.plotly_chart(style(fig), use_container_width=True)

    st.dataframe(K.by_dimension(f, "part_family"), use_container_width=True, hide_index=True)

with tab2:
    a, b = st.columns(2)
    bn = K.stage_bottleneck(ev, f)
    colors = [ORANGE if v == bn.avg_days.max() else BLUE for v in bn.avg_days]
    fig = px.bar(bn, x="avg_days", y="stage", orientation="h", title="Average days per stage (orange = biggest bottleneck)",
                 text="avg_days", custom_data=["share_of_tat", "p90_days"])
    fig.update_traces(marker_color=colors, texttemplate="%{text:.1f} d",
                      hovertemplate="%{y}<br>Avg: %{x:.1f} days<br>P90: %{customdata[1]:.1f} days<br>Share of TAT: %{customdata[0]:.0%}<extra></extra>")
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(C.STAGES)))
    a.plotly_chart(style(fig, 420), use_container_width=True)

    p = K.delay_pareto(f)
    fig = px.bar(p, x="primary_delay_reason", y="late_orders", title="Primary reason for late orders",
                 text="late_orders", custom_data=["cum_pct", "penalty_usd"])
    fig.update_traces(marker_color=BLUE,
                      hovertemplate="%{x}<br>Late orders: %{y}<br>Cumulative: %{customdata[0]:.0%}<br>Penalty: $%{customdata[1]:,.0f}<extra></extra>")
    b.plotly_chart(style(fig, 420), use_container_width=True)

    st.subheader("Part numbers with the most parts-wait days")
    st.dataframe(K.top_shortage_parts(ev, f), use_container_width=True, hide_index=True)

with tab3:
    ar = at_risk_all[at_risk_all.order_id.isin(f.order_id)]
    st.write(f"**{(ar.risk_band == 'High').sum()}** open orders are High risk of missing contracted TAT. "
             "Scores come from a logistic regression trained on intake attributes only.")
    band = st.radio("Risk band", ["High", "Medium", "Low", "All"], horizontal=True)
    view = ar if band == "All" else ar[ar.risk_band == band]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Download as CSV", view.to_csv(index=False), "at_risk_open_orders.csv")

with tab4:
    st.write("Estimate the impact of improvement initiatives on the selected orders.")
    a, b, c = st.columns(3)
    pw = a.slider("Cut parts-wait time by", 0, 100, 30, 5, format="%d%%") / 100
    qa = b.slider("Cut quote-approval time by", 0, 100, 50, 5, format="%d%%") / 100
    rw = c.slider("Cut rework time by", 0, 100, 25, 5, format="%d%%") / 100
    r = K.what_if(f, ev, pw, qa, rw)
    x = st.columns(3)
    x[0].metric("On-time %", f"{r['scenario_on_time_pct']:.1%}", f"{r['scenario_on_time_pct'] - r['baseline_on_time_pct']:+.1%}")
    x[1].metric("Avg TAT (days)", r["scenario_avg_tat"], f"{r['scenario_avg_tat'] - r['baseline_avg_tat']:+.1f}", delta_color="inverse")
    x[2].metric("Penalty savings", f"${r['penalty_savings_usd']:,.0f}")
    st.caption("Assumes removed wait time does not shift to another stage. Validate with a pilot before committing.")
