import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Recipe } from "../api";
import * as api from "../api";
import { FavoriteButton } from "../components/FavoriteButton";
import { RecipeGridSkeleton } from "../components/RecipeCardSkeleton";
import { RecipeThumb } from "../components/RecipeThumb";
import { useFavorites } from "../context/FavoritesContext";
import { toUserErrorMessage } from "../lib/userError";

const SORTS = [
  { id: "recent", label: "Recent" },
  { id: "calories", label: "Calories ↑" },
  { id: "protein", label: "Protein ↓" },
  { id: "title", label: "A–Z" },
] as const;

const FILTERS = [
  { id: "all", label: "All" },
  { id: "favourites", label: "♥ Favourites" },
  { id: "high-protein", label: "High protein" },
  { id: "low-carb", label: "Low carb" },
  { id: "under500", label: "<500 cal" },
  { id: "quick", label: "Under 30 min" },
] as const;

function match(r: Recipe, id: string, favoriteIds: Set<number>): boolean {
  if (id === "all") return true;
  if (id === "favourites") return favoriteIds.has(r.id);
  const cal = r.nutrition?.per_serving?.calories;
  const prot = r.nutrition?.per_serving?.protein_g;
  const flags = r.dietary_flags ?? [];
  const mins = (r.prep_time_min ?? 0) + (r.cook_time_min ?? 0);
  if (id === "high-protein") return (prot != null && prot >= 25) || flags.includes("high-protein");
  if (id === "low-carb") return flags.includes("low-carb") || flags.includes("keto");
  if (id === "under500") return cal != null && cal < 500;
  if (id === "quick") return mins > 0 && mins <= 30;
  return true;
}

export function DiscoverPage() {
  const { favoriteIds } = useFavorites();
  const favoriteSet = useMemo(() => new Set(favoriteIds), [favoriteIds]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<(typeof SORTS)[number]["id"]>("recent");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecipes(await api.fetchRecipes());
    } catch (e) {
      setRecipes([]);
      setError(toUserErrorMessage(e, "Couldn’t load recipes. Please try again."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = recipes
    .filter((r) => {
      if (!match(r, filter, favoriteSet)) return false;
      if (!q.trim()) return true;
      const ql = q.toLowerCase();
      return (
        r.title.toLowerCase().includes(ql) ||
        r.ingredients.some((i) => i.toLowerCase().includes(ql))
      );
    })
    .sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      if (sort === "protein") {
        return (b.nutrition?.per_serving?.protein_g ?? -1) - (a.nutrition?.per_serving?.protein_g ?? -1);
      }
      if (sort === "calories") {
        return (a.nutrition?.per_serving?.calories ?? 99999) - (b.nutrition?.per_serving?.calories ?? 99999);
      }
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });

  return (
    <div className="page">
      <h1 className="page-title">Discover</h1>
      <p className="page-sub">Your saved recipes — filter by what fits today.</p>

      {error ? (
        <div className="alert alert--error" role="alert" style={{ marginBottom: "0.85rem" }}>
          {error}
          <button type="button" className="btn btn--secondary" style={{ marginTop: "0.65rem" }} onClick={() => void load()}>
            Try again
          </button>
        </div>
      ) : null}

      <input
        className="input"
        type="search"
        placeholder="Search title or ingredients…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: "0.85rem" }}
      />

      <section className="discover-controls card">
        <div className="discover-controls__group">
          <span className="discover-controls__label">Sort by</span>
          <div className="chip-scroll" role="group" aria-label="Sort recipes">
            {SORTS.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`chip ${sort === s.id ? "chip--on" : ""}`}
                onClick={() => setSort(s.id)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="discover-controls__group">
          <span className="discover-controls__label">Filter</span>
          <div className="chip-grid" role="group" aria-label="Filter recipes">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`chip ${f.id === "favourites" ? "chip--fav" : ""} ${filter === f.id ? "chip--on" : ""}`}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {loading ? (
        <RecipeGridSkeleton count={6} />
      ) : shown.length === 0 ? (
        <p className="card" style={{ color: "var(--text-muted)", textAlign: "center" }}>
          {filter === "favourites"
            ? "No favourites yet — tap ♡ on a recipe to save it here."
            : "No recipes match. Import a TikTok or YouTube video to build your library."}
        </p>
      ) : (
        <ul className="recipe-grid">
          {shown.map((r) => (
            <li key={r.id} className="recipe-card-wrap">
              <Link to={`/recipe/${r.id}`} className="recipe-card">
                <RecipeThumb
                  recipeId={r.id}
                  title={r.title}
                  thumbnailUrl={r.thumbnail_url}
                  sourceUrl={r.source_url}
                  sourcePlatform={r.source_platform}
                  calories={r.nutrition?.per_serving?.calories}
                  proteinG={r.nutrition?.per_serving?.protein_g}
                />
                <div className="recipe-card__body">
                  <p className="recipe-card__title">{r.title}</p>
                  <p className="recipe-card__meta">
                    {r.nutrition?.per_serving?.calories != null
                      ? `${Math.round(r.nutrition.per_serving.calories)} kcal/serv`
                      : "—"}
                  </p>
                </div>
              </Link>
              <FavoriteButton recipeId={r.id} className="recipe-card__fav" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
