"""Workora checkout A/B test dashboard (Streamlit + Plotly). All data is synthetic."""
import zipfile
from math import erf, sqrt
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Workora checkout test dashboard", page_icon="📊", layout="wide")

FILE = "checkout_ab_test.csv"
HERE = Path(__file__).resolve().parent
TEAL, GOLD, RED, GREY = "#0F6E7A", "#D9962B", "#C0443A", "#8A9BA0"
VCOL = {"A": GREY, "B": TEAL}


def locate():
    """Find the CSV: next to the app, in data/, anywhere in the repo, or inside a zip."""
    for base in (HERE, HERE / "data", Path.cwd(), Path.cwd() / "data"):
        if (base / FILE).is_file():
            return ("csv", base / FILE)
    for base in {HERE, Path.cwd()}:
        hit = next(base.rglob(FILE), None)
        if hit:
            return ("csv", hit)
        for z in base.rglob("*.zip"):
            try:
                with zipfile.ZipFile(z) as zf:
                    m = next((n for n in zf.namelist() if n == FILE or n.endswith("/" + FILE)), None)
            except zipfile.BadZipFile:
                continue
            if m:
                return ("zip", z, m)
    return None


found = locate()
if found is None:
    st.error(f"{FILE} not found. Add it to the same GitHub folder as this app file and redeploy.")
    st.stop()


def inr(x):
    return f"₹{x:,.0f}"


@st.cache_data
def load():
    if found[0] == "zip":
        with zipfile.ZipFile(found[1]) as zf:
            raw = pd.read_csv(zf.open(found[2]), parse_dates=["Timestamp"])
    else:
        raw = pd.read_csv(found[1], parse_dates=["Timestamp"])
    df = raw.drop_duplicates("VisitorID").copy()
    df["Date"] = df["Timestamp"].dt.normalize()
    df["Hour"] = df["Timestamp"].dt.hour
    df["Started"] = df["CheckoutStarted"].eq("Yes")
    df["Converted"] = df["Converted"].eq("Yes")
    checks = {
        "rows": len(raw), "dups": len(raw) - len(df), "nulls": int(raw.isna().sum().sum()),
        "conv_no_start": int((df["Converted"] & ~df["Started"]).sum()),
        "value_no_order": int(((~df["Converted"]) & (df["OrderValueINR"] > 0)).sum()),
        "order_no_value": int((df["Converted"] & (df["OrderValueINR"] <= 0)).sum()),
    }
    return df, checks


df, checks = load()

# ------------------------------------------------------------------ filters
st.sidebar.header("Filters")
dmin, dmax = df["Date"].min().date(), df["Date"].max().date()
picked = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if not isinstance(picked, (tuple, list)) or len(picked) != 2:
    st.sidebar.info("Pick an end date to apply the range.")
    st.stop()
devices = st.sidebar.multiselect("Device", sorted(df["Device"].unique()), default=sorted(df["Device"].unique()))
sources = st.sidebar.multiselect("Traffic source", sorted(df["TrafficSource"].unique()),
                                 default=sorted(df["TrafficSource"].unique()))
d = df[df["Date"].between(pd.Timestamp(picked[0]), pd.Timestamp(picked[1]))
       & df["Device"].isin(devices) & df["TrafficSource"].isin(sources)]

st.title("Workora checkout test dashboard")
st.caption("Variant A vs B in the checkout flow, 1 to 22 July 2026. Synthetic learning data, not real Workora results.")
if d.empty:
    st.info("No visitors match these filters. Widen the date range or select more devices and sources.")
    st.stop()

# ------------------------------------------------------------------ KPIs
orders = d[d["Converted"]]
revenue = int(orders["OrderValueINR"].sum())
started = int(d["Started"].sum())
k = st.columns(5)
k[0].metric("Total revenue", inr(revenue), help="Sum of order value for converted visitors.")
k[1].metric("Visitors", f"{len(d):,}", help="Unique visitors in the test. Used as the active-user count.")
k[2].metric("Conversion rate", f"{len(orders) / len(d):.1%}", help="Orders divided by all visitors.")
k[3].metric("Checkout abandonment", f"{1 - len(orders) / started:.1%}" if started else "–",
            help="Visitors who started checkout but did not order. This file has no churn data, so this is the drop-off measure.")
