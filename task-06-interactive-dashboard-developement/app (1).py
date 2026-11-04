"""Workora growth dashboard (Streamlit + Plotly). All data is synthetic."""
import zipfile
from math import erf, sqrt
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Workora growth dashboard", page_icon="📊", layout="wide")

DATA = Path(__file__).parent / "data"
ZONES = ["North", "South", "East", "West", "Central"]  # values already used in customer_churn.csv
ZIP = Path(__file__).parent / "data_analytics_dashboard_bundle.zip"


def read(name, **kw):
    """Read a CSV straight from the uploaded zip; fall back to the data/ folder."""
    if ZIP.exists():
        with zipfile.ZipFile(ZIP) as z:
            return pd.read_csv(z.open(name), **kw)
    return pd.read_csv(DATA / name, **kw)


TEAL, GOLD, RED, VIOLET, GREY = "#0F6E7A", "#D9962B", "#C0443A", "#6B5FC7", "#8A9BA0"
SEGMENT_COLORS = {"Student": TEAL, "Early Career": GOLD, "Professional": VIOLET}


def inr(x: float) -> str:
    return f"₹{x:,.0f}"


@st.cache_data
def load():
    """Read the four CSVs, clean them, and return them with a cleaning log."""
    web = read("web_traffic.csv", parse_dates=["Date"])
    for c in ["StartedRegistration", "Registered", "Bounced"]:
        web[c] = web[c].eq("Yes")

    raw = read("customer_churn.csv")
    churn = raw.drop_duplicates().copy()
    churn["Churned"] = churn["Churn"].eq("Yes")
    churn["Zone"] = churn["Region"].fillna("Unknown")
    churn["AutoPay"] = churn["AutoPay"].astype(str)
    outlier = churn["MonthlyChargesINR"] > 3000
    churn["MonthlyClean"] = churn["MonthlyChargesINR"].mask(outlier)
    churn["TenureBand"] = pd.cut(churn["TenureMonths"], [-1, 12, 24, 48, 999],
                                 labels=["0–12", "13–24", "25–48", "49+"])

    mk = read("regional_market.csv")

    ab = read("checkout_ab_test.csv", parse_dates=["Timestamp"])
    ab["Date"] = ab["Timestamp"].dt.normalize()
    ab["Started"] = ab["CheckoutStarted"].eq("Yes")
    ab["Converted"] = ab["Converted"].eq("Yes")

    log = {
        "dup_rows": len(raw) - len(churn), "raw_customers": len(raw), "customers": len(churn),
        "missing_region": int(churn["Region"].isna().sum()),
        "unknown_total": int((churn["TotalChargesINR"] == "unknown").sum()),
        "outliers": int(outlier.sum()),
        "sessions": len(web), "markets": len(mk), "visitors": len(ab),
    }
    return web, churn, mk, ab, log


web, churn, mk, ab, log = load()

# ---------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
dmin = min(web["Date"].min(), ab["Date"].min()).date()
dmax = max(web["Date"].max(), ab["Date"].max()).date()
picked = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if not isinstance(picked, (tuple, list)) or len(picked) != 2:
    st.sidebar.info("Pick an end date to apply the range.")
    st.stop()
start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
state = st.sidebar.selectbox("State (web traffic)", ["All"] + sorted(web["Region"].unique()))
city = st.sidebar.selectbox("City (markets)", ["All"] + sorted(mk["City"].unique()))
zone = st.sidebar.selectbox("Customer zone (retention)", ["All"] + ZONES)
device = st.sidebar.selectbox("Device", ["All", "Mobile", "Desktop", "Tablet"])
plan = st.sidebar.selectbox("Plan (retention)", ["All", "Basic", "Standard", "Pro"])
segment = st.sidebar.selectbox("Segment (markets)", ["All", "Student", "Early Career", "Professional"])
st.sidebar.caption("Each file keeps its own region field, so there are three region filters. "
                   "Date and Device apply to web traffic and the checkout test. "
                   "The checkout test has no region, and customers have no date, device or state.")

w = web[web["Date"].between(start, end)]
a = ab[ab["Date"].between(start, end)]
c = churn
m = mk
if device != "All":
    w, a = w[w["DeviceCategory"] == device], a[a["Device"] == device]
if state != "All":
    w = w[w["Region"] == state]
if zone != "All":
    c = c[c["Zone"] == zone]
if city != "All":
    m = m[m["City"] == city]
if plan != "All":
    c = c[c["SubscriptionType"] == plan]
if segment != "All":
    m = m[m["PopulationSegment"] == segment]

# ---------------------------------------------------------------- header and KPIs
st.title("Workora growth dashboard")
st.caption("Acquisition, retention, regional demand and checkout testing. "
           "All figures come from synthetic learning data, not real Workora results.")

orders = a[a["Converted"]]
revenue = int(orders["OrderValueINR"].sum())
churned = int(c["Churned"].sum())
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total revenue", inr(revenue), help="Sum of order value in the checkout test. Responds to date and device.")
k2.metric("Active customers", f"{len(c) - churned:,}", help="Customers with Churn = No. Responds to customer zone and plan.")
k3.metric("Churn rate", f"{churned / len(c):.1%}" if len(c) else "–", help="Churned customers divided by all customers. Responds to customer zone and plan.")
k4.metric("Avg ticket size", inr(revenue / len(orders)) if len(orders) else "–", help="Revenue divided by converted orders. Responds to date and device.")


