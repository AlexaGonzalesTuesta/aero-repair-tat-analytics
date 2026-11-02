# Power BI Build Guide

The pipeline writes a star schema to `data/processed/` that loads straight into Power BI Desktop.

## 1. Load the tables
1. Run `python run_pipeline.py`.
2. Open Power BI Desktop > **Home** > **Get data** > **Text/CSV**.
3. Load each file from `data/processed/`: `fact_repair_orders.csv`, `fact_stage_events.csv`, `dim_site.csv`, `dim_part.csv`, `dim_date.csv`.

## 2. Create relationships (Model view)
| From (many) | To (one) |
|---|---|
| `fact_repair_orders[site]` | `dim_site[site]` |
| `fact_repair_orders[part_number]` | `dim_part[part_number]` |
| `fact_repair_orders[received_date]` | `dim_date[date]` |
| `fact_stage_events[order_id]` | `fact_repair_orders[order_id]` (single direction, orders filter events) |

Mark `dim_date` as a date table: select the table > **Table tools** > **Mark as date table** > choose `date`.

## 3. DAX measures
Create these in `fact_repair_orders` (**Home** > **New measure**):

```DAX
Closed Orders = CALCULATE(COUNTROWS(fact_repair_orders), fact_repair_orders[status] = "Closed")

On-Time % =
DIVIDE(
    CALCULATE(COUNTROWS(fact_repair_orders), fact_repair_orders[status] = "Closed", fact_repair_orders[on_time] = TRUE()),
    [Closed Orders]
)

Avg TAT Days = CALCULATE(AVERAGE(fact_repair_orders[tat_days]), fact_repair_orders[status] = "Closed")

First Pass Yield =
DIVIDE(
    CALCULATE(COUNTROWS(fact_repair_orders), fact_repair_orders[status] = "Closed", fact_repair_orders[first_pass_test] = TRUE()),
    [Closed Orders]
)

Penalty Exposure = SUM(fact_repair_orders[penalty_usd])

Open Past Contract = CALCULATE(COUNTROWS(fact_repair_orders), fact_repair_orders[open_past_contract] = TRUE())

On-Time Gap to Target = [On-Time %] - 0.85
```

Create this one in `fact_stage_events`:

```DAX
Avg Stage Days = AVERAGE(fact_stage_events[duration_days])
```

## 4. Suggested report pages
1. **Executive overview:** cards for On-Time %, Avg TAT Days, First Pass Yield, Penalty Exposure, Open Past Contract; line chart of On-Time % by `dim_date[year_month]`; slicers for site, part family, priority.
2. **Bottlenecks:** bar chart of Avg Stage Days by `fact_stage_events[stage]` (sort by `stage_sequence`); bar chart of late orders by `primary_delay_reason`.
3. **At-risk orders:** load `outputs/at_risk_open_orders.csv` as a table visual with conditional formatting on `late_risk`.