k[4].metric("Avg ticket size", inr(revenue / len(orders)) if len(orders) else "–", help="Revenue divided by orders.")

tab_ov, tab_ex, tab_seg, tab_notes = st.tabs(["Overview", "Variant A vs B", "Segments", "Data notes"])

# ------------------------------------------------------------------ overview
with tab_ov:
    daily = d.groupby("Date").agg(Visitors=("VisitorID", "size"), Orders=("Converted", "sum")).reset_index()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=daily["Date"], y=daily["Visitors"], name="Visitors", marker_color=TEAL)
    fig.add_scatter(x=daily["Date"], y=daily["Orders"], name="Orders", mode="lines+markers",
                    line=dict(color=GOLD, width=3), secondary_y=True)
    fig.update_layout(title="Visitors and orders by day", height=340, margin=dict(l=0, r=0, t=40, b=0),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    l, r = st.columns(2)
    steps = pd.DataFrame({"Step": ["Visitors", "Started checkout", "Ordered"], "Count": [len(d), started, len(orders)]})
    f = px.funnel(steps, x="Count", y="Step", color_discrete_sequence=[TEAL])
    f.update_layout(title="Checkout funnel", margin=dict(l=0, r=0, t=40, b=0), height=300)
    l.plotly_chart(f, use_container_width=True)
    rev = orders.groupby("Device")["OrderValueINR"].sum().reset_index()
    f2 = px.bar(rev, x="Device", y="OrderValueINR", color_discrete_sequence=[GOLD], labels={"OrderValueINR": "Revenue (₹)"})
    f2.update_layout(title="Revenue by device", margin=dict(l=0, r=0, t=40, b=0), height=300, xaxis_title=None)
    r.plotly_chart(f2, use_container_width=True)

# ------------------------------------------------------------------ A vs B
with tab_ex:
    rows = []
    for v in ["A", "B"]:
        g = d[d["Variant"] == v]
        n, o = len(g), int(g["Converted"].sum())
        p = o / n if n else 0.0
        rows.append(dict(v=v, n=n, st=int(g["Started"].sum()), o=o, p=p, ci=1.96 * sqrt(p * (1 - p) / n) if n else 0.0,
                         aov=g.loc[g["Converted"], "OrderValueINR"].mean(), rev=int(g["OrderValueINR"].sum())))
    A, B = rows
    if A["n"] == 0 or B["n"] == 0:
        st.info("Both variants need visitors for a comparison.")
    else:
        pool = (A["o"] + B["o"]) / (A["n"] + B["n"])
        se = sqrt(pool * (1 - pool) * (1 / A["n"] + 1 / B["n"]))
        z = (B["p"] - A["p"]) / se if se else 0.0
        pv = 1 - erf(abs(z) / sqrt(2))
        diff = (B["p"] - A["p"]) * 100
        verdict = ("This difference is statistically significant at the 95% level." if pv < 0.05 else
                   "This difference is not statistically significant at the 95% level, so it could be chance. "
                   "More visitors would be needed to be sure.")
        st.info(f"**Variant B converts {abs(diff):.1f} points {'higher' if diff >= 0 else 'lower'} than A** "
                f"(z = {z:.2f}, p = {pv:.2f}). {verdict}")
        st.dataframe(pd.DataFrame([{"Variant": x["v"], "Visitors": x["n"], "Started checkout": x["st"], "Orders": x["o"],
                                    "Conversion rate": f"{x['p']:.1%} ± {x['ci'] * 100:.1f}",
                                    "Avg order": inr(x["aov"]) if x["o"] else "–", "Revenue": inr(x["rev"])} for x in rows]),
                     hide_index=True, use_container_width=True)
        st.caption("Conversion rate is orders divided by all visitors. The range is a 95% interval.")
        l, r = st.columns(2)
        cv = pd.DataFrame({"Variant": [x["v"] for x in rows], "Conversion (%)": [x["p"] * 100 for x in rows],
                           "err": [x["ci"] * 100 for x in rows]})
        f = px.bar(cv, x="Variant", y="Conversion (%)", error_y="err", color="Variant", color_discrete_map=VCOL)
        f.update_layout(title="Conversion by variant", margin=dict(l=0, r=0, t=40, b=0), height=320, showlegend=False)
        l.plotly_chart(f, use_container_width=True)
        mix = orders.groupby(["OrderValueINR", "Variant"]).size().reset_index(name="Orders")
        mix["OrderValueINR"] = "₹" + mix["OrderValueINR"].astype(str)
        f2 = px.bar(mix, x="OrderValueINR", y="Orders", color="Variant", barmode="group", color_discrete_map=VCOL)
        f2.update_layout(title="Orders by order value", margin=dict(l=0, r=0, t=40, b=0), height=320, xaxis_title=None)
        r.plotly_chart(f2, use_container_width=True)

# ------------------------------------------------------------------ segments
with tab_seg:
    l, r = st.columns(2)
    for box, col, title in [(l, "Device", "Conversion by device"), (r, "TrafficSource", "Conversion by traffic source")]:
        g = d.groupby([col, "Variant"]).agg(rate=("Converted", "mean"), n=("VisitorID", "size")).reset_index()
        g["rate"] *= 100
        f = px.bar(g, x=col, y="rate", color="Variant", barmode="group", color_discrete_map=VCOL,
                   hover_data={"n": True}, labels={"rate": "Conversion (%)", col: ""})
        f.update_layout(title=title, margin=dict(l=0, r=0, t=40, b=0), height=320)
        box.plotly_chart(f, use_container_width=True)
    hm = d.pivot_table(index="Device", columns="TrafficSource", values="Converted", aggfunc="mean")
    f = px.imshow(hm, text_auto=".1%", color_continuous_scale="Teal", aspect="auto")
    f.update_layout(title="Conversion rate by device and traffic source", margin=dict(l=0, r=0, t=40, b=0), height=320,
                    coloraxis_showscale=False)
    st.plotly_chart(f, use_container_width=True)
    hr = d.groupby("Hour").agg(Visitors=("VisitorID", "size"), Orders=("Converted", "sum")).reset_index()
    f = px.bar(hr, x="Hour", y=["Visitors", "Orders"], barmode="group", color_discrete_sequence=[TEAL, GOLD])
    f.update_layout(title="Visitors and orders by hour of day", margin=dict(l=0, r=0, t=40, b=0), height=320,
                    yaxis_title=None, legend_title=None)
    st.plotly_chart(f, use_container_width=True)

# ------------------------------------------------------------------ notes
with tab_notes:
    st.markdown(f"""
### What the data contains
One row per visitor ({checks['rows']:,} rows): variant (A or B), visit time, device, traffic source, whether checkout started, whether the visitor ordered, and order value in rupees.

### Quality checks
- Duplicate visitor IDs: {checks['dups']}. Missing values: {checks['nulls']}.
- Orders without a checkout start: {checks['conv_no_start']}. Order value on non-orders: {checks['value_no_order']}. Orders with no value: {checks['order_no_value']}.
- Nothing needed cleaning or was excluded.

### Calculated fields
- **Total revenue:** sum of order value for converted visitors.
- **Visitors:** unique visitors, used as the active-user count.
- **Conversion rate:** orders divided by visitors.
- **Checkout abandonment:** visitors who started checkout and did not order, divided by visitors who started. Used in place of churn, which this file does not contain.
- **Avg ticket size:** revenue divided by orders.
- **Significance test:** two-sided two-proportion z-test on conversion.

### Limits
- The file covers 22 days in one month and has no region, customer ID or repeat-visit data, so churn and regional views are not possible.
- Synthetic data, so patterns are illustrative only.
""")