def rate_bar(df, col, flag, color, horizontal=False, order=None):
    """Bar chart of the share of rows where `flag` is true, per `col`."""
    g = df.groupby(col, observed=True)[flag].agg(rate="mean", rows="size").reset_index()
    g["rate"] *= 100
    g = g.sort_values("rate") if horizontal else g
    fig = px.bar(g, x="rate" if horizontal else col, y=col if horizontal else "rate",
                 orientation="h" if horizontal else "v", hover_data={"rows": True},
                 category_orders={col: order} if order else None, color_discrete_sequence=[color])
    fig.update_traces(hovertemplate="%{y:.1f}% of %{customdata[0]} rows<extra></extra>" if not horizontal
                      else "%{x:.1f}% of %{customdata[0]} rows<extra></extra>")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300,
                      xaxis_title=None if not horizontal else "Rate (%)",
                      yaxis_title="Rate (%)" if not horizontal else None)
    return fig


tab_acq, tab_ret, tab_mkt, tab_exp, tab_notes = st.tabs(
    ["Acquisition", "Retention", "Markets", "Checkout test", "Data notes"])

# ---------------------------------------------------------------- acquisition
with tab_acq:
    if w.empty:
        st.info("No web sessions match these filters. Widen the date range or reset the filters.")
    else:
        mo = w.groupby(w["Date"].dt.to_period("M").dt.to_timestamp()).agg(
            Sessions=("SessionID", "size"), Registered=("Registered", "sum")).reset_index()
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=mo["Date"], y=mo["Sessions"], name="Sessions", marker_color=TEAL)
        fig.add_scatter(x=mo["Date"], y=mo["Registered"], name="Registered", mode="lines+markers",
                        line=dict(color=GOLD, width=3), secondary_y=True)
        fig.update_layout(title="Sessions and registrations by month", height=340, margin=dict(l=0, r=0, t=40, b=0),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)

        l, r = st.columns(2)
        l.subheader("Registration rate by source")
        l.plotly_chart(rate_bar(w, "Source", "Registered", TEAL, horizontal=True), use_container_width=True)
        steps = pd.DataFrame({"Step": ["Sessions", "Not bounced", "Started registration", "Registered"],
                              "Count": [len(w), int((~w["Bounced"]).sum()), int(w["StartedRegistration"].sum()),
                                        int(w["Registered"].sum())]})
        r.subheader("Registration funnel")
        f = px.funnel(steps, x="Count", y="Step", color_discrete_sequence=[TEAL])
        f.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
        r.plotly_chart(f, use_container_width=True)

        l2, r2 = st.columns(2)
        l2.subheader("Registration rate by landing page")
        l2.plotly_chart(rate_bar(w, "LandingPage", "Registered", VIOLET, horizontal=True), use_container_width=True)
        r2.subheader("Registration rate by campaign")
        r2.plotly_chart(rate_bar(w, "Campaign", "Registered", GOLD), use_container_width=True)

# ---------------------------------------------------------------- retention
with tab_ret:
    if c.empty:
        st.info("No customers match these filters.")
    else:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Customers", f"{len(c):,}")
        s2.metric("Avg monthly charge", inr(c["MonthlyClean"].mean()), help="Excludes the monthly-charge outliers.")
        s3.metric("Avg tenure", f"{c['TenureMonths'].mean():.1f} months")
        s4.metric("Avg support tickets", f"{c['SupportTickets'].mean():.1f}")
        l, r = st.columns(2)
        l.subheader("Churn by contract type")
        l.plotly_chart(rate_bar(c, "ContractType", "Churned", RED), use_container_width=True)
        r.subheader("Churn by tenure")
        r.plotly_chart(rate_bar(c, "TenureBand", "Churned", RED, order=["0–12", "13–24", "25–48", "49+"]),
                       use_container_width=True)
        l2, r2 = st.columns(2)
        l2.subheader("Churn by late payments")
        l2.plotly_chart(rate_bar(c, "LatePayments", "Churned", RED), use_container_width=True)
        r2.subheader("Churn by AutoPay")
        r2.plotly_chart(rate_bar(c, "AutoPay", "Churned", RED), use_container_width=True)

