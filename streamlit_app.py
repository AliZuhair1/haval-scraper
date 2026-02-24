"""
HAVAL Used Car Market Report — Streamlit Web UI
"""
import streamlit as st
import pandas as pd
from collections import defaultdict

from haval_scraper import (
    MODELS, PURCHASES,
    scrape_iqcars, scrape_opensooq, to_iqd, fmt_iqd,
)

st.set_page_config(page_title="HAVAL Market Report", page_icon="🚗", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────
st.sidebar.title("HAVAL Market Report")
st.sidebar.caption("IQCars.net + OpenSouq.com")

model_options = ["All Models"] + list(MODELS.keys())
selected = st.sidebar.selectbox("Model", model_options)

if selected == "All Models":
    selected_models = list(MODELS.keys())
else:
    selected_models = [selected]

year_options = ["All Years"] + [str(y) for y in range(2026, 2018, -1)]
year_choice = st.sidebar.selectbox("Year", year_options)
year_filter = int(year_choice) if year_choice != "All Years" else None

usd_to_iqd = st.sidebar.number_input("USD → IQD Rate", value=1500, min_value=1000, max_value=2000, step=50)

run = st.sidebar.button("Run Scraper", type="primary", use_container_width=True)

# ── Main ─────────────────────────────────────────────────────────
st.title("🚗 HAVAL Used Car Market — Iraq")

if not run:
    st.info("Pick a **Model** and **Year** from the sidebar, then click **Run Scraper**.")
    st.stop()

# ── Scrape ───────────────────────────────────────────────────────
progress = st.progress(0, text="Starting...")
all_listings = []
tasks = []
for m in selected_models:
    if "iqcars" in MODELS[m]:
        tasks.append(("iqcars", m))
    if "opensooq" in MODELS[m]:
        tasks.append(("opensooq", m))

for i, (source, model) in enumerate(tasks):
    progress.progress(i / len(tasks), text=f"{source} → HAVAL {model}...")
    if source == "iqcars":
        results = scrape_iqcars(model, MODELS[model]["iqcars"], usd_to_iqd)
    else:
        results = scrape_opensooq(model, MODELS[model]["opensooq"], usd_to_iqd)
    if results:
        all_listings.extend(results)

progress.progress(1.0, text="Done!")

# ── Deduplicate + Filter ────────────────────────────────────────
seen = set()
unique = []
for l in all_listings:
    key = (l["model"], l["year"], l["mileage_km"], l["price_original"], l["source"])
    if key not in seen:
        seen.add(key)
        unique.append(l)

if year_filter:
    unique = [l for l in unique if l["year"] == str(year_filter)]
unique = [l for l in unique if l.get("price_iqd") and l["price_iqd"] > 0]

# Remove outliers (> 3x median per model)
by_model_prices = defaultdict(list)
for l in unique:
    by_model_prices[l["model"]].append(l["price_iqd"])
for mdl, prices in by_model_prices.items():
    if len(prices) < 3:
        continue
    median = sorted(prices)[len(prices) // 2]
    for l in unique:
        if l["model"] == mdl and l["price_iqd"] > median * 3:
            l["_outlier"] = True
outliers = [l for l in unique if l.get("_outlier")]
unique = [l for l in unique if not l.get("_outlier")]

if outliers:
    st.warning(f"Excluded {len(outliers)} price outlier(s)")

if not unique:
    st.error("No listings found. Try a different model or remove the year filter.")
    st.stop()

# ── Summary Metrics ──────────────────────────────────────────────
all_prices = [l["price_iqd"] for l in unique]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Listings", len(unique))
col2.metric("Avg Price", fmt_iqd(sum(all_prices) // len(all_prices)))
col3.metric("Min Price", fmt_iqd(min(all_prices)))
col4.metric("Max Price", fmt_iqd(max(all_prices)))

# ── Listings Table ───────────────────────────────────────────────
st.subheader(f"All Listings ({len(unique)})")
df = pd.DataFrame(unique)
display_df = df[["source", "model", "year", "mileage_range", "trim", "city", "price_iqd", "url"]].copy()
display_df.columns = ["Source", "Model", "Year", "Mileage", "Trim", "City", "Price (IQD)", "Link"]
display_df["Price (IQD)"] = display_df["Price (IQD)"].apply(fmt_iqd)
display_df["Mileage"] = display_df["Mileage"].replace({"0": "N/A", "": "N/A"})

st.dataframe(
    display_df,
    use_container_width=True,
    column_config={"Link": st.column_config.LinkColumn("Link", display_text="View")},
    hide_index=True,
)

# ── Market Price Report ──────────────────────────────────────────
st.subheader("Market Price Summary")
by_model = defaultdict(list)
for l in unique:
    by_model[l["model"]].append(l["price_iqd"])

rows = []
for mdl, prices in sorted(by_model.items()):
    prices.sort()
    rows.append({
        "Model": mdl,
        "Count": len(prices),
        "Min": fmt_iqd(min(prices)),
        "Max": fmt_iqd(max(prices)),
        "Average": fmt_iqd(sum(prices) // len(prices)),
        "Median": fmt_iqd(prices[len(prices) // 2]),
    })
st.table(pd.DataFrame(rows))

# ── Price by Model + Year ────────────────────────────────────────
st.subheader("Price by Model + Year")
by_year = defaultdict(list)
for l in unique:
    by_year[(l["model"], l["year"])].append(l["price_iqd"])

rows = []
for (mdl, year), prices in sorted(by_year.items()):
    prices.sort()
    rows.append({
        "Model": mdl,
        "Year": year,
        "Count": len(prices),
        "Min": fmt_iqd(min(prices)),
        "Max": fmt_iqd(max(prices)),
        "Average": fmt_iqd(sum(prices) // len(prices)),
    })
st.table(pd.DataFrame(rows))

# ── City Distribution ────────────────────────────────────────────
st.subheader("Listings by City")
by_city = defaultdict(int)
for l in unique:
    if l["city"] and l["city"] != "N/A":
        by_city[l["city"]] += 1
if by_city:
    city_df = pd.DataFrame(
        sorted(by_city.items(), key=lambda x: -x[1]),
        columns=["City", "Count"],
    )
    st.bar_chart(city_df.set_index("City"))

# ── NAI Purchase vs Market ───────────────────────────────────────
selected_set = set(selected_models)
haval_purchases = [p for p in PURCHASES if p["model"] in selected_set]
if year_filter:
    haval_purchases = [p for p in haval_purchases if p["year"] == str(year_filter)]

if haval_purchases:
    st.subheader("NAI Purchase vs Market")

    market = defaultdict(lambda: defaultdict(list))
    market_all = defaultdict(list)
    for l in unique:
        mdl = l["model"].replace("HAVAL ", "")
        market[mdl][l["year"]].append(l["price_iqd"])
        market_all[mdl].append(l["price_iqd"])

    def stats(prices):
        if not prices:
            return None, None, None, None
        prices = sorted(prices)
        return min(prices), max(prices), sum(prices) // len(prices), prices[len(prices) // 2]

    rows = []
    for p in sorted(haval_purchases, key=lambda x: x["model"]):
        mdl, yr = p["model"], p["year"]
        mkt_prices = market.get(mdl, {}).get(yr, []) or market_all.get(mdl, [])
        _, _, m_avg, _ = stats(mkt_prices)

        if m_avg:
            diff = p["price_iqd"] - m_avg
            diff_pct = (diff / m_avg) * 100
            if diff_pct < -10:
                status = "🟢 GOOD DEAL"
            elif diff_pct < -5:
                status = "🟢 Below Mkt"
            elif diff_pct > 10:
                status = "🔴 OVERPAID"
            elif diff_pct > 5:
                status = "🟡 Above Mkt"
            else:
                status = "⚪ Fair"
            diff_str = f"{diff/1_000_000:+.1f}M ({diff_pct:+.0f}%)"
        else:
            diff_str = "N/A"
            status = "— No data"

        rows.append({
            "Product": p["product"],
            "Year": yr,
            "KM": f"{p['km']:,}" if p["km"] > 0 else "New",
            "Your Price": fmt_iqd(p["price_iqd"]),
            "Market Avg": fmt_iqd(m_avg) if m_avg else "N/A",
            "Diff": diff_str,
            "Status": status,
        })
    st.table(pd.DataFrame(rows))

# ── CSV Download ─────────────────────────────────────────────────
csv_df = df[["source", "model", "year", "mileage_km", "mileage_range", "trim", "city",
             "condition", "price_original", "currency_original", "price_iqd", "url", "scraped_at"]]
st.download_button(
    "📥 Download CSV",
    csv_df.to_csv(index=False),
    file_name="haval_listings.csv",
    mime="text/csv",
    use_container_width=True,
)
