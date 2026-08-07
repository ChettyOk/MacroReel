import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Recipe } from "../api";
import * as api from "../api";
import { RecipeGridSkeleton } from "../components/RecipeCardSkeleton";
import { RecipeThumb } from "../components/RecipeThumb";
import { toUserErrorMessage } from "../lib/userError";

export function CookbookPage() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setRecipes(await api.fetchRecipes());
    } catch (e) {
      setError(toUserErrorMessage(e, "Couldn’t load your cookbook. Please try again."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="page">
        <h1 className="page-title">Cookbook</h1>
        <RecipeGridSkeleton count={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" role="alert" style={{ color: "var(--danger-soft-text)" }}>
        {error}
      </div>
    );
  }

  if (recipes.length === 0) {
    return (
      <section className="card" style={{ textAlign: "center", padding: "2.5rem 1.25rem" }}>
        <p style={{ fontSize: "2.5rem", margin: "0 0 0.5rem" }}>📓</p>
        <h2 className="page-title" style={{ fontSize: "1.35rem" }}>Cookbook is empty</h2>
        <p className="page-sub">Save recipes from TikTok, Instagram, or YouTube to cook them later.</p>
        <div className="btn-row" style={{ justifyContent: "center" }}>
          <button type="button" className="btn btn--primary" onClick={() => navigate("/import")}>
            Import a video
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => navigate("/new")}>
            Add manually
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title" style={{ margin: 0 }}>Cookbook</h1>
        <p className="page-sub" style={{ marginBottom: 0 }}>
          {recipes.length} saved · no impact on today&apos;s log until you log a meal
        </p>
      </header>

      <div className="add-recipe-bar">
        <button type="button" className="btn btn--primary" onClick={() => navigate("/import")}>
          Import video
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => navigate("/new")}>
          Add manually
        </button>
      </div>

      <ul className="recipe-grid">
        {recipes.map((r) => (
          <li key={r.id}>
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
                    ? `${Math.round(r.nutrition.per_serving.calories)} kcal`
                    : "—"}
                </p>
                {r.nutrition?.per_serving?.protein_g != null && r.nutrition.per_serving.protein_g >= 15 ? (
                  <span className="recipe-card__badge">{Math.round(r.nutrition.per_serving.protein_g)}g protein</span>
                ) : null}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
