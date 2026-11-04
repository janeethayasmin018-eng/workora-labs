# Workora Growth Dashboard

An interactive business intelligence dashboard built with **Streamlit** and **Plotly**. It combines acquisition, retention, regional demand and checkout testing in one app.


## Dashboard contents

- **KPI cards:** Total revenue, Active customers, Churn rate, Avg ticket size.
- **Filters (sidebar):** Date range, Device (used as the "Category" filter), State (web traffic), City (markets), customer zone and Plan (retention), and Segment (markets).
- **Tabs:** Acquisition, Retention, Markets, Checkout test, Data notes.

## Data cleaning

- Removed 5 exact duplicate rows from the customer file (605 down to 600).
- 13 customers have no region. They are kept as "Unknown" and drop out when a region is chosen.
- 10 customers have `TotalChargesINR` set to "unknown". That column is not used.
- 7 customers have `MonthlyChargesINR` above ₹3,000, roughly ten times their plan's typical price. They still count for churn but are excluded from the average monthly charge.
- The other three files had no missing values or duplicate IDs.

## Joins

The files share no common key, so no joins are made. Each file feeds its own charts, and each KPI card says which filters affect it.

## Calculated fields

| Field | Definition |
|---|---|
| Total revenue | Sum of `OrderValueINR` for converted checkout-test visitors |
| Avg ticket size | Total revenue divided by converted orders |
| Active customers | Customers in the cleaned churn file with `Churn = No` |
| Churn rate | Churned customers divided by all customers |
| Registration rate | Registered sessions divided by all web sessions |
| Checkout conversion | Converted visitors divided by all visitors in the variant |
| Tenure bands | 0–12, 13–24, 25–48 and 49+ months |

## Assumptions

- The data has no revenue or user-count column, so the KPIs above are my own definitions.
- No region mapping is invented. Each file keeps its own region field, so the sidebar has three region filters: State for web traffic, City for markets and customer zone (North, South, East, West, Central) for retention.
- The checkout test has no region, and the customer file has no dates or devices, so those filters leave them unchanged.

## Key findings (no filters)

- Checkout test: 128 orders, ₹18,772 revenue, ₹147 average ticket.
- Variant B converts 11.8% of visitors against 9.5% for A. The difference is not statistically significant at the 95% level (z ≈ 1.31, p ≈ 0.19), so no winner can be declared.
- Churn is 41.2% (247 of 600 customers), leaving 353 active customers.
- Web traffic: 900 sessions with an 18.4% registration rate.

## Limitations

- Synthetic data, so patterns are illustrative only.
- The files cover different periods (web traffic runs January to August 2026, the checkout test only July 2026), so the KPI cards mix time frames.
- Region is not shared across files, so the three region filters work independently.
