# Workora Checkout Test Dashboard

An interactive dashboard built with **Streamlit** and **Plotly**, using only `checkout_ab_test.csv` from the Workora data pack.

## Data

`checkout_ab_test.csv` has 1,200 rows, one per visitor: `VisitorID`, `Variant` (A or B), `Timestamp` (1 to 22 July 2026), `Device`, `TrafficSource`, `CheckoutStarted`, `Converted` and `OrderValueINR`.

## Dashboard contents

**KPI cards**
- Total revenue
- Visitors (used as the active-user count)
- Conversion rate
- Checkout abandonment (used in place of churn, which this file does not contain)
- Avg ticket size

**Filters:** date range, device, traffic source.

**Tabs**
- **Overview:** visitors and orders by day, checkout funnel, revenue by device.
- **Variant A vs B:** results table, two-proportion z-test, conversion by variant with 95% intervals, orders by order value.
- **Segments:** conversion by device and by traffic source, a device by source heatmap, visitors and orders by hour.
- **Data notes:** quality checks, calculated fields and limits.

## Data cleaning

The file needed no cleaning: no duplicate visitor IDs, no missing values, no orders without a checkout start, and order value only on converted visitors. No rows were excluded.

## Calculated fields

| Field | Definition |
|---|---|
| Total revenue | Sum of `OrderValueINR` for converted visitors |
| Conversion rate | Orders divided by all visitors |
| Checkout abandonment | Visitors who started checkout and did not order, divided by visitors who started |
| Avg ticket size | Total revenue divided by orders |

## Key findings (no filters)

- 128 orders and ₹18,772 revenue, with an average ticket of about ₹147.
- 380 visitors started checkout and 128 ordered, so abandonment is 66.3%.
- Variant B converts 11.8% of visitors against 9.5% for A. The difference is not statistically significant at the 95% level (p ≈ 0.19), so no winner can be declared.

## Limitations

- Only 22 days in one month, with no region, customer ID or repeat-visit data, so churn and regional views are not possible.
- Synthetic data, so patterns are illustrative only.

