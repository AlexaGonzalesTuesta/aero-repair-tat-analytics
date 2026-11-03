"""Build the static dashboard published on GitHub Pages.

Reads the processed tables from run_pipeline.py, exports one compact record per repair
order, and writes _site/index.html. Every number on the page is recomputed in the
browser from those records, so filters and what-if sliders work with no server.

Run:  python run_pipeline.py  then  python site/build_site.py
The build fails if the exported records do not reproduce the Python KPIs exactly.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tat_analytics import config as C  # noqa: E402
from tat_analytics import kpis as K  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "_site"


def load():
    f = pd.read_csv(C.PROCESSED_DIR / "fact_repair_orders.csv", parse_dates=["received_ts", "shipped_ts"])
    ev = pd.read_csv(C.PROCESSED_DIR / "fact_stage_events.csv", parse_dates=["start_ts", "end_ts"])
    at_risk = pd.read_csv(C.OUTPUT_DIR / "at_risk_open_orders.csv")
    return f, ev, at_risk


def records(f, ev):
    """One row per order, columnar to keep the page small."""
    stage_days = (ev.groupby(["order_id", "stage"]).duration_days.sum().unstack(fill_value=0)
                  .reindex(columns=C.STAGES, fill_value=0))
    ap = ev[ev.stage == "Awaiting Parts"].groupby("order_id").size()
    rework = ev[ev.is_rework.astype(bool)].groupby("order_id").duration_days.sum()
    has_events = set(ev.order_id)

    def num(s, nd=6):
        return [None if pd.isna(v) else round(float(v), nd) for v in s]

    fpt = f.first_pass_test.map({True: 1, False: 0, "True": 1, "False": 0})
    return {
        "id": f.order_id.tolist(),
        "pn": f.part_number.tolist(),
        "fam": f.part_family.tolist(),
        "site": f.site.tolist(),
        "prio": f.priority.tolist(),
        "rec": f.received_ts.dt.strftime("%Y-%m-%d").tolist(),
        "shipM": [s.strftime("%Y-%m") if not pd.isna(s) else "" for s in f.shipped_ts],
        "closed": (f.status == "Closed").astype(int).tolist(),
        "tat": num(f.tat_days),
        "ctat": f.contract_tat_days.astype(int).tolist(),
        "ppd": f.penalty_per_day_usd.astype(int).tolist(),
        "on": num(f.on_time, 0),
        "fpt": [None if pd.isna(v) else int(v) for v in fpt],
        "pen": num(f.penalty_usd, 6),
        "late": num(f.is_late, 0),
        "reason": [None if pd.isna(v) else v for v in f.primary_delay_reason],
        "opc": f.open_past_contract.astype(int).tolist(),
        "ev": [1 if o in has_events else 0 for o in f.order_id],
        "stg": [[round(float(x), 6) for x in stage_days.loc[o]] if o in stage_days.index else [0] * len(C.STAGES)
                for o in f.order_id],
        "apn": [int(ap.get(o, 0)) for o in f.order_id],
        "rw": [round(float(rework.get(o, 0.0)), 6) for o in f.order_id],
    }


def check(rec, f):
    """Recompute the headline KPIs from the exported records and compare with kpis.py."""
    d = pd.DataFrame({k: rec[k] for k in ("closed", "tat", "on", "fpt", "pen", "opc")})
    c = d[d.closed == 1]
    h = K.headline(f)
    mine = {
        "closed_orders": len(c),
        "avg_tat_days": round(float(c.tat.mean()), 1),
        "on_time_pct": round(float(c.on.mean()), 3),
        "first_pass_yield": round(float(c.fpt.mean()), 3),
        "total_penalty_usd": round(float(c.pen.sum()), 0),
        "open_past_contract": int(d[d.closed == 0].opc.sum()),
    }
    bad = {k: (v, h[k]) for k, v in mine.items() if not np.isclose(v, h[k])}
    if bad:
        raise SystemExit(f"Exported records do not match kpis.py: {bad}")
    return h


def main():
    f, ev, at_risk = load()
    rec = records(f, ev)
    h = check(rec, f)
    config = {
        "stages": C.STAGES,
        "target": C.TARGETS["on_time_pct"],
        "cutoff": C.DATA_CUTOFF,
        "sites": sorted(f.site.unique()),
        "families": sorted(f.part_family.unique()),
        "priorities": ["AOG", "Critical", "Routine"],
    }
    risk_cols = ["order_id", "part_number", "part_family", "site", "customer_type", "priority", "current_stage",
                 "age_days", "contract_tat_days", "days_to_contract_due", "late_risk", "risk_band"]
    risk = at_risk[risk_cols].to_dict(orient="split")
    risk.pop("index", None)

    html = (SITE / "template.html").read_text(encoding="utf-8")
    html = (html.replace("/*__DATA__*/null", json.dumps(rec, separators=(",", ":")))
                .replace("/*__CONFIG__*/null", json.dumps(config, separators=(",", ":")))
                .replace("/*__RISK__*/null", json.dumps(risk, separators=(",", ":"))))
    if "__DATA__" in html or "__CONFIG__" in html or "__RISK__" in html:
        raise SystemExit("template placeholders were not replaced")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(SITE / "vendor" / "plotly-basic.min.js", OUT / "plotly-basic.min.js")
    (OUT / ".nojekyll").write_text("")
    print(f"wrote {OUT / 'index.html'}  ({len(html) / 1e6:.1f} MB)  on-time {h['on_time_pct']:.1%}, "
          f"avg TAT {h['avg_tat_days']} days, penalty ${h['total_penalty_usd']:,.0f}")


if __name__ == "__main__":
    main()
