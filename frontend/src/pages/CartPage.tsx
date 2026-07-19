import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { IngredientPriceEstimate, RecipePriceEstimate } from "../api";
import * as api from "../api";
import { useShoppingCart } from "../context/ShoppingCartContext";
import { formatMergedIngredient } from "../lib/shoppingCart";

const CART_LOCATION_KEY = "macroreel-shopping-location";

type CartStoreTotal = {
  store: string;
  currency: string;
  total: number;
  matched: number;
};

function formatMoney(price: number, currency: string): string {
  return `${currency} ${price.toFixed(2)}`;
}

function cartStoreTotals(pricing: RecipePriceEstimate | null): CartStoreTotal[] {
  if (!pricing) return [];
  const totals = new Map<string, CartStoreTotal>();
  for (const item of pricing.items) {
    for (const store of item.stores) {
      const key = `${store.store}|${store.currency}`;
      const current = totals.get(key) ?? {
        store: store.store,
        currency: store.currency,
        total: 0,
        matched: 0,
      };
      current.total += store.price;
      current.matched += 1;
      totals.set(key, current);
    }
  }
  return Array.from(totals.values())
    .map((store) => ({ ...store, total: Math.round(store.total * 100) / 100 }))
    .sort((a, b) => b.matched - a.matched || a.total - b.total || a.store.localeCompare(b.store));
}