# ---------------------------------------------------------------- markets
with tab_mkt:
    if m.empty:
        st.info("No markets match these filters.")
    else:
        st.subheader("Market map")
        st.caption("Each bubble is one market. Bigger means more monthly search demand.")
        fig = px.scatter_map(m, lat="Latitude", lon="Longitude", size="MonthlySearchDemand",
                             color="PopulationSegment", color_discrete_map=SEGMENT_COLORS,
                             hover_name="City", hover_data={"MonthlySearchDemand": True, "EstimatedAcquisitionCostINR": True,
                                                            "Latitude": False, "Longitude": False},
                             size_max=14, zoom=3.6, center={"lat": 21.5, "lon": 79}, height=520)
        fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        t = (m.groupby("City").agg(Markets=("RegionID", "size"), AvgSearchDemand=("MonthlySearchDemand", "mean"),
                                   AvgCompetitors=("ExistingCompetitors", "mean"), LeadConversion=("LeadConversionRate", "mean"),
                                   CostToAcquire=("EstimatedAcquisitionCostINR", "mean"))
             .sort_values("AvgSearchDemand", ascending=False).reset_index())
        st.subheader("City summary")
        st.dataframe(t, hide_index=True, use_container_width=True, column_config={
            "AvgSearchDemand": st.column_config.NumberColumn("Avg search demand", format="%.0f"),
            "AvgCompetitors": st.column_config.NumberColumn("Avg competitors", format="%.1f"),
            "LeadConversion": st.column_config.NumberColumn("Lead conversion", format="percent"),
            "CostToAcquire": st.column_config.NumberColumn("Cost to acquire", format="₹%.0f")})

# ---------------------------------------------------------------- checkout test
with tab_exp:
    rows = []
    for v in ["A", "B"]:
        d = a[a["Variant"] == v]
        n, o = len(d), int(d["Converted"].sum())
        p = o / n if n else 0.0
        rows.append(dict(Variant=v, Visitors=n, Started=int(d["Started"].sum()), Orders=o, p=p,
                         CI=1.96 * sqrt(p * (1 - p) / n) if n else 0.0,
                         AvgOrder=d.loc[d["Converted"], "OrderValueINR"].mean(), Revenue=int(d["OrderValueINR"].sum())))
    A, B = rows
    if A["Visitors"] == 0 or B["Visitors"] == 0:
        st.info("Not enough checkout-test visitors for these filters.")
    else:
        pool = (A["Orders"] + B["Orders"]) / (A["Visitors"] + B["Visitors"])
        se = sqrt(pool * (1 - pool) * (1 / A["Visitors"] + 1 / B["Visitors"]))
        z = (B["p"] - A["p"]) / se if se else 0.0
        pval = 1 - erf(abs(z) / sqrt(2))
        diff = (B["p"] - A["p"]) * 100
        verdict = ("This difference is statistically significant at the 95% level." if pval < 0.05 else
                   "This difference is not statistically significant at the 95% level, so it could be chance. "
                   "More visitors would be needed to be sure.")
        st.info(f"**Variant B converts {abs(diff):.1f} points {'higher' if diff >= 0 else 'lower'} than A** "
                f"(z = {z:.2f}, p = {pval:.2f}). {verdict}")
        st.subheader("Variant results")
        st.caption("Conversion rate is orders divided by all visitors. The range is a 95% interval.")
        tbl = pd.DataFrame([{"Variant": r["Variant"], "Visitors": r["Visitors"], "Started checkout": r["Started"],
                             "Orders": r["Orders"], "Conversion rate": f"{r['p']:.1%} ± {r['CI'] * 100:.1f}",
                             "Avg order": inr(r["AvgOrder"]) if r["Orders"] else "–", "Revenue": inr(r["Revenue"])}
                            for r in rows])
        st.dataframe(tbl, hide_index=True, use_container_width=True)
        l, r = st.columns(2)
        for box, col, title in [(l, "Device", "Conversion by device"), (r, "TrafficSource", "Conversion by traffic source")]:
            g = a.groupby([col, "Variant"])["Converted"].mean().mul(100).reset_index()
            fig = px.bar(g, x=col, y="Converted", color="Variant", barmode="group",
                         color_discrete_map={"A": GREY, "B": TEAL}, labels={"Converted": "Conversion (%)", col: ""})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=300)
            box.subheader(title)
            box.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- notes
with tab_notes:
    st.markdown(f"""
### Cleaning and joins
- Customer file: removed {log['dup_rows']} exact duplicate rows ({log['raw_customers']} down to {log['customers']}).
- {log['missing_region']} customers have no region. They stay in the totals as "Unknown" and drop out when a region is chosen.
- {log['unknown_total']} customers have "unknown" total charges. That column is not used in any chart.
- {log['outliers']} customers have a monthly charge above ₹3,000, roughly ten times their plan's typical price. They still count for churn but are left out of the average monthly charge.
- Web traffic ({log['sessions']} sessions), markets ({log['markets']}) and the checkout test ({log['visitors']} visitors) had no missing values or duplicate IDs, so nothing was removed.

### Assumptions
- The files share no common key, so nothing is joined. Each file feeds its own charts.
- No region mapping is invented. Web traffic is filtered by its own State, markets by City, and customers by their own zone (North, South, East, West, Central).
- The data has no revenue or user-count column, so the KPIs are defined below.

### Calculated fields
- **Total revenue:** sum of order value for converted checkout-test visitors.
- **Avg ticket size:** total revenue divided by converted orders.
- **Active customers:** customers in the cleaned churn file with Churn = No.
- **Churn rate:** churned customers divided by all customers.
- **Registration rate:** registered sessions divided by all web sessions.
- **Checkout conversion:** converted visitors divided by all visitors in the variant, tested with a two-sided two-proportion z-test.
""")
