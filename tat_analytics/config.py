"""Central configuration for the Repair and Overhaul TAT Analytics project.

All business assumptions live here so a stakeholder can review and change them
in one place without touching pipeline logic.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"

SEED = 42
N_ORDERS = 4000
START_DATE = "2025-01-01"
DATA_CUTOFF = "2026-09-30"  # "today" for the snapshot; orders not shipped by now are open WIP

# Repair value stream, in order. Mirrors a typical aerospace component repair station.
STAGES = [
    "Receiving",
    "Inspection",
    "Teardown & Evaluation",
    "Quote Approval",
    "Awaiting Parts",
    "Repair",
    "Reassembly",
    "Test",
    "Final QA & Ship",
]

# Part families: contracted turnaround time (days) and late penalty per day (USD).
PART_FAMILIES = {
    "Auxiliary Power Unit": {"contract_tat": 30, "penalty_per_day": 1500, "share": 0.18, "scale": 1.6},
    "Avionics LRU": {"contract_tat": 15, "penalty_per_day": 400, "share": 0.30, "scale": 0.8},
    "Engine Controls": {"contract_tat": 20, "penalty_per_day": 900, "share": 0.17, "scale": 1.1},
    "Wheels & Brakes": {"contract_tat": 10, "penalty_per_day": 250, "share": 0.20, "scale": 0.55},
    "Environmental Control": {"contract_tat": 18, "penalty_per_day": 500, "share": 0.15, "scale": 0.95},
}

# Fictional repair sites. parts_shortage_rate drives the "Awaiting Parts" bottleneck.
SITES = {
    "Desert Ridge (US-SW)": {"share": 0.35, "parts_shortage_rate": 0.42, "efficiency": 1.00},
    "Prairie (US-MW)": {"share": 0.25, "parts_shortage_rate": 0.30, "efficiency": 0.92},
    "Rhine (EU)": {"share": 0.22, "parts_shortage_rate": 0.36, "efficiency": 1.05},
    "Straits (APAC)": {"share": 0.18, "parts_shortage_rate": 0.48, "efficiency": 1.10},
}

CUSTOMER_TYPES = {
    "Airline": {"share": 0.45, "quote_days": 2.0},
    "Business Aviation": {"share": 0.25, "quote_days": 3.5},
    "Defense": {"share": 0.15, "quote_days": 6.0},
    "MRO Partner": {"share": 0.15, "quote_days": 2.5},
}

PRIORITIES = {"AOG": 0.12, "Critical": 0.28, "Routine": 0.60}  # AOG = aircraft on ground

FIRST_PASS_TEST_YIELD = 0.86  # share of units that pass Test on the first attempt

DELAY_REASONS = [
    "Parts shortage",
    "Customer quote approval",
    "Test failure / rework",
    "Technician capacity",
    "Documentation / RTS paperwork",
]

# KPI targets used for Red / Amber / Green status in the stakeholder report.
TARGETS = {
    "on_time_pct": 0.85,
    "first_pass_yield": 0.90,
    "avg_tat_vs_contract": 1.00,
}
