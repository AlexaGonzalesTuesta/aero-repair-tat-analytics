"""One command to run the whole project end to end.

    python run_pipeline.py

Steps: generate synthetic data -> clean and validate -> build star schema ->
KPIs and charts -> train late-risk model -> write stakeholder report.
"""
import json

from tat_analytics import charts, generate_data, pipeline, report, risk_model
from tat_analytics import config as C
from tat_analytics import kpis as K


def main():
    print("1/5 Generating synthetic repair data")
    generate_data.main()

    print("2/5 Cleaning, validating, and building star schema")
    f, ev = pipeline.run()

    print("3/5 Calculating KPIs and saving charts")
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "headline": K.headline(f),
        "bottleneck": K.stage_bottleneck(ev, f).to_dict(orient="records"),
        "delay_pareto": K.delay_pareto(f).to_dict(orient="records"),
    }
    (C.OUTPUT_DIR / "kpi_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    charts.run(f, ev)

    print("4/5 Training late-delivery risk model")
    metrics, _, at_risk = risk_model.run(f)

    print("5/5 Writing weekly stakeholder report")
    report.run(f, ev, metrics, at_risk)

    h = summary["headline"]
    print(
        f"\nDone. On-time {h['on_time_pct']:.1%} | Avg TAT {h['avg_tat_days']} days | "
        f"Penalty exposure ${h['total_penalty_usd']:,.0f} | Open past contract: {h['open_past_contract']}"
    )
    print("Next: streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
