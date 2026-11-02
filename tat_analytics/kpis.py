"""KPI, bottleneck, and what-if scenario calculations.

Every function takes the processed fact tables and returns a DataFrame or dict,
so the same logic powers the dashboard, the automated report, and the tests.
"""
from __future__ import annotations

import pandas as pd

from . import config as C


def closed(f: pd.DataFrame) -> pd.DataFrame:
    return f[f.status == "Closed"]


def headline(f: pd.DataFrame) -> dict:
    c = closed(f)
    op = f[f.status == "Open"]
    return {
        "closed_orders": int(len(c)),
        "open_orders": int(len(op)),
        "avg_tat_days": round(float(c.tat_days.mean()), 1),
        "median_tat_days": round(float(c.tat_days.median()), 1),
        "on_time_pct": round(float(c.on_time.astype(float).mean()), 3),
        "first_pass_yield": round(float(c.first_pass_test.astype(float).mean()), 3),
        "avg_tat_vs_contract": round(float((c.tat_days / c.contract_tat_days).mean()), 2),
        "total_penalty_usd": round(float(c.penalty_usd.sum()), 0),
        "open_past_contract": int(op.open_past_contract.sum()),
    }


def by_dimension(f: pd.DataFrame, col: str) -> pd.DataFrame:
    c = closed(f)
    out = (
        c.groupby(col)
        .agg(
            orders=("order_id", "count"),
            avg_tat_days=("tat_days", "mean"),
            on_time_pct=("on_time", lambda s: s.astype(float).mean()),
            penalty_usd=("penalty_usd", "sum"),
        )
        .reset_index()
        .sort_values("on_time_pct")
    )
    return out.round({"avg_tat_days": 1, "on_time_pct": 3, "penalty_usd": 0})


def monthly_trend(f: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    """Monthly KPIs by ship month. Months with too few orders are dropped to avoid noisy points."""
    c = closed(f).copy()
    c["month"] = c.shipped_ts.dt.to_period("M").astype(str)
    out = (
        c.groupby("month")
        .agg(
            orders=("order_id", "count"),
            avg_tat_days=("tat_days", "mean"),
            on_time_pct=("on_time", lambda s: s.astype(float).mean()),
            penalty_usd=("penalty_usd", "sum"),
        )
        .reset_index()
    )
    out = out[out.orders >= min_orders]
    return out.round({"avg_tat_days": 1, "on_time_pct": 3, "penalty_usd": 0})


def stage_bottleneck(ev: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """Average days each closed order spends in each stage (rework included)."""
    closed_ids = set(closed(f).order_id)
    e = ev[ev.order_id.isin(closed_ids)]
    per_order = e.groupby(["order_id", "stage"]).duration_days.sum().unstack(fill_value=0)
    per_order = per_order.reindex(columns=C.STAGES, fill_value=0)
    out = pd.DataFrame(
        {
            "stage": C.STAGES,
            "avg_days": per_order.mean().values,
            "p90_days": per_order.quantile(0.9).values,
        }
    )
    out["share_of_tat"] = out.avg_days / out.avg_days.sum()
    return out.round({"avg_days": 2, "p90_days": 2, "share_of_tat": 3})


def delay_pareto(f: pd.DataFrame) -> pd.DataFrame:
    late = closed(f)
    late = late[late.is_late.astype(bool)]
    out = (
        late.groupby("primary_delay_reason")
        .agg(late_orders=("order_id", "count"), penalty_usd=("penalty_usd", "sum"))
        .reset_index()
        .sort_values("late_orders", ascending=False)
    )
    out["cum_pct"] = out.late_orders.cumsum() / out.late_orders.sum()
    return out.round({"penalty_usd": 0, "cum_pct": 3})


def top_shortage_parts(ev: pd.DataFrame, f: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    wait = ev[ev.stage == "Awaiting Parts"].merge(f[["order_id", "part_number"]], on="order_id")
    out = (
        wait.groupby("part_number")
        .agg(total_wait_days=("duration_days", "sum"), orders=("order_id", "nunique"), avg_wait_days=("duration_days", "mean"))
        .reset_index()
        .sort_values("total_wait_days", ascending=False)
        .head(n)
    )
    return out.round(1)


def what_if(
    f: pd.DataFrame,
    ev: pd.DataFrame,
    parts_wait_reduction: float = 0.0,
    quote_reduction: float = 0.0,
    rework_reduction: float = 0.0,
) -> dict:
    """Re-estimate TAT if a share of waiting / rework time were removed.

    parts_wait_reduction: e.g. 0.30 = safety stock / dual-sourcing cuts parts wait by 30%
    quote_reduction:      e.g. 0.50 = pre-approved repair limits cut quote wait by 50%
    rework_reduction:     e.g. 0.25 = better first-pass test practices cut rework time by 25%
    """
    for name, v in [("parts_wait_reduction", parts_wait_reduction), ("quote_reduction", quote_reduction), ("rework_reduction", rework_reduction)]:
        if not 0 <= v <= 1:
            raise ValueError(f"{name} must be between 0 and 1")

    c = closed(f)
    e = ev[ev.order_id.isin(c.order_id)]
    saved = pd.Series(0.0, index=e.index)
    saved += (e.stage == "Awaiting Parts") * e.duration_days * parts_wait_reduction
    saved += (e.stage == "Quote Approval") * e.duration_days * quote_reduction
    saved += e.is_rework * e.duration_days * rework_reduction
    saved_per_order = saved.groupby(e.order_id).sum()

    s = c.set_index("order_id").copy()
    s["new_tat"] = s.tat_days - saved_per_order.reindex(s.index).fillna(0)
    s["new_days_late"] = (s.new_tat - s.contract_tat_days).clip(lower=0)
    s["new_penalty"] = s.new_days_late * s.penalty_per_day_usd

    base_pen = float(s.penalty_usd.sum())
    new_pen = float(s.new_penalty.sum())
    return {
        "baseline_on_time_pct": round(float((s.tat_days <= s.contract_tat_days).mean()), 3),
        "scenario_on_time_pct": round(float((s.new_tat <= s.contract_tat_days).mean()), 3),
        "baseline_avg_tat": round(float(s.tat_days.mean()), 1),
        "scenario_avg_tat": round(float(s.new_tat.mean()), 1),
        "baseline_penalty_usd": round(base_pen, 0),
        "scenario_penalty_usd": round(new_pen, 0),
        "penalty_savings_usd": round(base_pen - new_pen, 0),
    }


def rag(value: float, target: float, higher_is_better: bool = True, amber_band: float = 0.05) -> str:
    """Red / Amber / Green status against a target."""
    gap = (value - target) if higher_is_better else (target - value)
    if gap >= 0:
        return "Green"
    if gap >= -amber_band * abs(target):
        return "Amber"
    return "Red"
