# Business Requirements Document

**Project:** Repair and Overhaul Turnaround Time (TAT) Analytics
**Author:** Alexa Gonzales Tuesta
**Status:** v1.0 delivered (portfolio project, synthetic data)

## 1. Problem statement
Aerospace component repair stations commit to a contracted turnaround time for every unit they repair (auxiliary power units, avionics, engine controls, wheels and brakes). When a unit ships late, the customer's aircraft may be grounded (AOG), the company pays contractual penalties, and customer satisfaction drops.

Today, TAT performance is reported manually and after the fact. Leaders cannot easily see which stage of the repair value stream is causing delay, which open orders are about to miss contract, or how much an improvement initiative would be worth.

## 2. Objectives
| # | Objective | Success measure |
|---|---|---|
| O1 | Give leaders one trusted view of TAT performance | Dashboard with on-time %, TAT, yield, and penalty exposure, filterable by site, part family, priority, and date |
| O2 | Identify the biggest bottleneck in the repair value stream | Stage-level time breakdown and Pareto of late-order root causes |
| O3 | Flag open orders likely to miss contract before they do | Risk score for every open order, model AUC above 0.70 on held-out data |
| O4 | Quantify improvement initiatives before funding them | What-if model showing on-time % and penalty savings per initiative |
| O5 | Remove manual weekly reporting effort | Status report generated automatically on a schedule |
| O6 | Make the data trustworthy | Automated data quality checks run on every refresh |

## 3. Stakeholders
| Stakeholder | Interest |
|---|---|
| Repair station / value stream leaders | Daily prioritization, bottleneck removal |
| Supply chain and procurement | Parts shortage drivers, safety stock decisions |
| Customer support / account managers | Proactive communication on late orders |
| Finance | Penalty exposure and savings from initiatives |
| IT / data team | Data model, refresh, and maintenance |

## 4. Scope
**In scope:** closed and open repair orders, stage-level timestamps, contracted TAT and penalty terms, four repair sites, five part families.
**Out of scope:** labor scheduling, pricing, and integration with a live ERP (simulated with generated data).

## 5. User stories and acceptance criteria
| ID | User story | Acceptance criteria |
|---|---|---|
| US-1 | As a value stream leader, I want to see on-time % by site and month so I can spot where performance is slipping. | Trend and site charts update when filters change; target line shown at 85%. |
| US-2 | As a value stream leader, I want to know which stage adds the most time so I can focus improvement work. | Average and P90 days per stage shown; largest stage highlighted. |
| US-3 | As a supply chain analyst, I want the part numbers with the most parts-wait days so I can target safety stock. | Ranked table of part numbers by total wait days. |
| US-4 | As a customer support lead, I want a list of open orders at high risk of being late so I can warn customers early. | Every open order has a 0 to 1 risk score and a High / Medium / Low band; downloadable as CSV. |
| US-5 | As a finance partner, I want to estimate penalty savings from an initiative before approving it. | Sliders for parts wait, quote wait, and rework reduction show new on-time % and savings. |
| US-6 | As a program manager, I want a weekly status report with RAG status so I do not have to build it by hand. | Markdown report regenerates with one command and on a weekly GitHub Actions schedule. |
| US-7 | As a data owner, I want bad records caught before they reach the dashboard. | Duplicates, inconsistent site names, missing priority, and impossible timestamps are detected, fixed, and logged. |

## 6. KPI definitions
| KPI | Definition |
|---|---|
| TAT (days) | Shipped timestamp minus received timestamp |
| On-time delivery % | Closed orders with TAT at or below contracted TAT, divided by closed orders |
| First-pass test yield | Closed orders that passed Test on the first attempt, divided by closed orders |
| Days late | max(0, TAT minus contracted TAT) |
| Penalty exposure | Days late multiplied by the part family's penalty per day |
| Open past contract | Open orders whose age already exceeds contracted TAT |

## 7. Data quality rules
1. `order_id` must be unique (duplicates removed, count logged).
2. Site names must match the canonical site list (case and whitespace normalized).
3. Missing priority is imputed as Routine and flagged with `priority_imputed`.
4. Stage end before start is repaired using the next stage's start time.
5. Every stage event must link to a known order.

## 8. Assumptions and risks
- Data is synthetic. Distributions were designed from publicly described repair station dynamics and are not company data.
- What-if estimates assume removed wait time is not absorbed by another stage. Results should be validated with a pilot.
- The risk model uses intake-time attributes only, to avoid leaking information from later stages.