function loadCartLocation(): string {
  try {
    return localStorage.getItem(CART_LOCATION_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveCartLocation(location: string): void {
  try {
    if (location) localStorage.setItem(CART_LOCATION_KEY, location);
    else localStorage.removeItem(CART_LOCATION_KEY);
  } catch {
    /* ignore unavailable storage */
  }
}

export function CartPage() {
  const { entries, merged, uncheckedCount, removeEntry, clearAll, toggleChecked, isChecked } = useShoppingCart();
  const [pricing, setPricing] = useState<RecipePriceEstimate | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceErr, setPriceErr] = useState<string | null>(null);
  const [locationInput, setLocationInput] = useState(loadCartLocation);
  const [priceLocation, setPriceLocation] = useState(loadCartLocation);

  const checkedCount = merged.length - uncheckedCount;
  const cartIngredientLines = useMemo(() => merged.map(formatMergedIngredient), [merged]);
  const priceLookup = useMemo(() => {
    const map = new Map<string, IngredientPriceEstimate>();
    for (const item of pricing?.items ?? []) map.set(item.ingredient, item);
    return map;
  }, [pricing]);
  const storeTotals = useMemo(() => cartStoreTotals(pricing), [pricing]);
  const pricedItemCount = pricing?.items.filter((item) => item.stores.length > 0).length ?? 0;

  useEffect(() => {
    let cancelled = false;
    if (!cartIngredientLines.length) {
      setPricing(null);
      setPriceErr(null);
      setPriceLoading(false);
      return;
    }
    setPriceLoading(true);
    setPriceErr(null);
    void api
      .getGroceryPrices(cartIngredientLines, priceLocation)
      .then((next) => {
        if (!cancelled) setPricing(next);
      })
      .catch((e) => {
        if (!cancelled) setPriceErr(e instanceof Error ? e.message : "Could not load grocery prices.");
      })
      .finally(() => {
        if (!cancelled) setPriceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cartIngredientLines, priceLocation]);

  function handleLocationSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const cleaned = locationInput.trim().split(/\s+/).filter(Boolean).join(" ");
    setLocationInput(cleaned);
    setPriceLocation(cleaned);
    saveCartLocation(cleaned);
  }

  return (
    <div className="page">
      <header style={{ marginBottom: "1rem" }}>
        <h1 className="page-title">Shopping list</h1>
        <p className="page-sub" style={{ margin: 0 }}>
          Ingredients gathered from recipes — separate from your cookbook.
        </p>
      </header>

      {entries.length === 0 ? (
        <section className="card" style={{ textAlign: "center", padding: "2rem 1rem" }}>
          <p style={{ margin: "0 0 1rem", color: "var(--text-muted)" }}>
            Add recipes from the cookbook to build your shopping list. Similar ingredients are combined automatically.
          </p>
          <Link to="/cookbook" className="btn btn--primary" style={{ textDecoration: "none" }}>
            Browse cookbook
          </Link>
        </section>
      ) : (
        <>
          <section className="card cart-recipes">
            <div className="cart-section-head">
              <strong>Recipes in list</strong>
              <span className="cart-section-head__meta">{entries.length} added</span>
            </div>
            <ul className="cart-recipes__list">
              {entries.map((entry) => (
                <li key={entry.entryId} className="cart-recipes__item">
                  <Link to={`/recipe/${entry.recipeId}`} className="cart-recipes__title">
                    {entry.title}
                  </Link>
                  <span className="cart-recipes__meta">{entry.lines.length} items</span>
                  <button
                    type="button"
                    className="btn btn--ghost cart-recipes__remove"
                    aria-label={`Remove ${entry.title} from shopping list`}
                    onClick={() => removeEntry(entry.entryId)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="card cart-price-card">
            <div className="cart-section-head">
              <strong>Price estimate</strong>
              <span className="cart-section-head__meta">
                {priceLoading ? "Checking stores…" : pricedItemCount ? `${pricedItemCount}/${merged.length} priced` : "Estimate"}
              </span>
            </div>
            <form className="cart-location-form" onSubmit={handleLocationSubmit}>
              <label className="field">
                <span className="field__label">Shopping location</span>
                <input
                  className="input"
                  type="text"
                  value={locationInput}
                  maxLength={120}
                  placeholder="City, province/state, or postal code"
                  onChange={(e) => setLocationInput(e.target.value)}
                />
              </label>
              <button type="submit" className="btn btn--secondary">
                Use location
              </button>
            </form>
            {pricing?.location_label ? (
              <p className="cart-location-note">Using stores likely available near {pricing.location_label}.</p>
            ) : (
              <p className="cart-location-note">Add a location to narrow store options for your area.</p>
            )}
            {priceErr ? (
              <div className="alert alert--error" role="alert">{priceErr}</div>
            ) : (
              <>
                <div className="cart-price-card__total">
                  <span>Best available total</span>
                  <strong>
                    {pricing?.total_best_price != null
                      ? formatMoney(pricing.total_best_price, pricing.currency)
                      : priceLoading
                        ? "Loading…"
                        : "Add quantities for prices"}
                  </strong>
                </div>
                {storeTotals.length ? (
                  <div className="cart-store-totals" aria-label="Store price comparisons">
                    {storeTotals.slice(0, 6).map((store) => (
                      <div key={`${store.store}-${store.currency}`} className="cart-store-total">
                        <span className="cart-store-total__name">{store.store}</span>
                        <strong>{formatMoney(store.total, store.currency)}</strong>
                        <span>{store.matched}/{pricedItemCount} items</span>
                      </div>
                    ))}
                  </div>
                ) : null}
                {pricing?.possible_stores.length ? (
                  <div className="cart-possible-stores" aria-label="Possible stores">
                    {pricing.possible_stores.map((store) => (
                      <span key={store} className="cart-possible-store">{store}</span>
                    ))}
                  </div>
                ) : null}
                {pricing?.notes[0] ? <p className="cart-price-card__note">{pricing.notes[0]}</p> : null}
              </>
            )}
          </section>

          <section className="card cart-checklist">
            <div className="cart-section-head">
              <strong>Ingredients</strong>
              <span className="cart-section-head__meta">
                {checkedCount}/{merged.length} checked
              </span>
            </div>
            {merged.length === 0 ? (
              <p className="page-sub" style={{ margin: 0 }}>No ingredients in these recipes.</p>
            ) : (
              <ul className="cart-checklist__list">
                {merged.map((item) => {
                  const checked = isChecked(item.mergeKey);
                  const line = formatMergedIngredient(item);
                  const price = priceLookup.get(line);
                  const bestStore = price?.stores.find((store) => store.store === price.best_store && store.price === price.best_price);
                  return (
                    <li key={item.mergeKey}>
                      <label className={`cart-checklist__row ${checked ? "cart-checklist__row--done" : ""}`}>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleChecked(item.mergeKey)}
                        />
                        <span className="cart-checklist__body">
                          <span className="cart-checklist__text">{line}</span>
                          {price?.best_price != null && price.best_store ? (
                            <span className="cart-price-line">
                              Best: {price.best_store} {formatMoney(price.best_price, bestStore?.currency ?? pricing?.currency ?? "USD")}
                            </span>
                          ) : priceLoading ? (
                            <span className="cart-price-line">Checking store prices…</span>
                          ) : null}
                          {price?.stores.length ? (
                            <span className="cart-store-pills">
                              {price.stores.slice(0, 5).map((store) => (
                                <span key={`${store.store}-${store.currency}`} className="cart-store-pill">
                                  {store.store}: {formatMoney(store.price, store.currency)}
                                </span>
                              ))}
                            </span>
                          ) : null}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {entries.length > 0 ? (
            <button type="button" className="btn btn--secondary btn--block" onClick={clearAll}>
              Clear shopping list
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
