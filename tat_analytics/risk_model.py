"""Predict, at intake, which repair orders are likely to miss contracted TAT.

Uses only information known when a unit arrives (no leakage from later stages),
a time-based train/test split, and an interpretable logistic regression so
business stakeholders can see which drivers raise risk.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import config as C

CATEGORICAL = ["part_family", "part_number", "site", "customer_type", "priority"]
NUMERIC = ["unit_age_years", "prior_repairs_12m", "received_month"]
SPLIT_DATE = "2026-04-01"


def _features(f: pd.DataFrame) -> pd.DataFrame:
    x = f[CATEGORICAL + ["unit_age_years", "prior_repairs_12m"]].copy()
    x["received_month"] = f.received_ts.dt.month
    return x


def build_model() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ]
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000, C=0.5))])


def train_and_score(f: pd.DataFrame):
    c = f[f.status == "Closed"].copy()
    y = c.is_late.astype(int)
    train_mask = c.received_ts < pd.Timestamp(SPLIT_DATE)

    model = build_model()
    model.fit(_features(c[train_mask]), y[train_mask])
    p_test = model.predict_proba(_features(c[~train_mask]))[:, 1]
    y_test = y[~train_mask].values

    auc = roc_auc_score(y_test, p_test)
    top_decile = p_test >= np.quantile(p_test, 0.9)
    metrics = {
        "train_orders": int(train_mask.sum()),
        "test_orders": int((~train_mask).sum()),
        "split": f"train: received before {SPLIT_DATE}; test: on or after",
        "test_late_rate": round(float(y_test.mean()), 3),
        "roc_auc": round(float(auc), 3),
        "precision_top_10pct": round(float(y_test[top_decile].mean()), 3),
        "lift_top_10pct": round(float(y_test[top_decile].mean() / max(y_test.mean(), 1e-9)), 2),
    }

    # Refit on all closed history, then score current open WIP.
    model.fit(_features(c), y)
    names = model.named_steps["pre"].get_feature_names_out()
    coefs = pd.DataFrame({"feature": names, "coefficient": model.named_steps["clf"].coef_[0]})
    coefs["feature"] = coefs.feature.str.replace("cat__", "", regex=False).str.replace("num__", "", regex=False)
    drivers = coefs.reindex(coefs.coefficient.abs().sort_values(ascending=False).index).head(12)

    op = f[f.status == "Open"].copy()
    op["late_risk"] = model.predict_proba(_features(op))[:, 1] if len(op) else []
    op["days_to_contract_due"] = (op.contract_tat_days - op.age_days).round(1)
    op["risk_band"] = pd.cut(op.late_risk, [-0.01, 0.4, 0.7, 1.0], labels=["Low", "Medium", "High"])
    op.loc[op.days_to_contract_due < 0, "risk_band"] = "High"
    at_risk = op.sort_values(["late_risk"], ascending=False)[
        [
            "order_id", "part_number", "part_family", "site", "customer_type", "priority",
            "current_stage", "age_days", "contract_tat_days", "days_to_contract_due", "late_risk", "risk_band",
        ]
    ].round({"age_days": 1, "late_risk": 3})
    return model, metrics, drivers.round(3), at_risk


def run(f: pd.DataFrame):
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _, metrics, drivers, at_risk = train_and_score(f)
    (C.OUTPUT_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2))
    drivers.to_csv(C.OUTPUT_DIR / "model_top_drivers.csv", index=False)
    at_risk.to_csv(C.OUTPUT_DIR / "at_risk_open_orders.csv", index=False)
    print(f"Risk model: ROC AUC {metrics['roc_auc']}, top-decile lift {metrics['lift_top_10pct']}x; "
          f"{(at_risk.risk_band == 'High').sum()} open orders flagged High risk")
    return metrics, drivers, at_risk
