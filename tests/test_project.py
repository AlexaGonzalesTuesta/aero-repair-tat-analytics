"""Automated tests: data generation, data quality rules, KPIs, scenarios, model."""
import pandas as pd
import pytest

from tat_analytics import config as C
from tat_analytics import kpis as K
from tat_analytics import pipeline, risk_model
from tat_analytics.generate_data import generate


@pytest.fixture(scope="module")
def data():
    orders, events, catalog = generate(n_orders=800, seed=7, inject_dirty=True)
    o, e, log = pipeline.clean(orders, events)
    f, ev, *_ = pipeline.build_star_schema(o, e, catalog)
    return orders, events, f, ev, log


def test_generation_is_reproducible():
    a, _, _ = generate(n_orders=50, seed=1, inject_dirty=False)
    b, _, _ = generate(n_orders=50, seed=1, inject_dirty=False)
    pd.testing.assert_frame_equal(a, b)


def test_stages_follow_value_stream_order(data):
    *_, ev, _ = data
    first = ev.sort_values("start_ts").groupby("order_id").stage.first()
    assert (first == "Receiving").all()
    assert set(ev.stage) <= set(C.STAGES)


def test_cleaning_fixes_injected_issues(data):
    orders, _, f, ev, log = data
    assert orders.order_id.duplicated().any()  # dirty input really had duplicates
    assert f.order_id.is_unique
    assert set(f.site) <= set(C.SITES)
    assert f.priority.notna().all()
    assert (ev.duration_days.dropna() >= 0).all()
    checks = {c["check"]: c["issues_found"] for c in log}
    assert checks["Duplicate order rows removed"] > 0
    assert checks["Negative stage durations remaining"] == 0


def test_on_time_logic():
    f = pd.DataFrame(
        {
            "order_id": ["a", "b", "c"],
            "status": ["Closed", "Closed", "Open"],
            "tat_days": [9.0, 12.0, None],
            "contract_tat_days": [10, 10, 10],
            "on_time": [True, False, None],
            "first_pass_test": [True, True, None],
            "penalty_usd": [0, 500, 0],
            "open_past_contract": [False, False, True],
        }
    )
    h = K.headline(f)
    assert h["on_time_pct"] == 0.5
    assert h["closed_orders"] == 2 and h["open_orders"] == 1
    assert h["open_past_contract"] == 1


def test_penalty_only_when_late(data):
    *_, f, _, _ = data
    c = K.closed(f)
    assert (c.loc[c.on_time.astype(bool), "penalty_usd"] == 0).all()
    assert (c.loc[c.is_late.astype(bool), "penalty_usd"] > 0).all()


def test_what_if_never_makes_things_worse(data):
    *_, f, ev, _ = data
    base = K.what_if(f, ev)
    better = K.what_if(f, ev, parts_wait_reduction=0.3, quote_reduction=0.5, rework_reduction=0.25)
    assert base["penalty_savings_usd"] == 0
    assert better["scenario_on_time_pct"] >= better["baseline_on_time_pct"]
    assert better["scenario_penalty_usd"] <= better["baseline_penalty_usd"]


def test_what_if_rejects_bad_input(data):
    *_, f, ev, _ = data
    with pytest.raises(ValueError):
        K.what_if(f, ev, parts_wait_reduction=1.5)


def test_rag_status():
    assert K.rag(0.90, 0.85) == "Green"
    assert K.rag(0.83, 0.85) == "Amber"
    assert K.rag(0.60, 0.85) == "Red"
    assert K.rag(0.9, 1.0, higher_is_better=False) == "Green"


def test_risk_model_beats_random(data):
    *_, f, _, _ = data
    _, metrics, drivers, at_risk = risk_model.train_and_score(f)
    assert metrics["roc_auc"] > 0.6
    assert at_risk.late_risk.between(0, 1).all()
    assert len(drivers) > 0
