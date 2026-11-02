"""Automatically generate the weekly stakeholder status report (Markdown).

Replaces a manual process of pulling numbers into slides every week. Run it on
a schedule (GitHub Actions, Power Automate, or Task Scheduler) and the report
is always current.
"""
from __future__ import annotations

import json

import pandas as pd

from . import config as C
from . import kpis as K


def _pct(x: float) -> str:
    return f"{x:.1%}"


def _usd(x: float) -> str:
    return f"${x:,.0f}"


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def scenarios(f, ev) -> pd.DataFrame:
    rows = [
        ("A. Safety stock + dual-sourcing for chronic shortage parts (parts wait -30%)", dict(parts_wait_reduction=0.30)),
        ("B. Pre-approved not-to-exceed repair limits with customers (quote wait -50%)", dict(quote_reduction=0.50)),
        ("C. Standard work + test checklist to cut rework (rework time -25%)", dict(rework_reduction=0.25)),
        ("A + B + C combined", dict(parts_wait_reduction=0.30, quote_reduction=0.50, rework_reduction=0.25)),
    ]
    out = []
    for name, kw in rows:
        r = K.what_if(f, ev, **kw)
        out.append(
            {
                "Initiative": name,
                "On-time % (now -> scenario)": f"{_pct(r['baseline_on_time_pct'])} -> {_pct(r['scenario_on_time_pct'])}",
                "Avg TAT days": f"{r['baseline_avg_tat']} -> {r['scenario_avg_tat']}",
                "Penalty savings": _usd(r["penalty_savings_usd"]),
            }
        )
    return pd.DataFrame(out)


def build(f, ev, metrics: dict, at_risk: pd.DataFrame) -> str:
    h = K.headline(f)
    dq = json.loads((C.PROCESSED_DIR / "data_quality_report.json").read_text())
    bottleneck = K.stage_bottleneck(ev, f).sort_values("avg_days", ascending=False).iloc[0]
    pareto = K.delay_pareto(f)
    sites = K.by_dimension(f, "site")
    worst_site = sites.iloc[0]
    trend = K.monthly_trend(f)
    last3, prev3 = trend.tail(3).on_time_pct.mean(), trend.iloc[-6:-3].on_time_pct.mean()
    sc = scenarios(f, ev)
    combined = K.what_if(f, ev, parts_wait_reduction=0.30, quote_reduction=0.50, rework_reduction=0.25)

    kpi = pd.DataFrame(
        [
            {"KPI": "On-time delivery", "Actual": _pct(h["on_time_pct"]), "Target": _pct(C.TARGETS["on_time_pct"]),
             "Status": K.rag(h["on_time_pct"], C.TARGETS["on_time_pct"])},
            {"KPI": "First-pass test yield", "Actual": _pct(h["first_pass_yield"]), "Target": _pct(C.TARGETS["first_pass_yield"]),
             "Status": K.rag(h["first_pass_yield"], C.TARGETS["first_pass_yield"])},
            {"KPI": "Avg TAT / contracted TAT", "Actual": f"{h['avg_tat_vs_contract']:.2f}x", "Target": "1.00x or less",
             "Status": K.rag(h["avg_tat_vs_contract"], C.TARGETS["avg_tat_vs_contract"], higher_is_better=False)},
            {"KPI": "Late-delivery penalty exposure", "Actual": _usd(h["total_penalty_usd"]), "Target": "Trending down", "Status": "Info"},
            {"KPI": "Open orders already past contract", "Actual": str(h["open_past_contract"]), "Target": "0", "Status": "Info"},
        ]
    )
    high = at_risk[at_risk.risk_band == "High"].head(10)

    md = f"""# Repair and Overhaul TAT: Weekly Status Report

**Data as of:** {C.DATA_CUTOFF}  |  **Scope:** {h['closed_orders']:,} closed and {h['open_orders']:,} open repair orders across {len(C.SITES)} sites
*Synthetic data for portfolio demonstration. Generated automatically by `run_pipeline.py`.*

## Executive summary
- On-time delivery is **{_pct(h['on_time_pct'])}** against an 85% target. The last 3 months averaged {_pct(last3)} vs {_pct(prev3)} in the 3 months before.
- **{bottleneck.stage}** is the largest bottleneck at {bottleneck.avg_days:.1f} days per order ({bottleneck.share_of_tat:.0%} of total TAT).
- **{pareto.iloc[0].primary_delay_reason}** is the top cause of late orders ({pareto.iloc[0].late_orders} orders, {_pct(pareto.iloc[0].late_orders / pareto.late_orders.sum())} of all late orders).
- **{worst_site.site}** has the lowest on-time rate ({_pct(worst_site.on_time_pct)}).
- Combining the three initiatives below is estimated to lift on-time delivery to **{_pct(combined['scenario_on_time_pct'])}** and avoid **{_usd(combined['penalty_savings_usd'])}** in penalties over the same period.

## KPI scorecard
{_table(kpi)}

## Recommended initiatives (what-if estimates)
{_table(sc)}

## Open orders at highest risk of missing contract (top 10)
Risk model ROC AUC on held-out recent orders: **{metrics['roc_auc']}** (top 10% of scores are {metrics['lift_top_10pct']}x more likely to be late than average).

{_table(high[['order_id', 'part_family', 'site', 'priority', 'current_stage', 'age_days', 'days_to_contract_due', 'late_risk']])}

**Action:** review these orders in the daily production meeting; expedite parts or escalate quotes where the order is waiting.

## Data quality
{_table(pd.DataFrame(dq['checks']).rename(columns={'check': 'Check', 'issues_found': 'Issues found / fixed'}))}

All post-cleaning integrity checks passed: **{dq['post_clean_checks_passed']}**

## Next steps
1. Validate stage timestamp definitions with repair station leads before using results for decisions.
2. Pilot initiative A at {worst_site.site}; track on-time % weekly against this baseline.
3. Publish the star schema to Power BI and schedule this report weekly.

## Assumptions and lessons learned
- Contracted TAT and penalty rates are set per part family in `tat_analytics/config.py`.
- What-if estimates assume removed wait time does not shift to another stage; real results will be lower and should be confirmed in a pilot.
- Data entry issues (duplicates, inconsistent site names, impossible timestamps) were common enough that automated quality checks should run before every refresh.
"""
    return md


def run(f, ev, metrics, at_risk):
    md = build(f, ev, metrics, at_risk)
    path = C.OUTPUT_DIR / "weekly_status_report.md"
    path.write_text(md)
    print(f"Stakeholder report -> {path}")
    return path
