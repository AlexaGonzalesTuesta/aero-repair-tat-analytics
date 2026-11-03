import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tat_analytics import config as C  # noqa: E402
from tat_analytics import kpis as K  # noqa: E402

BLUE, ORANGE, INK_2, GRID = "#2a78d6", "#eb6834", "#8a8984", "rgba(128,128,128,0.25)"
GITHUB_URL = "https://github.com/AlexaGonzalesTuesta/aero-repair-tat-analytics"
LINKEDIN_URL = "https://www.linkedin.com/in/alexa-gonzales-tuesta/"

st.set_page_config(page_title="Repair TAT Analytics", layout="wide")


SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshot"


@st.cache_data
def load():
    """Read the processed tables. A fresh pipeline run (data/processed) wins; otherwise the
    app uses the bundled snapshot, so a cold start on the free host only reads files and
    never re-runs the pipeline while a visitor waits."""
    def path(name):
        fresh = C.PROCESSED_DIR / name
        return fresh if fresh.exists() else SNAPSHOT_DIR / f"{name}.gz"

    f = pd.read_csv(path("fact_repair_orders.csv"), parse_dates=["received_ts", "shipped_ts"])
    ev = pd.read_csv(path("fact_stage_events.csv"), parse_dates=["start_ts", "end_ts"])
    at_risk = pd.read_csv(C.OUTPUT_DIR / "at_risk_open_orders.csv")
    return f, ev, at_risk


def style(fig, height=360):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, title=None)
    fig.update_yaxes(gridcolor=GRID, title=None)
    return fig


f_all, ev_all, at_risk_all = load()

st.title("Aerospace Repair and Overhaul: Turnaround Time Analytics")
st.markdown(
    f"Created by **Alexa Gonzales Tuesta**  |  [GitHub repository]({GITHUB_URL})  |  [LinkedIn]({LINKEDIN_URL})"
)

st.markdown(
    """
**The problem.** Aerospace repair stations promise customers a contracted turnaround time (TAT) for every
part they repair. When a part ships late, an aircraft can sit on the ground, the company pays contract
penalties, and customer trust drops. Leaders usually find out after the fact, from manual reports, without
knowing which step of the repair process caused the delay.

**What this tool does.** I built this dashboard to turn repair order data into decisions. It shows how often
repairs ship on time, where time is lost in the repair process, which open orders are likely to be late
before it happens, and how much money each improvement idea could save.
"""
)

with st.expander("How to use this dashboard", expanded=True):
    st.markdown(
        """
1. **Filter** by site, part family, priority (AOG means aircraft on ground, the most urgent), or date range. Every number and chart updates.
2. **Performance:** check on-time delivery against the 85% target and compare sites.
3. **Bottlenecks:** find the repair stage that adds the most days, and the most common reason orders run late.
4. **At-risk open orders:** see which orders still in progress are most likely to miss their deadline, so they can be expedited today.
5. **What-if scenarios:** move the sliders to estimate how much on-time delivery and penalty cost would improve with each fix.

*Data is synthetic, built to reflect real repair station challenges such as parts shortages, customer quote delays, and test failures. Data as of """ + C.DATA_CUTOFF + """.*
"""
    )

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
    st.caption("Is the repair station keeping its promises? Points below the dashed line mean the month missed the 85% on-time target.")
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
    st.caption("Where does repair time go? The orange bar is the biggest bottleneck. The chart on the right ranks the main causes of late orders, so you know what to fix first.")
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
    st.caption("Which orders need attention today? A model trained on past orders scores every open order from 0 to 1 for "
               "its chance of shipping late, using only what is known when the part arrives.")
    st.write(f"**{(ar.risk_band == 'High').sum()}** open orders are High risk of missing their contracted turnaround time. "
             "A negative value in days_to_contract_due means the order is already past its deadline.")
    band = st.radio("Risk band", ["High", "Medium", "Low", "All"], horizontal=True)
    view = ar if band == "All" else ar[ar.risk_band == band]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Download as CSV", view.to_csv(index=False), "at_risk_open_orders.csv")

with tab4:
    st.caption("Is a fix worth funding? Each slider represents an improvement initiative. Move them to estimate the impact on the orders you filtered.")
    st.markdown(
        "- **Parts wait:** keep safety stock or add a second supplier for parts that are often short\n"
        "- **Quote approval:** agree on pre-approved repair cost limits with customers so routine repairs skip the wait\n"
        "- **Rework:** add a standard checklist before testing so fewer parts fail and need repair again"
    )
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

st.divider()
st.caption(f"Built by Alexa Gonzales Tuesta with Python, pandas, scikit-learn, and Streamlit. Source code, requirements document, and process maps: [GitHub]({GITHUB_URL})")
