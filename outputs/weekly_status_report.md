# Repair and Overhaul TAT: Weekly Status Report

**Data as of:** 2026-09-30  |  **Scope:** 3,789 closed and 211 open repair orders across 4 sites
*Synthetic data for portfolio demonstration. Generated automatically by `run_pipeline.py`.*

## Executive summary
- On-time delivery is **62.7%** against an 85% target. The last 3 months averaged 61.1% vs 64.1% in the 3 months before.
- **Awaiting Parts** is the largest bottleneck at 4.2 days per order (25% of total TAT).
- **Parts shortage** is the top cause of late orders (1025 orders, 72.4% of all late orders).
- **Straits (APAC)** has the lowest on-time rate (50.1%).
- Combining the three initiatives below is estimated to lift on-time delivery to **76.8%** and avoid **$3,662,453** in penalties over the same period.

## KPI scorecard
| KPI | Actual | Target | Status |
|---|---|---|---|
| On-time delivery | 62.7% | 85.0% | Red |
| First-pass test yield | 84.2% | 90.0% | Red |
| Avg TAT / contracted TAT | 0.96x | 1.00x or less | Green |
| Late-delivery penalty exposure | $6,267,749 | Trending down | Info |
| Open orders already past contract | 32 | 0 | Info |

## Recommended initiatives (what-if estimates)
| Initiative | On-time % (now -> scenario) | Avg TAT days | Penalty savings |
|---|---|---|---|
| A. Safety stock + dual-sourcing for chronic shortage parts (parts wait -30%) | 62.7% -> 69.5% | 16.7 -> 15.4 | $2,611,629 |
| B. Pre-approved not-to-exceed repair limits with customers (quote wait -50%) | 62.7% -> 69.4% | 16.7 -> 15.7 | $1,072,713 |
| C. Standard work + test checklist to cut rework (rework time -25%) | 62.7% -> 63.3% | 16.7 -> 16.5 | $202,861 |
| A + B + C combined | 62.7% -> 76.8% | 16.7 -> 14.3 | $3,662,453 |

## Open orders at highest risk of missing contract (top 10)
Risk model ROC AUC on held-out recent orders: **0.751** (top 10% of scores are 1.99x more likely to be late than average).

| order_id | part_family | site | priority | current_stage | age_days | days_to_contract_due | late_risk |
|---|---|---|---|---|---|---|---|
| RO-103808 | Wheels & Brakes | Straits (APAC) | Routine | Final QA & Ship | 14.6 | -4.6 | 0.865 |
| RO-103937 | Wheels & Brakes | Straits (APAC) | Critical | Quote Approval | 3.9 | 6.1 | 0.85 |
| RO-103854 | Wheels & Brakes | Straits (APAC) | Routine | Awaiting Parts | 10.8 | -0.8 | 0.771 |
| RO-103941 | Wheels & Brakes | Straits (APAC) | Routine | Repair | 3.8 | 6.2 | 0.734 |
| RO-103974 | Wheels & Brakes | Rhine (EU) | Routine | Teardown & Evaluation | 1.1 | 8.9 | 0.733 |
| RO-103951 | Avionics LRU | Straits (APAC) | Critical | Quote Approval | 2.8 | 12.2 | 0.727 |
| RO-103760 | Avionics LRU | Straits (APAC) | Routine | Repair | 18.4 | -3.4 | 0.722 |
| RO-103766 | Avionics LRU | Straits (APAC) | Routine | Repair | 17.9 | -2.9 | 0.719 |
| RO-103875 | Wheels & Brakes | Straits (APAC) | Routine | Final QA & Ship | 8.9 | 1.1 | 0.714 |
| RO-103982 | Avionics LRU | Straits (APAC) | Routine | Inspection | 0.7 | 14.3 | 0.705 |

**Action:** review these orders in the daily production meeting; expedite parts or escalate quotes where the order is waiting.

## Data quality
| Check | Issues found / fixed |
|---|---|
| Duplicate order rows removed | 12 |
| order_id unique after cleaning | 0 |
| Site labels standardized (case / whitespace) | 40 |
| Unmapped site labels remaining | 0 |
| Missing priority imputed as Routine (flagged) | 25 |
| Stage end-before-start timestamps repaired | 15 |
| Negative stage durations remaining | 0 |
| Orphan stage events (no matching order) | 0 |

All post-cleaning integrity checks passed: **True**

## Next steps
1. Validate stage timestamp definitions with repair station leads before using results for decisions.
2. Pilot initiative A at Straits (APAC); track on-time % weekly against this baseline.
3. Publish the star schema to Power BI and schedule this report weekly.

## Assumptions and lessons learned
- Contracted TAT and penalty rates are set per part family in `tat_analytics/config.py`.
- What-if estimates assume removed wait time does not shift to another stage; real results will be lower and should be confirmed in a pilot.
- Data entry issues (duplicates, inconsistent site names, impossible timestamps) were common enough that automated quality checks should run before every refresh.
