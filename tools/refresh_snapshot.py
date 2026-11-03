"""Copy the processed tables into app/snapshot after running run_pipeline.py.

The dashboard reads the snapshot on Streamlit Community Cloud, so the first visit after the
app wakes up does not have to regenerate and process the data.
Run:  python run_pipeline.py  then  python tools/refresh_snapshot.py
"""
import gzip
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed"
DST = ROOT / "app" / "snapshot"

DST.mkdir(parents=True, exist_ok=True)
for name in ("fact_repair_orders.csv", "fact_stage_events.csv"):
    with open(SRC / name, "rb") as src, gzip.open(DST / f"{name}.gz", "wb", compresslevel=9) as dst:
        shutil.copyfileobj(src, dst)
    print("wrote", DST / f"{name}.gz")
