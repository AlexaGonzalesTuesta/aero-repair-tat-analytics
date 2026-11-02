"""Clean, validate, and model raw repair data into a Power BI-ready star schema.

Outputs (data/processed/):
    fact_repair_orders.csv   one row per repair order
    fact_stage_events.csv    one row per stage visit (includes rework attempts)
    dim_site.csv, dim_part.csv, dim_date.csv
    data_quality_report.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as C


def load_raw():
    orders = pd.read_csv(C.RAW_DIR / "repair_orders.csv", parse_dates=["received_ts", "shipped_ts"])
    events = pd.read_csv(C.RAW_DIR / "stage_events.csv", parse_dates=["start_ts", "end_ts"])
    catalog = pd.read_csv(C.RAW_DIR / "part_catalog.csv")
    return orders, events, catalog


def clean(orders: pd.DataFrame, events: pd.DataFrame):
    """Apply data quality rules. Returns cleaned frames plus a check log."""
    log = []
    o = orders.copy()
    e = events.copy()

    # Rule 1: one row per order_id
    # Keyed on order_id because duplicates can differ in formatting (e.g. site casing).
    n_dupes = int(o.order_id.duplicated().sum())
    o = o.drop_duplicates(subset="order_id", keep="first").reset_index(drop=True)
    log.append({"check": "Duplicate order rows removed", "issues_found": n_dupes})
    still_dup = int(o.order_id.duplicated().sum())
    log.append({"check": "order_id unique after cleaning", "issues_found": still_dup})

    # Rule 2: standardize site names to the canonical list
    canonical = {s.lower(): s for s in C.SITES}
    raw_sites = o.site.astype(str)
    fixed = raw_sites.str.strip().str.lower().map(canonical)
    n_site = int((fixed != raw_sites).sum())
    o["site"] = fixed
    log.append({"check": "Site labels standardized (case / whitespace)", "issues_found": n_site})
    log.append({"check": "Unmapped site labels remaining", "issues_found": int(o.site.isna().sum())})

    # Rule 3: missing priority -> impute Routine and flag it for follow-up
    missing_prio = o.priority.isna()
    o["priority_imputed"] = missing_prio
    o.loc[missing_prio, "priority"] = "Routine"
    log.append({"check": "Missing priority imputed as Routine (flagged)", "issues_found": int(missing_prio.sum())})

    # Rule 4: stage end before start -> repair from the next stage's start time.
    # Stages are contiguous, so the next stage start is the true end.
    e = e.sort_values(["order_id", "start_ts"]).reset_index(drop=True)
    bad = e.end_ts.notna() & (e.end_ts < e.start_ts)
    next_start = e.groupby("order_id").start_ts.shift(-1)
    shipped = e.order_id.map(o.set_index("order_id").shipped_ts)
    repair_value = next_start.fillna(shipped)
    e.loc[bad, "end_ts"] = repair_value[bad]
    log.append({"check": "Stage end-before-start timestamps repaired", "issues_found": int(bad.sum())})
    still_bad = int((e.end_ts.notna() & (e.end_ts < e.start_ts)).sum())
    log.append({"check": "Negative stage durations remaining", "issues_found": still_bad})

    # Rule 5: every event must belong to a known order
    orphan = int((~e.order_id.isin(o.order_id)).sum())
    log.append({"check": "Orphan stage events (no matching order)", "issues_found": orphan})

    return o, e, log


def build_star_schema(o: pd.DataFrame, e: pd.DataFrame, catalog: pd.DataFrame):
    cutoff = pd.Timestamp(C.DATA_CUTOFF)
    f = o.copy()
    f["received_date"] = f.received_ts.dt.normalize()
    f["shipped_date"] = f.shipped_ts.dt.normalize()
    f["tat_days"] = (f.shipped_ts - f.received_ts).dt.total_seconds() / 86400
    f["age_days"] = np.where(
        f.status == "Open", (cutoff - f.received_ts).dt.total_seconds() / 86400, f.tat_days
    )
    f["days_late"] = (f.tat_days - f.contract_tat_days).clip(lower=0)
    f["is_late"] = np.where(f.status == "Closed", f.tat_days > f.contract_tat_days, np.nan)
    f["on_time"] = np.where(f.status == "Closed", f.tat_days <= f.contract_tat_days, np.nan)
    f["penalty_usd"] = (f.days_late.fillna(0) * f.penalty_per_day_usd).round(2)
    f["open_past_contract"] = (f.status == "Open") & (f.age_days > f.contract_tat_days)

    ev = e.copy()
    ev["duration_days"] = (ev.end_ts - ev.start_ts).dt.total_seconds() / 86400
    ev["stage_sequence"] = ev.stage.map({s: i + 1 for i, s in enumerate(C.STAGES)})
    ev["is_rework"] = ev.attempt > 1
    ev = ev.merge(f[["order_id", "site", "part_family", "priority"]], on="order_id", how="left")

    first_pass = (
        ev[ev.stage == "Test"].groupby("order_id").attempt.max().eq(1).rename("first_pass_test")
    )
    f = f.merge(first_pass, on="order_id", how="left")

    dim_site = pd.DataFrame(
        [{"site": s, "parts_shortage_rate_assumption": v["parts_shortage_rate"]} for s, v in C.SITES.items()]
    )
    dim_part = catalog.merge(
        pd.DataFrame(
            [
                {"part_family": k, "contract_tat_days": v["contract_tat"], "penalty_per_day_usd": v["penalty_per_day"]}
                for k, v in C.PART_FAMILIES.items()
            ]
        ),
        on="part_family",
    )
    dates = pd.date_range(C.START_DATE, cutoff, freq="D")
    dim_date = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "quarter": "Q" + dates.quarter.astype(str),
            "month": dates.month,
            "month_name": dates.strftime("%b"),
            "year_month": dates.strftime("%Y-%m"),
            "iso_week": dates.isocalendar().week.values,
        }
    )
    return f, ev, dim_site, dim_part, dim_date


def run():
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    orders, events, catalog = load_raw()
    o, e, log = clean(orders, events)
    f, ev, dim_site, dim_part, dim_date = build_star_schema(o, e, catalog)

    f.to_csv(C.PROCESSED_DIR / "fact_repair_orders.csv", index=False)
    ev.to_csv(C.PROCESSED_DIR / "fact_stage_events.csv", index=False)
    dim_site.to_csv(C.PROCESSED_DIR / "dim_site.csv", index=False)
    dim_part.to_csv(C.PROCESSED_DIR / "dim_part.csv", index=False)
    dim_date.to_csv(C.PROCESSED_DIR / "dim_date.csv", index=False)

    report = {
        "raw_order_rows": int(len(orders)),
        "clean_orders": int(len(f)),
        "stage_events": int(len(ev)),
        "checks": log,
        "post_clean_checks_passed": all(
            c["issues_found"] == 0
            for c in log
            if c["check"].startswith(("order_id unique", "Unmapped", "Negative", "Orphan"))
        ),
    }
    (C.PROCESSED_DIR / "data_quality_report.json").write_text(json.dumps(report, indent=2))
    print(f"Pipeline complete: {len(f):,} clean orders, {len(ev):,} stage events")
    for c in log:
        print(f"  [{c['issues_found']:>4}] {c['check']}")
    return f, ev


if __name__ == "__main__":
    run()
