import json

import app.config as config
import app.grocery_prices as grocery_prices
from app.schemas import Nutrition, NutritionReport
from app.upgrades import build_recipe_upgrades, estimate_recipe_price, repair_recipe


def test_price_estimate_uses_store_catalog():
    pricing = estimate_recipe_price(["200 g chicken breast", "100 g rice"])

    assert pricing.total_best_price is not None
    assert pricing.total_best_price > 0
    stores = {store.store for store in pricing.items[0].stores}
    assert pricing.items[0].best_store in stores
    assert len(stores) >= 6
    assert {"Walmart", "Costco", "No Frills", "Real Canadian Superstore"} <= stores


def test_price_estimate_uses_canadian_location_stores():
    pricing = estimate_recipe_price(["200 g chicken breast"], location="Toronto, ON")

    stores = {store.store for store in pricing.items[0].stores}
    assert pricing.location_label == "Toronto, ON"
    assert {"No Frills", "Loblaws", "Real Canadian Superstore"} <= stores
    assert "Kroger" not in stores
    assert "Target" not in stores
    assert pricing.possible_stores
    assert pricing.currency == "CAD"


def test_price_estimate_uses_us_location_stores():
    pricing = estimate_recipe_price(["200 g chicken breast"], location="Austin, TX 78701")

    stores = {store.store for store in pricing.items[0].stores}
    assert {"Kroger", "Target", "Trader Joe's"} <= stores
    assert "No Frills" not in stores
    assert "Real Canadian Superstore" not in stores
    assert pricing.currency == "USD"


def test_price_estimate_prefers_configured_feed(tmp_path, monkeypatch):
    feed = {
        "currency": "CAD",
        "items": [
            {
                "name": "chicken breast",
                "aliases": ["boneless chicken breast"],
                "store": "Real Canadian Superstore",
                "region": "Canada",
                "price": 10.0,
                "unit": "kg",
            }
        ],
    }
    path = tmp_path / "grocery_prices.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    monkeypatch.setattr(config, "GROCERY_PRICE_FEED_FILE", str(path))
    monkeypatch.setattr(config, "GROCERY_PRICE_FEED_URL", "")
    monkeypatch.setattr(grocery_prices, "_FEED_CACHE", (0.0, None))

    pricing = estimate_recipe_price(["200 g chicken breast"])

    assert pricing.items[0].best_store == "Real Canadian Superstore"
    assert pricing.items[0].best_price == 2.0
    assert pricing.items[0].stores[0].currency == "CAD"
    assert "Live/partner" in pricing.notes[0]


def test_price_estimate_uses_spoonacular_when_configured(monkeypatch):
    monkeypatch.setattr(config, "GROCERY_PRICE_FEED_FILE", "")
    monkeypatch.setattr(config, "GROCERY_PRICE_FEED_URL", "")
    monkeypatch.setattr(config, "SPOONACULAR_API_KEY", "test-spoon-key")
    monkeypatch.setattr(grocery_prices, "_FEED_CACHE", (0.0, None))
    monkeypatch.setattr(grocery_prices, "_SPOONACULAR_CACHE", {})

    def fake_get_json(url: str, timeout: int = 8):  # noqa: ARG001
        if "/food/ingredients/search" in url:
            return {"results": [{"id": 123, "name": "chicken breast"}]}
        if "/food/ingredients/123/information" in url:
            return {"estimatedCost": {"value": 250.0, "unit": "US Cents"}}
        return None

    monkeypatch.setattr(grocery_prices, "_http_get_json", fake_get_json)

    pricing = estimate_recipe_price(["200 g chicken breast"])

    assert pricing.items[0].best_store == "Spoonacular estimate"
    assert pricing.items[0].best_price == 2.5
    assert pricing.items[0].stores[0].currency == "USD"
    assert "Spoonacular" in pricing.notes[0]


def test_repair_recipe_flags_missing_temperature_time_and_quantities():
    repairs = repair_recipe(
        ["chicken breast", "salt"],
        ["Bake until cooked through."],
        servings=None,
        nutrition=None,
    )

    fields = {r.field for r in repairs}
    assert "servings" in fields
    assert "temperature" in fields
    assert "cook_time" in fields
    assert "ingredient_quantities" in fields
    assert "nutrition" in fields


def test_upgrade_response_includes_low_calorie_and_narration():
    upgrades = build_recipe_upgrades(
        title="Creamy chicken pasta",
        ingredients=["200 g chicken breast", "2 tbsp butter", "1 cup heavy cream", "100 g pasta"],
        steps=["Cook pasta.", "Simmer chicken in cream sauce."],
        servings=2,
        nutrition=NutritionReport(per_serving=Nutrition(calories=720)),
        profile=None,
    )

    assert upgrades.pricing.total_best_price is not None
    assert upgrades.low_calorie_options
    assert upgrades.cook_narration[0] == "Starting Creamy chicken pasta."
    assert "Step 1." in upgrades.cook_narration[1]
