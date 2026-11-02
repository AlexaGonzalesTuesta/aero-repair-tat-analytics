"""Generate a realistic SYNTHETIC dataset of aerospace component repair orders.

No real company data is used. Distributions are tuned to reflect publicly
described dynamics of component repair stations: parts shortages, customer
quote approvals, test failures with rework loops, and AOG (aircraft on ground)
expediting. A small amount of "dirty" data is injected on purpose so the
pipeline's data quality checks have something real to catch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _pick(rng: np.random.Generator, options: dict, n: int, key: str = "share") -> np.ndarray:
    names = list(options)
    probs = np.array([v[key] if isinstance(v, dict) else v for v in options.values()], dtype=float)
    return rng.choice(names, size=n, p=probs / probs.sum())


def _lognormal(rng: np.random.Generator, mean: float, sigma: float = 0.45) -> float:
    """Lognormal draw whose expected value is approximately `mean` days."""
    if mean <= 0:
        return 0.0
    mu = np.log(mean) - sigma**2 / 2
    return float(rng.lognormal(mu, sigma))


def build_part_catalog(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for fam_idx, family in enumerate(C.PART_FAMILIES):
        prefix = "".join(w[0] for w in family.replace("&", "").split()).upper()
        for i in range(15):
            rows.append(
                {
                    "part_number": f"{prefix}-{100 + fam_idx * 50 + i}",
                    "part_family": family,
                    # Zipf-like popularity: a few part numbers drive most volume.
                    "popularity": 1.0 / (i + 1) ** 0.9,
                    # A handful of parts are chronically short on sub-components.
                    "shortage_risk": float(rng.uniform(1.4, 2.0)) if i in (0, 2, 5) else float(rng.uniform(0.6, 1.1)),
                }
            )
    return pd.DataFrame(rows)


def generate(n_orders: int = C.N_ORDERS, seed: int = C.SEED, inject_dirty: bool = True):
    rng = np.random.default_rng(seed)
    catalog = build_part_catalog(rng)
    start = pd.Timestamp(C.START_DATE)
    cutoff = pd.Timestamp(C.DATA_CUTOFF)
    span_days = (cutoff - start).days

    # Volume ramps up over time (growing aftermarket demand).
    received_offsets = np.sort(span_days * np.sqrt(rng.uniform(0, 1, n_orders)))
    families = _pick(rng, C.PART_FAMILIES, n_orders)
    sites = _pick(rng, C.SITES, n_orders)
    customers = _pick(rng, C.CUSTOMER_TYPES, n_orders)
    priorities = _pick(rng, C.PRIORITIES, n_orders, key=None)

    orders, events = [], []
    for i in range(n_orders):
        order_id = f"RO-{100000 + i}"
        fam, site, cust, prio = families[i], sites[i], customers[i], priorities[i]
        fam_cfg, site_cfg, cust_cfg = C.PART_FAMILIES[fam], C.SITES[site], C.CUSTOMER_TYPES[cust]

        fam_parts = catalog[catalog.part_family == fam]
        p = fam_parts.popularity / fam_parts.popularity.sum()
        part_row = fam_parts.iloc[rng.choice(len(fam_parts), p=p.values)]

        received = start + pd.Timedelta(days=float(received_offsets[i])) + pd.Timedelta(hours=float(rng.uniform(6, 18)))
        unit_age = round(float(rng.gamma(3.0, 3.0)), 1)
        prior_repairs = int(rng.poisson(0.6 + unit_age / 15))

        scale = fam_cfg["scale"] * site_cfg["efficiency"]
        speed = {"AOG": 0.55, "Critical": 0.85, "Routine": 1.0}[prio]
        month = received.month
        seasonal_load = 1.15 if month in (6, 7, 8, 12) else 1.0  # summer flying + year-end

        shortage_p = min(0.9, site_cfg["parts_shortage_rate"] * part_row.shortage_risk * (1 + prior_repairs * 0.05))
        has_shortage = rng.uniform() < shortage_p
        needs_quote = rng.uniform() < 0.7
        test_fails = rng.uniform() > (C.FIRST_PASS_TEST_YIELD - 0.02 * min(prior_repairs, 4))

        contrib = {r: 0.0 for r in C.DELAY_REASONS}
        plan = []
        plan.append(("Receiving", _lognormal(rng, 0.6 * speed), 1))
        plan.append(("Inspection", _lognormal(rng, 1.0 * scale * speed * seasonal_load), 1))
        plan.append(("Teardown & Evaluation", _lognormal(rng, 1.8 * scale * speed * seasonal_load), 1))
        q = _lognormal(rng, cust_cfg["quote_days"] * (0.5 if prio == "AOG" else 1.0)) if needs_quote else 0.05
        contrib["Customer quote approval"] += q
        plan.append(("Quote Approval", q, 1))
        if has_shortage:
            wait = _lognormal(rng, 9.0 * fam_cfg["scale"] * (0.5 if prio == "AOG" else 1.0), sigma=0.6)
            contrib["Parts shortage"] += wait
        else:
            wait = _lognormal(rng, 0.3)
        plan.append(("Awaiting Parts", wait, 1))
        rep = _lognormal(rng, 4.0 * scale * speed * seasonal_load)
        contrib["Technician capacity"] += max(0.0, rep - 4.0 * scale * speed)
        plan.append(("Repair", rep, 1))
        plan.append(("Reassembly", _lognormal(rng, 1.5 * scale * speed), 1))
        plan.append(("Test", _lognormal(rng, 1.0 * scale), 1))
        if test_fails:
            rework = _lognormal(rng, 2.5 * scale)
            retest = _lognormal(rng, 1.0 * scale)
            contrib["Test failure / rework"] += rework + retest
            plan.append(("Repair", rework, 2))
            plan.append(("Test", retest, 2))
        qa = _lognormal(rng, 0.8, sigma=0.7)
        contrib["Documentation / RTS paperwork"] += max(0.0, qa - 0.8)
        plan.append(("Final QA & Ship", qa, 1))

        t = received
        current_stage = None
        for stage, dur, attempt in plan:
            end = t + pd.Timedelta(days=dur)
            if t > cutoff:
                break
            is_open = end > cutoff
            events.append(
                {
                    "order_id": order_id,
                    "stage": stage,
                    "attempt": attempt,
                    "start_ts": t,
                    "end_ts": pd.NaT if is_open else end,
                }
            )
            if is_open:
                current_stage = stage
                break
            t = end
        shipped = t if current_stage is None else pd.NaT

        tat = (shipped - received).total_seconds() / 86400 if pd.notna(shipped) else np.nan
        late = bool(tat > fam_cfg["contract_tat"]) if pd.notna(shipped) else None
        primary_delay = max(contrib, key=contrib.get) if late else None

        orders.append(
            {
                "order_id": order_id,
                "part_number": part_row.part_number,
                "part_family": fam,
                "site": site,
                "customer_type": cust,
                "priority": prio,
                "received_ts": received,
                "shipped_ts": shipped,
                "contract_tat_days": fam_cfg["contract_tat"],
                "penalty_per_day_usd": fam_cfg["penalty_per_day"],
                "unit_age_years": unit_age,
                "prior_repairs_12m": prior_repairs,
                "status": "Open" if pd.isna(shipped) else "Closed",
                "current_stage": current_stage,
                "primary_delay_reason": primary_delay,
            }
        )

    orders_df = pd.DataFrame(orders)
    events_df = pd.DataFrame(events)

    if inject_dirty:
        orders_df, events_df = _inject_dirty_data(rng, orders_df, events_df)
    return orders_df, events_df, catalog.drop(columns=["popularity"])


def _inject_dirty_data(rng, orders_df: pd.DataFrame, events_df: pd.DataFrame):
    """Simulate common ERP / manual-entry issues found in real repair data."""
    o = orders_df.copy()
    e = events_df.copy()
    # 1) Duplicate order rows (double-keyed records)
    dupes = o.sample(12, random_state=1)
    o = pd.concat([o, dupes], ignore_index=True)
    # 2) Inconsistent site labels (casing / whitespace)
    idx = o.sample(40, random_state=2).index
    o.loc[idx, "site"] = o.loc[idx, "site"].str.upper() + "  "
    # 3) Stage events where end is before start (manual timestamp entry errors)
    closed = e[e.end_ts.notna()].sample(15, random_state=3).index
    e.loc[closed, "end_ts"] = e.loc[closed, "start_ts"] - pd.Timedelta(hours=5)
    # 4) Missing priority values
    idx = o.sample(25, random_state=4).index
    o.loc[idx, "priority"] = None
    return o, e


def main():
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    orders, events, catalog = generate()
    orders.to_csv(C.RAW_DIR / "repair_orders.csv", index=False)
    events.to_csv(C.RAW_DIR / "stage_events.csv", index=False)
    catalog.to_csv(C.RAW_DIR / "part_catalog.csv", index=False)
    print(f"Generated {len(orders):,} order rows and {len(events):,} stage events -> {C.RAW_DIR}")


if __name__ == "__main__":
    main()
