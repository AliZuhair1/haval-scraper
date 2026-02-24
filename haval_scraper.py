#!/usr/bin/env python3
"""
HAVAL Used Car Market Report — Iraq
=====================================
Scrapes IQCars.net + OpenSouq.com using __NEXT_DATA__ JSON (both are Next.js)

Setup:
    pip3 install requests beautifulsoup4 lxml

Run:
    python3 haval_scraper.py
    python3 haval_scraper.py --debug   # saves raw HTML + JSON for troubleshooting
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import re
import sys
import os
from datetime import datetime
from collections import defaultdict

DEBUG = "--debug" in sys.argv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    # NOTE: Do NOT add "Accept-Encoding: br" — requests can't decode brotli
    # without the brotli package, causing garbled responses (31KB vs 450KB)
    "Accept-Encoding": "gzip, deflate",
}

MODELS = {
    "H6": {
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/h6",
        "opensooq": "https://iq.opensooq.com/en/cars/cars-for-sale/haval/haval-h6",
    },
    "H6 GT": {
        # OpenSouq merged H6 GT into H6 (URL returns 410)
        # H6 GT listings appear as trim under H6 on OpenSouq
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/h6-gt",
    },
    "H7": {
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/h7",
        "opensooq": "https://iq.opensooq.com/en/cars/cars-for-sale/haval/haval-h7",
    },
    "H9": {
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/h9",
        "opensooq": "https://iq.opensooq.com/en/cars/cars-for-sale/haval/haval-h9",
    },
    "Jolion": {
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/jolion",
        "opensooq": "https://iq.opensooq.com/en/cars/cars-for-sale/haval/model-haval-jolion",
    },
    "Dargo": {
        "iqcars": "https://www.iqcars.net/en/buy-cars/iraq/all/haval/dargo",
        "opensooq": "https://iq.opensooq.com/en/cars/cars-for-sale/haval/model-haval-dargo",
    },
}

# ── NAI Purchase History (from Odoo) ─────────────────────────────
# Map product names to scraper model categories
# Models not in HAVAL lineup (TANK 300, ORA, POER) are kept for reference
PURCHASES = [
    {"product": "H6 Top BE 4X2",  "model": "H6",     "price_iqd": 23_000_000, "date": "2026-02-11", "year": "2024", "km": 14458,  "vin": "LGWEF6A52RH945099"},
    {"product": "TANK 300",       "model": "TANK 300","price_iqd": 33_000_000, "date": "2026-01-23", "year": "2023", "km": 62180,  "vin": "LGWFF7A59PJ622961"},
    {"product": "TANK 300",       "model": "TANK 300","price_iqd": 42_000_000, "date": "2026-02-07", "year": "2025", "km": 668,    "vin": "LGWFFSA58SJ615947"},
    {"product": "HAVAL H9",       "model": "H9",     "price_iqd": 43_000_000, "date": "2026-01-18", "year": "2025", "km": 1000,   "vin": "LGWFF7A60SJ617441"},
    {"product": "TANK 300",       "model": "TANK 300","price_iqd": 39_000_000, "date": "2026-01-12", "year": "2025", "km": 12,     "vin": "LGWFFSA52SJ631528"},
    {"product": "HAVAL H9",       "model": "H9",     "price_iqd": 47_000_000, "date": "2025-12-23", "year": "2026", "km": 0,      "vin": "LGWFF7A60TJ617375"},
    {"product": "H6 HYBRID",      "model": "H6",     "price_iqd": 29_000_000, "date": "2025-12-15", "year": "2025", "km": 17,     "vin": "LGWEFUA55SH948590"},
    {"product": "JOLION Top 4X2", "model": "Jolion",  "price_iqd": 25_000_000, "date": "2025-12-13", "year": "2025", "km": 14,     "vin": "LGWEE4A54SK622513"},
    {"product": "ORA",            "model": "ORA",     "price_iqd": 25_000_000, "date": "2025-12-01", "year": "2023", "km": 153,    "vin": "LGWEEUA59PK617167"},
    {"product": "POER GF Top",    "model": "POER",    "price_iqd": 25_000_000, "date": "2025-11-11", "year": "2024", "km": 8,      "vin": "LGWDB6198RJ620511"},
    {"product": "H6 Top BE 4X2",  "model": "H6",     "price_iqd": 28_000_000, "date": "2025-10-29", "year": "2024", "km": 8830,   "vin": "LGWEF6A58RH954907"},
    {"product": "DARGO Top 4X4",  "model": "Dargo",   "price_iqd": 27_000_000, "date": "2025-08-26", "year": "2023", "km": 16051,  "vin": "LGWFF6A52PH943287"},
    {"product": "H6 HYBRID",      "model": "H6",     "price_iqd": 32_500_000, "date": "2025-10-14", "year": "2026", "km": 0,      "vin": "LGWEFUA54TH903643"},
    {"product": "H6 Top BE 4X2",  "model": "H6",     "price_iqd": 28_000_000, "date": "2025-10-07", "year": "2024", "km": 4721,   "vin": "LGWEF6A55RH945145"},
    {"product": "H6 HYBRID",      "model": "H6",     "price_iqd": 31_000_000, "date": "2025-10-04", "year": "2026", "km": 0,      "vin": "LGWEFUA50TH903655"},
    {"product": "H6 HYBRID",      "model": "H6",     "price_iqd": 28_000_000, "date": "2025-09-13", "year": "2026", "km": 0,      "vin": "LGWEFUA51TH903664"},
    {"product": "TANK 300",       "model": "TANK 300","price_iqd": 47_100_000, "date": "2025-10-05", "year": "2026", "km": 0,      "vin": "LGWFFSA51TJ613605"},
    {"product": "H6 GT",          "model": "H6 GT",   "price_iqd": 22_000_000, "date": "2025-09-22", "year": "2024", "km": 94601,  "vin": "LGWFF6A57RH923152"},
    {"product": "H6 GT",          "model": "H6 GT",   "price_iqd": 23_000_000, "date": "2025-09-22", "year": "2024", "km": 115000, "vin": "LGWFF6A57RH923149"},
    {"product": "JOLION Top 4X2", "model": "Jolion",  "price_iqd": 20_000_000, "date": "2025-09-22", "year": "2024", "km": 70597,  "vin": "LGWEE4A52RK610452"},
    {"product": "JOLION Low 4X2", "model": "Jolion",  "price_iqd": 18_000_000, "date": "2025-09-22", "year": "2024", "km": 34467,  "vin": "LGWEE4A56RK611667"},
    {"product": "H6 GT",          "model": "H6 GT",   "price_iqd": 22_000_000, "date": "2025-09-22", "year": "2024", "km": 97201,  "vin": "LGWFF6A53RH931023"},
    {"product": "JOLION Top 4X2", "model": "Jolion",  "price_iqd": 20_000_000, "date": "2025-09-10", "year": "2023", "km": 10655,  "vin": "LGWEE4A5XPK620031"},
    {"product": "H6 GT",          "model": "H6 GT",   "price_iqd": 28_500_000, "date": "2025-09-06", "year": "2023", "km": 28885,  "vin": "LGWFF6A52PH917594"},
    {"product": "H6 GT",          "model": "H6 GT",   "price_iqd": 32_500_000, "date": "2025-08-13", "year": "2024", "km": 8148,   "vin": "LGWFF6A53RH941454"},
    {"product": "TANK 300",       "model": "TANK 300","price_iqd": 33_000_000, "date": "2025-08-07", "year": "2023", "km": 74054,  "vin": "LGWFF7A55PJ618406"},
    {"product": "ORA",            "model": "ORA",     "price_iqd": 27_000_000, "date": "2025-08-03", "year": "2023", "km": 0,      "vin": "LGWEEUA58PK617158"},
    {"product": "JOLION Top 4X2", "model": "Jolion",  "price_iqd": 21_500_000, "date": "2025-08-01", "year": "2024", "km": 36237,  "vin": "LGWEE4A54RK610453"},
]

# Filter to only HAVAL models that match our scraper
HAVAL_MODELS_SET = set(MODELS.keys())


# ── Helpers ───────────────────────────────────────────────────────
def to_iqd(price, currency, usd_to_iqd):
    if price is None or price == 0:
        return None
    if currency == "IQD":
        return price
    if currency == "USD":
        return round(price * usd_to_iqd)
    return None


def fmt_iqd(val):
    if val is None:
        return "N/A"
    if val >= 1_000_000:
        return f"{val / 1_000_000:,.1f}M IQD"
    return f"{val:,} IQD"


def save_debug(source, model, suffix, content):
    if not DEBUG:
        return
    os.makedirs("debug", exist_ok=True)
    fname = f"debug/{source}_{model.replace(' ', '_')}.{suffix}"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"    [debug] saved -> {fname}")


def extract_next_data(html):
    """Extract __NEXT_DATA__ JSON from a Next.js page."""
    match = re.search(r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


# ── Interactive Menu ──────────────────────────────────────────────
def show_menu():
    print()
    print("=" * 55)
    print("  HAVAL Used Car Market Report — Iraq")
    print("      IQCars.net  +  OpenSouq.com")
    print("=" * 55)

    rate_input = input("\n  1 USD = ? IQD (e.g. 1500, Enter for 1500): ").strip()
    usd_to_iqd = int(rate_input) if rate_input.isdigit() else 1500
    print(f"     Using rate: 1 USD = {usd_to_iqd:,} IQD")

    model_names = list(MODELS.keys())
    print("\n  Choose model:")
    for i, name in enumerate(model_names, 1):
        print(f"    {i}. HAVAL {name}")
    print(f"    {len(model_names) + 1}. All models")

    while True:
        choice = input(f"\n  Enter choice [1-{len(model_names) + 1}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(model_names) + 1:
            break
        print("  Invalid choice, try again.")

    choice = int(choice)
    if choice == len(model_names) + 1:
        selected_models = model_names
    else:
        selected_models = [model_names[choice - 1]]

    year_input = input("\n  Filter by year (e.g. 2022) or Enter for all: ").strip()
    year_filter = int(year_input) if year_input.isdigit() else None

    return selected_models, year_filter, usd_to_iqd


# ── IQCars scraper (__NEXT_DATA__) ───────────────────────────────
def scrape_iqcars(model, url, usd_to_iqd):
    """
    IQCars __NEXT_DATA__ structure:
      props.pageProps.data.data[] = array of car objects
      Each car: ID, Year.YearName, Brand.BrandNameen, Model.ModelNameen,
                ModelSFX.SFXName (trim), VisitedKm, Price (USD), PriceIQD,
                PriceUnit (1=USD, 2=IQD), Location.LocationNameen,
                CarCondition.CarConditionNameen
    """
    listings = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()

        save_debug("iqcars", model, "html", resp.text)

        # Try __NEXT_DATA__ first (best source)
        next_data = extract_next_data(resp.text)
        if next_data:
            save_debug("iqcars", model, "json", json.dumps(next_data, indent=2, ensure_ascii=False))

            # Navigate to car list: props.pageProps.data.data
            try:
                cars = next_data["props"]["pageProps"]["data"]["data"]
            except (KeyError, TypeError):
                cars = []
                if DEBUG:
                    print(f"    [debug] __NEXT_DATA__ found but path props.pageProps.data.data missing")
                    # Try to show available keys
                    try:
                        pp = next_data.get("props", {}).get("pageProps", {})
                        print(f"    [debug] pageProps keys: {list(pp.keys())[:10]}")
                    except:
                        pass

            for car in cars:
                try:
                    # Year
                    year_obj = car.get("Year") or {}
                    year = str(year_obj.get("YearName", "")) if isinstance(year_obj, dict) else ""

                    # Mileage
                    mileage_km = car.get("VisitedKm", 0)
                    if mileage_km is None:
                        mileage_km = 0
                    mileage_km = int(mileage_km)

                    # Trim
                    sfx = car.get("ModelSFX") or {}
                    trim = sfx.get("SFXName", "N/A") if isinstance(sfx, dict) else "N/A"
                    if not trim:
                        trim = "N/A"

                    # City
                    loc = car.get("Location") or {}
                    city = loc.get("LocationNameen", "N/A") if isinstance(loc, dict) else "N/A"
                    if not city:
                        city = "N/A"

                    # Price: PriceUnit 1=USD, 2=IQD
                    price_unit = car.get("PriceUnit", 1)
                    if price_unit == 2:
                        price_val = int(car.get("PriceIQD", 0) or 0)
                        currency = "IQD"
                    else:
                        price_val = int(car.get("Price", 0) or 0)
                        currency = "USD"

                    # Condition
                    cond_obj = car.get("CarCondition") or {}
                    condition = cond_obj.get("CarConditionNameen", "Used") if isinstance(cond_obj, dict) else "Used"

                    # URL
                    car_id = car.get("ID", "")
                    listing_url = f"https://www.iqcars.net/en/car/{car_id}" if car_id else url

                    price_iqd = to_iqd(price_val, currency, usd_to_iqd)

                    listings.append({
                        "source": "IQCars",
                        "model": f"HAVAL {model}",
                        "year": year,
                        "mileage_km": str(mileage_km),
                        "mileage_range": f"{mileage_km:,} km" if mileage_km > 0 else "N/A",
                        "trim": trim,
                        "city": city,
                        "condition": condition or "Used",
                        "price_original": price_val,
                        "currency_original": currency,
                        "price_iqd": price_iqd,
                        "url": listing_url,
                        "scraped_at": datetime.now().isoformat(),
                    })
                except Exception as e:
                    if DEBUG:
                        print(f"    [debug] Error parsing car: {e}")
                    continue

            if listings:
                return listings

        # Fallback 1: JSON-LD (can be a list [BreadcrumbList, ItemList] or dict)
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue
            # Normalize to list
            objects = raw if isinstance(raw, list) else [raw]
            for data in objects:
                if not isinstance(data, dict):
                    continue
                if data.get("@type") != "ItemList":
                    continue
                for el in data.get("itemListElement", []):
                    offers = el.get("offers", {})
                    try:
                        price_val = int(float(str(offers.get("price", 0))))
                    except (ValueError, TypeError):
                        price_val = 0
                    currency = offers.get("priceCurrency", "IQD")
                    name = el.get("name", "")
                    year_m = re.search(r'(20[12]\d)', name)
                    year = year_m.group(1) if year_m else ""
                    price_iqd = to_iqd(price_val, currency, usd_to_iqd)

                    city_m = re.search(r'in Iraq\s*-\s*(.+)', name)
                    city = city_m.group(1).strip() if city_m else "N/A"

                    listings.append({
                        "source": "IQCars",
                        "model": f"HAVAL {model}",
                        "year": year,
                        "mileage_km": "0",
                        "mileage_range": "N/A",
                        "trim": "N/A",
                        "city": city,
                        "condition": "Used",
                        "price_original": price_val,
                        "currency_original": currency,
                        "price_iqd": price_iqd,
                        "url": el.get("url", url),
                        "scraped_at": datetime.now().isoformat(),
                    })

        if listings:
            return listings

        # Fallback 2: MUI card HTML parsing (IQCars uses Material-UI cards)
        cards = soup.select("div.MuiCard-root.desktopContainer")
        if DEBUG and not cards:
            print(f"    [debug] No MUI cards found, trying other selectors")
        if not cards:
            cards = soup.select("div.MuiCard-root")
        for card in cards:
            try:
                text = card.get_text(separator=" ", strip=True)
                year_m = re.search(r'(20[12]\d)', text)
                if not year_m:
                    continue
                year = year_m.group(1)

                # Mileage: "49,000 km"
                km_m = re.search(r'([\d,]+)\s*km', text, re.I)
                mileage_km = km_m.group(1).replace(",", "") if km_m else "0"

                # Trim: 3rd info span (Premium, LUX, Supreme, etc.)
                info_spans = card.select("div.MuiBox-root span.MuiTypography-title1")
                trim = "N/A"
                if len(info_spans) >= 3:
                    trim_text = info_spans[2].get_text(strip=True)
                    if trim_text and "km" not in trim_text.lower() and not trim_text.isdigit():
                        trim = trim_text

                # City: span near location icon
                city = "N/A"
                loc_img = card.find("img", alt="location")
                if loc_img:
                    city_span = loc_img.find_next("span")
                    if city_span:
                        city = city_span.get_text(strip=True)

                # Price: FontPrice class
                price_val, currency = 0, "USD"
                font_price = card.select("span.FontPrice")
                font_price_last = card.select("span.FontPriceLastDigits")
                dinar_label = card.find("span", string=re.compile(r'Dinar', re.I))

                if font_price:
                    price_text = "".join(sp.get_text(strip=True) for sp in font_price)
                    if font_price_last:
                        price_text += "".join(sp.get_text(strip=True) for sp in font_price_last)
                    price_clean = re.sub(r'[^\d]', '', price_text.replace("$", "").replace(",", ""))
                    try:
                        price_val = int(price_clean)
                    except ValueError:
                        price_val = 0

                    if dinar_label or price_val > 100_000:
                        currency = "IQD"
                    elif "$" in price_text:
                        currency = "USD"

                price_iqd = to_iqd(price_val, currency, usd_to_iqd)

                # Listing URL
                listing_url = url
                parent_a = card.find_parent("a", href=True)
                if parent_a:
                    href = parent_a["href"]
                    listing_url = href if href.startswith("http") else f"https://www.iqcars.net{href}"

                listings.append({
                    "source": "IQCars",
                    "model": f"HAVAL {model}",
                    "year": year,
                    "mileage_km": mileage_km,
                    "mileage_range": f"{int(mileage_km):,} km" if mileage_km.isdigit() and int(mileage_km) > 0 else "N/A",
                    "trim": trim,
                    "city": city,
                    "condition": "Used",
                    "price_original": price_val,
                    "currency_original": currency,
                    "price_iqd": price_iqd,
                    "url": listing_url,
                    "scraped_at": datetime.now().isoformat(),
                })
            except Exception as e:
                if DEBUG:
                    print(f"    [debug] Card parse error: {e}")
                continue

        if listings:
            return listings

        # Fallback 3: scan all <a> tags for car links (last resort)
        all_links = soup.find_all("a", attrs={"name": "car"}, href=True)
        if not all_links:
            all_links = [a for a in soup.find_all("a", href=True)
                         if re.search(r'/car/.*haval', a.get("href", ""), re.I)]
        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(separator=" ", strip=True)
            year_m = re.search(r'(20[12]\d)', text)
            if not year_m:
                continue
            year = year_m.group()
            price_val, currency = 0, "USD"
            prices = re.findall(r'([\d,]{4,})', text)
            for p in prices:
                pint = int(p.replace(",", ""))
                if pint > 5000:
                    if pint > 100_000:
                        price_val, currency = pint, "IQD"
                    else:
                        price_val, currency = pint, "USD"
                    break
            km_m = re.search(r'([\d,]+)\s*km', text, re.I)
            mileage_km = km_m.group(1).replace(",", "") if km_m else "0"
            price_iqd = to_iqd(price_val, currency, usd_to_iqd)
            listing_url = href if href.startswith("http") else f"https://www.iqcars.net{href}"

            listings.append({
                "source": "IQCars",
                "model": f"HAVAL {model}",
                "year": year,
                "mileage_km": mileage_km,
                "mileage_range": f"{int(mileage_km):,} km" if mileage_km.isdigit() and int(mileage_km) > 0 else "N/A",
                "trim": "N/A",
                "city": "N/A",
                "condition": "Used",
                "price_original": price_val,
                "currency_original": currency,
                "price_iqd": price_iqd,
                "url": listing_url,
                "scraped_at": datetime.now().isoformat(),
            })

    except requests.exceptions.RequestException as e:
        print(f"    Error: {e}")

    return listings


# ── OpenSouq scraper (__NEXT_DATA__ + JSON-LD fallback) ──────────
def scrape_opensooq(model, url, usd_to_iqd):
    """
    OpenSouq __NEXT_DATA__ structure:
      props.pageProps.serpApiResponse.listings.items[] = array of listing objects
      Each listing: id, title, price_amount, price_currency_iso,
                    city_label, nhood_label, cps[] (specs array),
                    highlightsObject (car_trim, Car_Year, Kilometers_Cars, etc.)
      Pagination: listings.meta.pages, listings.meta.current_page
    """
    listings = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()

        save_debug("opensooq", model, "html", resp.text)

        # Try __NEXT_DATA__ first
        next_data = extract_next_data(resp.text)
        if next_data:
            save_debug("opensooq", model, "json", json.dumps(next_data, indent=2, ensure_ascii=False))

            try:
                serp = next_data["props"]["pageProps"]["serpApiResponse"]
                items = serp["listings"]["items"]
                meta = serp["listings"].get("meta", {})
            except (KeyError, TypeError):
                items = []
                meta = {}
                if DEBUG:
                    print(f"    [debug] __NEXT_DATA__ found but serpApiResponse path missing")
                    try:
                        pp = next_data.get("props", {}).get("pageProps", {})
                        print(f"    [debug] pageProps keys: {list(pp.keys())[:10]}")
                    except:
                        pass

            if DEBUG and meta:
                print(f"    [debug] OpenSouq meta: {meta.get('count', '?')} total, page {meta.get('current_page', '?')}/{meta.get('pages', '?')}")

            for item in items:
                try:
                    # Year, trim, mileage from highlightsObject
                    highlights = item.get("highlightsObject", {})

                    year_list = highlights.get("Car_Year", [])
                    year = year_list[0].get("label", "") if year_list else ""

                    trim_list = highlights.get("car_trim", [])
                    trim = trim_list[0].get("label", "N/A") if trim_list else "N/A"
                    if not trim:
                        trim = "N/A"

                    km_list = highlights.get("Kilometers_Cars", [])
                    km_label = km_list[0].get("label", "0") if km_list else "0"
                    # Parse range like "20,000 - 29,999" to midpoint
                    km_nums = re.findall(r'(\d+)', km_label.replace(",", ""))
                    if len(km_nums) >= 2:
                        mileage_km = (int(km_nums[0]) + int(km_nums[1])) // 2
                    elif len(km_nums) == 1:
                        mileage_km = int(km_nums[0])
                    else:
                        mileage_km = 0

                    # City
                    city = item.get("city_label", "N/A")
                    if not city:
                        city = "N/A"

                    # Price
                    price_str = item.get("price_amount", "0")
                    # price_amount comes as "32,000,000 IQD" or "32,000,000 USD"
                    price_clean = re.sub(r'[^\d]', '', str(price_str).split(" ")[0].replace(",", ""))
                    try:
                        price_val = int(price_clean) if price_clean else 0
                    except ValueError:
                        price_val = 0

                    currency = item.get("price_currency_iso", "IQD")
                    if not currency:
                        # Try to detect from price_amount string
                        if "USD" in str(price_str) or "$" in str(price_str):
                            currency = "USD"
                        else:
                            currency = "IQD"

                    # Fix mismatched currency: some listings show "USD" but value is clearly IQD
                    if currency == "USD" and price_val > 1_000_000:
                        currency = "IQD"

                    # Condition
                    cond_list = highlights.get("ConditionUsed", []) or highlights.get("ConditionNew", [])
                    condition = cond_list[0].get("label", "Used") if cond_list else "Used"

                    listing_url = item.get("post_url", "")
                    if listing_url and not listing_url.startswith("http"):
                        listing_url = f"https://iq.opensooq.com{listing_url}"

                    price_iqd = to_iqd(price_val, currency, usd_to_iqd)

                    listings.append({
                        "source": "OpenSouq",
                        "model": f"HAVAL {model}",
                        "year": str(year),
                        "mileage_km": str(mileage_km),
                        "mileage_range": km_label if km_label != "0" else "N/A",
                        "trim": trim,
                        "city": city,
                        "condition": condition,
                        "price_original": price_val,
                        "currency_original": currency,
                        "price_iqd": price_iqd,
                        "url": listing_url or url,
                        "scraped_at": datetime.now().isoformat(),
                    })
                except Exception as e:
                    if DEBUG:
                        print(f"    [debug] Error parsing item: {e}")
                    continue

            if listings:
                return listings

        # Fallback: JSON-LD (ItemList with Vehicle entries)
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            # JSON-LD can be a dict with @graph or a direct object
            objects = []
            if isinstance(raw, dict):
                if "@graph" in raw:
                    objects = raw["@graph"]
                else:
                    objects = [raw]
            elif isinstance(raw, list):
                objects = raw

            for obj in objects:
                if obj.get("@type") != "ItemList":
                    continue
                for el in obj.get("itemListElement", []):
                    vehicle = el.get("item", el)
                    if vehicle.get("@type") != "Vehicle":
                        continue

                    name = vehicle.get("name", "")
                    year = vehicle.get("vehicleModelDate", "")
                    config = vehicle.get("vehicleConfiguration", "")

                    mileage_obj = vehicle.get("mileageFromOdometer", {})
                    mileage_raw = mileage_obj.get("value", "0") if isinstance(mileage_obj, dict) else "0"
                    km_nums = re.findall(r'(\d+)', mileage_raw.replace(",", ""))
                    if len(km_nums) >= 2:
                        mileage_km = (int(km_nums[0]) + int(km_nums[1])) // 2
                    elif len(km_nums) == 1:
                        mileage_km = int(km_nums[0])
                    else:
                        mileage_km = 0

                    offers = vehicle.get("offers", {})
                    price_val = int(float(str(offers.get("price", 0)).replace(",", "")))
                    currency = offers.get("priceCurrency", "IQD")
                    if currency == "USD" and price_val > 1_000_000:
                        currency = "IQD"

                    city_m = re.search(r'\bin\s+(\w[\w\s]*?)$', name)
                    city = city_m.group(1).strip() if city_m else "N/A"

                    trim = "N/A"
                    if config:
                        parts = [p.strip() for p in config.split(",")]
                        trim_parts = [p for p in parts if not p.isdigit() and p.upper() not in ("SUV", "SEDAN", "HATCHBACK")]
                        if trim_parts:
                            trim = trim_parts[0]

                    price_iqd = to_iqd(price_val, currency, usd_to_iqd)

                    listings.append({
                        "source": "OpenSouq",
                        "model": f"HAVAL {model}",
                        "year": str(year),
                        "mileage_km": str(mileage_km),
                        "mileage_range": mileage_raw if mileage_raw != "0" else "N/A",
                        "trim": trim,
                        "city": city,
                        "condition": "Used",
                        "price_original": price_val,
                        "currency_original": currency,
                        "price_iqd": price_iqd,
                        "url": vehicle.get("url", url),
                        "scraped_at": datetime.now().isoformat(),
                    })

    except requests.exceptions.RequestException as e:
        print(f"    Error: {e}")

    return listings


# ── Report ────────────────────────────────────────────────────────
def print_report(listings, year_filter, usd_to_iqd, selected_models=None):
    if not listings:
        print("\n  No listings found.")
        print("  Tips:")
        print("    - Run with --debug to save raw HTML + JSON for inspection")
        print("    - Check if sites are accessible from your network")
        return

    # All listings table
    print(f"\n{'=' * 115}")
    title = f"ALL LISTINGS ({len(listings)})"
    if year_filter:
        title += f" | Year: {year_filter}"
    title += f"  |  Rate: 1 USD = {usd_to_iqd:,} IQD"
    print(f"  {title}")
    print(f"{'=' * 115}")
    print(f"  {'#':<4} {'Model':<14} {'Year':<6} {'Mileage':<18} {'Trim':<14} {'City':<16} {'Price (IQD)':<20} {'Source'}")
    print(f"  {'-' * 110}")

    sorted_listings = sorted(listings, key=lambda x: (x["model"], x.get("price_iqd") or 0))
    for i, l in enumerate(sorted_listings, 1):
        price_str = fmt_iqd(l["price_iqd"])
        if l["currency_original"] == "USD" and l["price_original"]:
            price_str += f"  (${l['price_original']:,})"
        mileage_display = l.get("mileage_range", "N/A")
        if mileage_display in ("0", "", "N/A"):
            mileage_display = "N/A"
        print(f"  {i:<4} {l['model']:<14} {l['year']:<6} {mileage_display:<18} {l['trim']:<14} {l['city']:<16} {price_str:<20} {l['source']}")

    # Price Report by Model
    by_model = defaultdict(list)
    for l in listings:
        if l["price_iqd"] and l["price_iqd"] > 0:
            by_model[l["model"]].append(l["price_iqd"])

    if by_model:
        print(f"\n{'=' * 80}")
        print(f"  MARKET PRICE REPORT (all prices in IQD  |  1 USD = {usd_to_iqd:,} IQD)")
        print(f"{'=' * 80}")
        print(f"  {'Model':<18} {'Count':<7} {'Min':<14} {'Max':<14} {'Avg':<14} {'Median':<14}")
        print(f"  {'-' * 76}")

        total_prices = []
        for mdl, prices in sorted(by_model.items()):
            prices.sort()
            avg = sum(prices) // len(prices)
            median = prices[len(prices) // 2]
            total_prices.extend(prices)
            print(f"  {mdl:<18} {len(prices):<7} {fmt_iqd(min(prices)):<14} {fmt_iqd(max(prices)):<14} {fmt_iqd(avg):<14} {fmt_iqd(median):<14}")

        if len(by_model) > 1 and total_prices:
            total_prices.sort()
            print(f"  {'-' * 76}")
            avg_all = sum(total_prices) // len(total_prices)
            med_all = total_prices[len(total_prices) // 2]
            print(f"  {'OVERALL':<18} {len(total_prices):<7} {fmt_iqd(min(total_prices)):<14} {fmt_iqd(max(total_prices)):<14} {fmt_iqd(avg_all):<14} {fmt_iqd(med_all):<14}")

    # Price by Year breakdown
    by_year = defaultdict(list)
    for l in listings:
        if l["price_iqd"] and l["price_iqd"] > 0:
            by_year[(l["model"], l["year"])].append(l["price_iqd"])

    if len(by_year) > 1:
        print(f"\n{'=' * 75}")
        print(f"  PRICE BY MODEL + YEAR")
        print(f"{'=' * 75}")
        print(f"  {'Model':<14} {'Year':<6} {'Count':<7} {'Min':<14} {'Max':<14} {'Avg':<14}")
        print(f"  {'-' * 70}")
        for (mdl, year), prices in sorted(by_year.items()):
            prices.sort()
            avg = sum(prices) // len(prices)
            print(f"  {mdl:<14} {year:<6} {len(prices):<7} {fmt_iqd(min(prices)):<14} {fmt_iqd(max(prices)):<14} {fmt_iqd(avg):<14}")

    # Mileage Report
    by_model_km = defaultdict(list)
    for l in listings:
        km = int(l["mileage_km"]) if l["mileage_km"].isdigit() else 0
        if km > 0:
            by_model_km[l["model"]].append(km)

    if by_model_km:
        print(f"\n{'=' * 70}")
        print(f"  MILEAGE REPORT")
        print(f"{'=' * 70}")
        print(f"  {'Model':<18} {'Count':<7} {'Min KM':<12} {'Max KM':<12} {'Avg KM':<12}")
        print(f"  {'-' * 60}")
        for mdl, kms in sorted(by_model_km.items()):
            avg_km = sum(kms) // len(kms)
            print(f"  {mdl:<18} {len(kms):<7} {min(kms):>9,}  {max(kms):>9,}  {avg_km:>9,}")

    # City Distribution
    by_city = defaultdict(int)
    for l in listings:
        if l["city"] and l["city"] != "N/A":
            by_city[l["city"]] += 1

    if by_city:
        print(f"\n{'=' * 45}")
        print(f"  LISTINGS BY CITY")
        print(f"{'=' * 45}")
        for city, count in sorted(by_city.items(), key=lambda x: -x[1]):
            bar = "#" * count
            print(f"  {city:<20} {count:>3}  {bar}")

    # Source Distribution
    by_source = defaultdict(int)
    for l in listings:
        by_source[l["source"]] += 1
    print(f"\n  Sources: ", end="")
    print(" | ".join(f"{src}: {cnt}" for src, cnt in sorted(by_source.items())))

    # ── NAI Purchase vs Market Comparison ────────────────────────
    print_purchase_comparison(listings, year_filter, selected_models)


def print_purchase_comparison(listings, year_filter, selected_models):
    """Compare NAI Odoo purchase prices against live market data."""
    # Only show purchases for models that were actually scraped
    selected_set = set(selected_models)
    haval_purchases = [p for p in PURCHASES if p["model"] in selected_set]
    if year_filter:
        haval_purchases = [p for p in haval_purchases if p["year"] == str(year_filter)]

    if not haval_purchases:
        return

    # Build market price lookup: model -> year -> list of IQD prices
    market = defaultdict(lambda: defaultdict(list))
    market_all = defaultdict(list)  # model -> all prices regardless of year
    for l in listings:
        if l.get("price_iqd") and l["price_iqd"] > 0:
            # Normalize model name: "HAVAL H6" -> "H6"
            mdl = l["model"].replace("HAVAL ", "")
            market[mdl][l["year"]].append(l["price_iqd"])
            market_all[mdl].append(l["price_iqd"])

    def stats(prices):
        if not prices:
            return None, None, None, None
        prices = sorted(prices)
        return min(prices), max(prices), sum(prices) // len(prices), prices[len(prices) // 2]

    # ── Summary: Your Avg Purchase vs Market Avg by Model ────────
    print(f"\n{'=' * 95}")
    print(f"  NAI PURCHASE vs MARKET COMPARISON")
    print(f"{'=' * 95}")
    print(f"  {'Model':<12} {'Year':<6} {'Your Purchases':<8} {'Your Avg':<14} {'Market Avg':<14} {'Market Min':<14} {'Market Max':<14} {'Verdict'}")
    print(f"  {'-' * 92}")

    # Group purchases by model + year
    purchase_groups = defaultdict(list)
    for p in haval_purchases:
        purchase_groups[(p["model"], p["year"])].append(p["price_iqd"])

    for (mdl, yr), prices in sorted(purchase_groups.items()):
        your_avg = sum(prices) // len(prices)
        mkt_prices = market.get(mdl, {}).get(yr, [])
        m_min, m_max, m_avg, m_med = stats(mkt_prices)

        # If no exact year match, try all years for this model
        if not mkt_prices:
            mkt_prices = market_all.get(mdl, [])
            m_min, m_max, m_avg, m_med = stats(mkt_prices)
            yr_label = f"{yr}*"  # asterisk = compared against all years
        else:
            yr_label = yr

        if m_avg:
            diff = your_avg - m_avg
            diff_pct = (diff / m_avg) * 100
            if diff_pct < -5:
                verdict = f"BELOW MKT ({diff_pct:+.0f}%)"
            elif diff_pct > 5:
                verdict = f"ABOVE MKT ({diff_pct:+.0f}%)"
            else:
                verdict = f"AT MARKET ({diff_pct:+.0f}%)"
        else:
            verdict = "No market data"

        print(f"  {mdl:<12} {yr_label:<6} {len(prices):<8} {fmt_iqd(your_avg):<14} "
              f"{fmt_iqd(m_avg) if m_avg else 'N/A':<14} "
              f"{fmt_iqd(m_min) if m_min else 'N/A':<14} "
              f"{fmt_iqd(m_max) if m_max else 'N/A':<14} {verdict}")

    # ── Detail: Each Purchase vs Market ──────────────────────────
    print(f"\n{'=' * 105}")
    print(f"  PURCHASE DETAIL vs MARKET")
    print(f"{'=' * 105}")
    print(f"  {'#':<4} {'Product':<18} {'Year':<6} {'KM':<10} {'Your Price':<14} {'Mkt Avg':<14} {'Diff':<14} {'Status'}")
    print(f"  {'-' * 100}")

    for i, p in enumerate(sorted(haval_purchases, key=lambda x: x["model"]), 1):
        mdl = p["model"]
        yr = p["year"]
        your_price = p["price_iqd"]

        # Try exact year match first, then all years
        mkt_prices = market.get(mdl, {}).get(yr, [])
        if not mkt_prices:
            mkt_prices = market_all.get(mdl, [])
        _, _, m_avg, _ = stats(mkt_prices)

        if m_avg:
            diff = your_price - m_avg
            diff_pct = (diff / m_avg) * 100
            if diff_pct < -10:
                status = "GOOD DEAL"
            elif diff_pct < -5:
                status = "Below Mkt"
            elif diff_pct > 10:
                status = "OVERPAID"
            elif diff_pct > 5:
                status = "Above Mkt"
            else:
                status = "Fair"
            diff_str = f"{diff/1_000_000:+.1f}M ({diff_pct:+.0f}%)"
        else:
            diff_str = "N/A"
            status = "No data"

        km_str = f"{p['km']:,}" if p['km'] > 0 else "New"
        print(f"  {i:<4} {p['product']:<18} {yr:<6} {km_str:<10} {fmt_iqd(your_price):<14} "
              f"{fmt_iqd(m_avg) if m_avg else 'N/A':<14} {diff_str:<14} {status}")

    # Note about year matching
    print(f"\n  * = compared against all years (no exact year match in market data)")
    print(f"  TANK 300, ORA, POER not shown (not scraped — different GWM brands)")


# ── Main ──────────────────────────────────────────────────────────
def main():
    selected_models, year_filter, usd_to_iqd = show_menu()

    all_listings = []

    print(f"\n{'-' * 55}")
    print(f"  Scraping IQCars + OpenSouq...")
    print(f"{'-' * 55}")

    for model in selected_models:
        # IQCars
        if "iqcars" in MODELS[model]:
            url = MODELS[model]["iqcars"]
            print(f"\n  IQCars  -> HAVAL {model}")
            results = scrape_iqcars(model, url, usd_to_iqd)
            if results:
                print(f"     Found {len(results)} listings")
                all_listings.extend(results)
            else:
                print(f"     No listings found")
            time.sleep(1)

        # OpenSouq
        if "opensooq" in MODELS[model]:
            url = MODELS[model]["opensooq"]
            print(f"\n  OpenSouq -> HAVAL {model}")
            results = scrape_opensooq(model, url, usd_to_iqd)
            if results:
                print(f"     Found {len(results)} listings")
                all_listings.extend(results)
            else:
                print(f"     No listings found")
            time.sleep(1)

    # Deduplicate
    seen = set()
    unique = []
    for l in all_listings:
        key = (l["model"], l["year"], l["mileage_km"], l["price_original"], l["source"])
        if key not in seen:
            seen.add(key)
            unique.append(l)

    # Year filter
    if year_filter:
        unique = [l for l in unique if l["year"] == str(year_filter)]

    # Filter out zero-price listings
    unique = [l for l in unique if l.get("price_iqd") and l["price_iqd"] > 0]

    # Flag price outliers (> 3x median for same model) — likely bad data
    by_model_prices = defaultdict(list)
    for l in unique:
        by_model_prices[l["model"]].append(l["price_iqd"])
    for mdl, prices in by_model_prices.items():
        if len(prices) < 3:
            continue
        prices_sorted = sorted(prices)
        median = prices_sorted[len(prices_sorted) // 2]
        threshold = median * 3
        for l in unique:
            if l["model"] == mdl and l["price_iqd"] > threshold:
                l["_outlier"] = True
    outliers = [l for l in unique if l.get("_outlier")]
    unique = [l for l in unique if not l.get("_outlier")]
    if outliers:
        print(f"\n  Excluded {len(outliers)} price outlier(s) (likely bad data)")
        for o in outliers:
            print(f"    - {o['model']} {o['year']} {o['city']}: {fmt_iqd(o['price_iqd'])} ({o['source']})")

    # Print report
    print_report(unique, year_filter, usd_to_iqd, selected_models)

    # Save CSV
    if unique:
        output_file = "haval_listings.csv"
        fieldnames = [
            "source", "model", "year", "mileage_km", "mileage_range",
            "trim", "city", "condition", "price_original",
            "currency_original", "price_iqd", "url", "scraped_at",
        ]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unique)
        print(f"\n  Saved -> {output_file}")

    # Run again?
    print()
    again = input("  Search again? (y/n): ").strip().lower()
    if again == "y":
        main()
    else:
        print("\n  Done!\n")


if __name__ == "__main__":
    main()
