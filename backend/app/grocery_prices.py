"""Grocery price estimates with optional live/partner feed support.

Feed sources are opt-in:
- GROCERY_PRICE_FEED_FILE=/data/grocery_prices.json
- GROCERY_PRICE_FEED_URL=https://partner.example.com/prices.json

Expected feed shape:
{
  "currency": "CAD",
  "items": [
    {
      "name": "chicken breast",
      "aliases": ["boneless chicken breast"],
      "store": "Walmart",
      "region": "Canada",
      "price": 13.49,
      "unit": "kg"
    },
    {
      "name": "rice",
      "store": "Real Canadian Superstore",
      "price": 6.99,
      "package_size_g": 2000
    }
  ]
}
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app import config
from app.nutrition_ingredient import resolve_ingredient_line
from app.schemas import IngredientPriceEstimate, RecipePriceEstimate, StorePriceEstimate

_CANADIAN_POSTAL_RE = re.compile(r"\b[abceghj-nprstvxy]\d[abceghj-nprstv-z][ -]?\d[abceghj-nprstv-z]\d\b", re.I)
_US_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")

_STORE_REGIONS = {
    "Walmart": "US/Canada",
    "Costco": "US/Canada",
    "No Frills": "Canada",
    "Loblaws": "Canada",
    "Real Canadian Superstore": "Canada",
    "Metro": "Canada",
    "Safeway": "US/Canada",
    "Kroger": "US",
    "Target": "US",
    "Trader Joe's": "US",
    "Whole Foods": "US/Canada",
}

_COUNTRY_STORE_AVAILABILITY = {
    "Canada": [
        "Walmart",
        "Costco",
        "No Frills",
        "Loblaws",
        "Real Canadian Superstore",
        "Metro",
        "Safeway",
        "Whole Foods",
    ],
    "US": [
        "Walmart",
        "Costco",
        "Kroger",
        "Target",
        "Trader Joe's",
        "Safeway",
        "Whole Foods",
    ],
}

_CANADA_HINTS = {
    "canada",
    "canadian",
    "ontario",
    "toronto",
    "ottawa",
    "mississauga",
    "brampton",
    "scarborough",
    "quebec",
    "montreal",
    "vancouver",
    "burnaby",
    "surrey",
    "victoria",
    "calgary",
    "edmonton",
    "alberta",
    "manitoba",
    "winnipeg",
    "saskatchewan",
    "regina",
    "saskatoon",
    "halifax",
    "nova",
    "brunswick",
    "newfoundland",
    "labrador",
    "yukon",
    "nunavut",
}
_CANADA_ABBRS = {"on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pei", "yt", "nt", "nu"}
_US_HINTS = {
    "usa",
    "america",
    "american",
    "states",
    "york",
    "los",
    "angeles",
    "chicago",
    "houston",
    "phoenix",
    "philadelphia",
    "dallas",
    "austin",
    "miami",
    "seattle",
    "boston",
    "denver",
    "atlanta",
    "california",
    "texas",
    "florida",
    "washington",
    "oregon",
    "illinois",
    "georgia",
    "colorado",
}
_US_ABBRS = {"ny", "tx", "fl", "wa", "or", "il", "ga", "co", "az", "pa", "ma", "mi", "oh", "nc", "sc", "tn", "va"}

# Approximate price per kg/ml-equivalent for common recipe ingredients.
_BASE_PRICE_PER_KG = {
    "chicken": 11.0,
    "chicken breast": 13.0,
    "beef": 15.0,
    "ground beef": 12.5,
    "salmon": 24.0,
    "shrimp": 22.0,
    "egg": 6.0,
    "milk": 2.0,
    "cream": 7.0,
    "cheese": 15.0,
    "butter": 11.0,
    "greek yogurt": 8.0,
    "rice": 4.0,
    "pasta": 4.5,
    "flour": 2.2,
    "sugar": 2.5,
    "oats": 4.0,
    "potato": 3.0,
    "sweet potato": 4.0,
    "tomato": 5.0,
    "onion": 2.5,
    "garlic": 8.0,
    "pepper": 6.0,
    "broccoli": 5.5,
    "spinach": 10.0,
    "lettuce": 5.0,
    "avocado": 9.0,
    "olive oil": 12.0,
    "vegetable oil": 5.5,
    "soy sauce": 4.0,
    "tortilla": 6.0,
    "bread": 5.0,
}

_STORE_MULTIPLIER = {
    "Walmart": 0.92,
    "Costco": 0.88,
    "No Frills": 0.9,
    "Loblaws": 1.04,
    "Real Canadian Superstore": 0.98,
    "Metro": 1.08,
    "Safeway": 1.06,
    "Kroger": 0.96,
    "Target": 1.0,
    "Trader Joe's": 1.02,
    "Whole Foods": 1.28,
}

_FEED_CACHE: tuple[float, dict[str, Any] | None] = (0.0, None)
_SPOONACULAR_CACHE: dict[str, list[StorePriceEstimate]] = {}
_SPOONACULAR_SEARCH_URL = "https://api.spoonacular.com/food/ingredients/search"
_SPOONACULAR_INFO_URL = "https://api.spoonacular.com/food/ingredients/{id}/information"


def _feed_configured() -> bool:
    return bool(config.GROCERY_PRICE_FEED_FILE or config.GROCERY_PRICE_FEED_URL)


def _http_get_json(url: str, timeout: int = 8) -> Any | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, TimeoutError):
        return None
    return data


def _load_feed() -> dict[str, Any] | None:
    global _FEED_CACHE

    now = time.time()
    cached_at, cached = _FEED_CACHE
    if cached is not None and now - cached_at < config.GROCERY_PRICE_CACHE_TTL_SEC:
        return cached

    data: dict[str, Any] | None = None
    if config.GROCERY_PRICE_FEED_FILE:
        path = Path(config.GROCERY_PRICE_FEED_FILE).expanduser()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None

    if data is None and config.GROCERY_PRICE_FEED_URL:
        data = _http_get_json(config.GROCERY_PRICE_FEED_URL)

    if isinstance(data, list):
        data = {"items": data}
    if not isinstance(data, dict):
        data = None

    _FEED_CACHE = (now, data)
    return data


def _tokens(value: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if len(part) > 2}


def _short_tokens(value: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if part}


def _normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    low = country.strip().lower()
    if low in {"ca", "can", "canada"}:
        return "Canada"
    if low in {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}:
        return "US"
    return None


def _location_info(location: str | None) -> dict[str, Any]:
    label = " ".join((location or "").split())
    short = _short_tokens(label)
    long = _tokens(label)
    country = None
    if _CANADIAN_POSTAL_RE.search(label) or short & _CANADA_ABBRS or long & _CANADA_HINTS:
        country = "Canada"
    elif _US_ZIP_RE.search(label) or short & _US_ABBRS or long & _US_HINTS:
        country = "US"
    return {
        "label": label or None,
        "tokens": short,
        "country": country,
    }


def possible_stores_for_location(location: str | None = None) -> list[str]:
    info = _location_info(location)
    country = info["country"]
    if country in _COUNTRY_STORE_AVAILABILITY:
        return _COUNTRY_STORE_AVAILABILITY[country]
    return list(_STORE_MULTIPLIER)


def _store_available_for_location(store: str, location: dict[str, Any]) -> bool:
    country = location["country"]
    if country is None:
        return True
    return store in _COUNTRY_STORE_AVAILABILITY.get(country, list(_STORE_MULTIPLIER))


def _region_matches_location(region: str, location: dict[str, Any]) -> bool:
    if not location["label"]:
        return True
    country = _normalize_country(region)
    if country is not None:
        return location["country"] is None or country == location["country"]
    region_tokens = _short_tokens(region)
    if location["country"] == "Canada" and ({"canada"} | _CANADA_HINTS | _CANADA_ABBRS) & region_tokens:
        return True
    if location["country"] == "US" and ({"us", "usa", "states"} | _US_HINTS | _US_ABBRS) & region_tokens:
        return True
    return not region_tokens or bool(region_tokens & location["tokens"])


def _feed_item_location_matches(item: dict[str, Any], location: dict[str, Any]) -> bool:
    if not location["label"]:
        return True
    parts = [
        item.get("region"),
        item.get("country"),
        item.get("province"),
        item.get("state"),
        item.get("city"),
        item.get("postal_prefix"),
        item.get("postal_code"),
    ]
    text = " ".join(str(part) for part in parts if part)
    if not text:
        return True
    country = _normalize_country(str(item.get("country") or item.get("region") or ""))
    if country is not None and location["country"] is not None:
        return country == location["country"]
    text_tokens = _short_tokens(text)
    if location["country"] == "Canada" and ({"canada"} | _CANADA_HINTS | _CANADA_ABBRS) & text_tokens:
        return True
    if location["country"] == "US" and ({"us", "usa", "states"} | _US_HINTS | _US_ABBRS) & text_tokens:
        return True
    return bool(text_tokens & location["tokens"])


def _feed_item_matches(item: dict[str, Any], search_name: str) -> bool:
    names = [str(item.get("name") or item.get("query") or "")]
    aliases = item.get("aliases") or []
    if isinstance(aliases, list):
        names.extend(str(alias) for alias in aliases)

    search_tokens = _tokens(search_name)
    if not search_tokens:
        return False
    for name in names:
        low = name.lower()
        if low and (low in search_name.lower() or search_name.lower() in low):
            return True
        if search_tokens & _tokens(name):
            return True
    return False


def _feed_unit_price_per_kg(item: dict[str, Any]) -> float | None:
    direct = item.get("price_per_kg")
    if direct is not None:
        try:
            return float(direct)
        except (TypeError, ValueError):
            return None

    price = item.get("price")
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None

    unit = str(item.get("unit") or "").strip().lower()
    if unit in ("kg", "kilogram", "kilograms"):
        return price_f
    if unit in ("g", "gram", "grams"):
        return price_f * 1000
    if unit in ("lb", "lbs", "pound", "pounds"):
        return price_f / 0.453592

    package_size_g = item.get("package_size_g") or item.get("size_g")
    try:
        grams = float(package_size_g)
    except (TypeError, ValueError):
        return None
    if grams <= 0:
        return None
    return price_f / (grams / 1000)


def _match_price_key(name: str) -> str | None:
    low = name.lower()
    matches = [key for key in _BASE_PRICE_PER_KG if key in low]
    if matches:
        return max(matches, key=len)
    words = [w for w in _tokens(low) if len(w) > 2]
    for word in words:
        if word in _BASE_PRICE_PER_KG:
            return word
    return None


def _stores_from_feed(search_name: str, grams: float, location: dict[str, Any]) -> list[StorePriceEstimate]:
    feed = _load_feed()
    raw_items = feed.get("items") if feed else None
    if not isinstance(raw_items, list):
        return []

    default_currency = str(feed.get("currency") or "USD/CAD")
    stores: list[StorePriceEstimate] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        if not isinstance(raw, dict) or not _feed_item_matches(raw, search_name) or not _feed_item_location_matches(raw, location):
            continue
        per_kg = _feed_unit_price_per_kg(raw)
        if per_kg is None:
            continue
        store = str(raw.get("store") or "Grocery feed")
        region = str(raw.get("region") or _STORE_REGIONS.get(store, "configured feed"))
        if not _store_available_for_location(store, location) or not _region_matches_location(region, location):
            continue
        key = (store, region)
        if key in seen:
            continue
        seen.add(key)
        stores.append(
            StorePriceEstimate(
                store=store,
                region=region,
                price=round(per_kg * grams / 1000, 2),
                currency=str(raw.get("currency") or default_currency),
            )
        )
    return stores


def _spoonacular_cost_to_price(cost: dict[str, Any]) -> tuple[float, str] | None:
    try:
        value = float(cost.get("value"))
    except (TypeError, ValueError):
        return None
    unit = str(cost.get("unit") or "").lower()
    if "cent" in unit:
        return round(value / 100, 2), "USD"
    return round(value, 2), "USD"


def _stores_from_spoonacular(search_name: str, grams: float, location: dict[str, Any]) -> list[StorePriceEstimate]:
    if not config.SPOONACULAR_API_KEY:
        return []
    if location["country"] == "Canada":
        return []
    cache_key = f"{search_name.lower()}|{round(grams, 1)}"
    if cache_key in _SPOONACULAR_CACHE:
        return _SPOONACULAR_CACHE[cache_key]

    search_params = urllib.parse.urlencode(
        {
            "query": search_name,
            "number": 1,
            "apiKey": config.SPOONACULAR_API_KEY,
        }
    )
    search = _http_get_json(f"{_SPOONACULAR_SEARCH_URL}?{search_params}")
    results = search.get("results") if isinstance(search, dict) else None
    if not isinstance(results, list) or not results:
        _SPOONACULAR_CACHE[cache_key] = []
        return []

    ingredient_id = results[0].get("id") if isinstance(results[0], dict) else None
    if ingredient_id is None:
        _SPOONACULAR_CACHE[cache_key] = []
        return []

    info_params = urllib.parse.urlencode(
        {
            "amount": round(grams, 2),
            "unit": "gram",
            "apiKey": config.SPOONACULAR_API_KEY,
        }
    )
    info = _http_get_json(f"{_SPOONACULAR_INFO_URL.format(id=ingredient_id)}?{info_params}")
    cost = info.get("estimatedCost") if isinstance(info, dict) else None
    parsed = _spoonacular_cost_to_price(cost) if isinstance(cost, dict) else None
    if parsed is None:
        _SPOONACULAR_CACHE[cache_key] = []
        return []

    price, currency = parsed
    stores = [
        StorePriceEstimate(
            store="Spoonacular estimate",
            region="US average",
            price=price,
            currency=currency,
        )
    ]
    _SPOONACULAR_CACHE[cache_key] = stores
    return stores


def _stores_from_fallback(search_name: str, grams: float, location: dict[str, Any]) -> list[StorePriceEstimate]:
    price_key = _match_price_key(search_name)
    if price_key is None:
        return []
    base = _BASE_PRICE_PER_KG[price_key]
    currency = "CAD" if location["country"] == "Canada" else "USD" if location["country"] == "US" else "USD/CAD"
    return [
        StorePriceEstimate(
            store=store,
            region=_STORE_REGIONS[store],
            price=round(base * mult * grams / 1000, 2),
            currency=currency,
        )
        for store, mult in _STORE_MULTIPLIER.items()
        if _store_available_for_location(store, location)
    ]


def price_item(line: str, location: dict[str, Any] | None = None) -> IngredientPriceEstimate:
    location = location or _location_info(None)
    resolved = resolve_ingredient_line(line)
    if resolved is None:
        return IngredientPriceEstimate(
            ingredient=line,
            normalized_name=line.strip().lower(),
            notes=["Add a quantity or weight for a better grocery estimate."],
        )

    estimate = IngredientPriceEstimate(
        ingredient=line,
        normalized_name=resolved.search_name,
        estimated_weight_g=round(resolved.grams, 1),
        quantity_label=f"{round(resolved.grams)} g estimated",
    )

    stores = _stores_from_feed(resolved.search_name, resolved.grams, location)
    source_note = "Live/partner grocery feed matched this ingredient." if stores else ""
    if not stores:
        if location["label"]:
            stores = _stores_from_fallback(resolved.search_name, resolved.grams, location)
            source_note = "Using stores available for your entered location; configure a grocery feed for live local prices." if stores else ""
        else:
            stores = _stores_from_spoonacular(resolved.search_name, resolved.grams, location)
            source_note = "Spoonacular estimated ingredient cost matched this item." if stores else ""
    if not stores:
        stores = _stores_from_fallback(resolved.search_name, resolved.grams, location)
        source_note = "Using built-in placeholder pricing; configure a grocery feed for live store data." if stores else ""

    if not stores:
        estimate.notes.append("No grocery price match yet for this ingredient.")
        return estimate

    estimate.stores = stores
    best = min(stores, key=lambda s: s.price)
    estimate.best_store = best.store
    estimate.best_price = best.price
    if source_note:
        estimate.notes.append(source_note)
    if resolved.approx:
        estimate.notes.append("Volume/count converted to approximate grams.")
    return estimate


def estimate_recipe_price(ingredients: list[str], location: str | None = None) -> RecipePriceEstimate:
    location_info = _location_info(location)
    items = [price_item(line, location_info) for line in ingredients[:50]]
    priced = [item.best_price for item in items if item.best_price is not None]
    total = round(sum(priced), 2) if priced else None
    currencies = sorted({store.currency for item in items for store in item.stores})
    currency = currencies[0] if len(currencies) == 1 else "USD/CAD"
    feed_active = _feed_configured() and _load_feed() is not None
    spoonacular_active = bool(config.SPOONACULAR_API_KEY)
    notes = [
        "Live/partner grocery feed enabled; unmatched ingredients fall back to placeholders."
        if feed_active
        else (
            f"Using stores likely available near {location_info['label']}; add a grocery feed for live shelf prices."
            if location_info["label"]
            else "Using built-in placeholder pricing. Configure SPOONACULAR_API_KEY, GROCERY_PRICE_FEED_FILE, or GROCERY_PRICE_FEED_URL for better prices."
            if not spoonacular_active
            else "Spoonacular pricing enabled; unmatched ingredients fall back to built-in placeholders."
        ),
        "Estimates use edible ingredient quantities, not package sizes, taxes, delivery fees, or sale pricing.",
    ]
    return RecipePriceEstimate(
        items=items,
        total_best_price=total,
        currency=currency,
        notes=notes,
        location_label=location_info["label"],
        possible_stores=possible_stores_for_location(location_info["label"]),
    )
