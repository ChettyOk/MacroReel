import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { ExtractFromVideoResult, NutritionReport, RecipeInsights } from "../api";
import * as api from "../api";
import { DIETARY_FLAGS } from "../api";
import { FitDayCard } from "../components/FitDayCard";
import { MacroHero } from "../components/MacroHero";
import { NutritionPanel } from "../NutritionPanel";
import type { PortionInput } from "../portion";
import { intOrNull, linesToList, numOrNull } from "../ui";

type FormLocationState = {
  draft?: ExtractFromVideoResult;
  reveal?: boolean;
  sourceUrl?: string;
};

export function RecipeFormPage() {
  const { id } = useParams();
  const editingId = id ? parseInt(id, 10) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const locState = location.state as FormLocationState | null;
  const draft = locState?.draft;
  const isManualNew = editingId == null && !draft;
  const showReveal = Boolean(locState?.reveal && draft?.nutrition);

  const [title, setTitle] = useState("");
  const [ingredientsText, setIngredientsText] = useState("");
  const [stepsText, setStepsText] = useState("");
  const [prepTime, setPrepTime] = useState("");
  const [cookTime, setCookTime] = useState("");
  const [servings, setServings] = useState("");
  const [dietaryFlags, setDietaryFlags] = useState<string[]>([]);
  const [nutrition, setNutrition] = useState<NutritionReport | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [sourcePlatform, setSourcePlatform] = useState<string | null>(null);
  const [sourceContextText, setSourceContextText] = useState<string | null>(null);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

  const [insights, setInsights] = useState<RecipeInsights | null>(null);
  const [portion, setPortion] = useState<PortionInput>({ amount: 1, unit: "serving" });
  const [recalcing, setRecalcing] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(editingId != null);
  const [saving, setSaving] = useState(false);

  // Load: existing recipe (edit) or import draft (new).
  useEffect(() => {
    let cancelled = false;
    if (editingId != null && !Number.isFinite(editingId)) {
      setError("Recipe not found.");
      setLoading(false);
      return;
    }
    if (editingId != null) {
      setLoading(true);
      void api
        .fetchRecipe(editingId)
        .then((r) => {
          if (cancelled) return;
          setTitle(r.title);
          setIngredientsText(r.ingredients.join("\n"));
          setStepsText(r.steps.join("\n"));
          setPrepTime(r.prep_time_min != null ? String(r.prep_time_min) : "");
          setCookTime(r.cook_time_min != null ? String(r.cook_time_min) : "");
          setServings(r.servings != null ? String(r.servings) : "");
          setDietaryFlags(r.dietary_flags ?? []);
          setNutrition(r.nutrition);
          setSourceUrl(r.source_url);
          setSourcePlatform(r.source_platform);
          setSourceContextText(r.source_context_text);
          setThumbnailUrl(r.thumbnail_url);
        })
        .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load"))
        .finally(() => !cancelled && setLoading(false));
    } else if (draft) {
      setTitle(draft.title);
      setIngredientsText(draft.ingredients.join("\n"));
      setStepsText(draft.steps.join("\n"));
      setPrepTime(draft.prep_time_min != null ? String(draft.prep_time_min) : "");
      setCookTime(draft.cook_time_min != null ? String(draft.cook_time_min) : "");
      setServings(draft.servings != null ? String(draft.servings) : "");
      setDietaryFlags(draft.dietary_flags ?? []);
      setNutrition(draft.nutrition);
      setSourceUrl(draft.source_url);
      setSourcePlatform(draft.source_platform);
      setSourceContextText(draft.source_context_text);
      setThumbnailUrl(draft.thumbnail_url);
      const platform = draft.source_platform
        ? `From ${draft.source_platform.charAt(0).toUpperCase()}${draft.source_platform.slice(1)}. `
        : "";
      const mode = draft.used_ai
        ? "We drafted this recipe from your video."
        : "We drafted this recipe from the video text — review carefully.";
      setBanner(`${platform}${mode} Edit anything that looks off, then save.`);
      if (!draft.nutrition && draft.ingredients.length > 0) {
        void api
          .computeNutrition(draft.ingredients, draft.servings, draft.source_context_text)
          .then(setNutrition)
          .catch(() => undefined);
      }
    }
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId]);

  const refreshInsights = useCallback(async (ingredients: string[], srv: number | null, nut: NutritionReport | null) => {
    if (ingredients.length === 0) {
      setInsights(null);
      return;
    }
    try {
      setInsights(await api.getInsights(ingredients, srv, nut));
    } catch {
      /* insights are best-effort */
    }
  }, []);

  // Auto-fetch insights when the ingredient list settles (rule-based, cheap).
  useEffect(() => {
    const ings = linesToList(ingredientsText);
    const t = setTimeout(() => void refreshInsights(ings, numOrNull(servings), nutrition), 500);
    return () => clearTimeout(t);
  }, [ingredientsText, servings, nutrition, refreshInsights]);

  function toggleFlag(flag: string) {
    setDietaryFlags((prev) => (prev.includes(flag) ? prev.filter((f) => f !== flag) : [...prev, flag]));
  }

  async function calcMacros() {
    setRecalcing(true);
    setError(null);
    try {
      const report = await api.computeNutrition(
        linesToList(ingredientsText),
        numOrNull(servings),
        sourceContextText,
      );
      setNutrition(report);
      setPortion({ amount: 1, unit: "serving" });
      if (report.servings != null && report.servings > 0) {
        setServings(String(report.servings));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nutrition lookup failed");
    } finally {
      setRecalcing(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Add a recipe title.");
      return;
    }
    if (cleanTitle.length > 200) {
      setError("Title must be at most 200 characters.");
      return;
    }
    const ingredients = linesToList(ingredientsText);
    const steps = linesToList(stepsText);
    if (ingredients.length === 0) {
      setError("Add at least one ingredient.");
      return;
    }
    if (steps.length === 0) {
      setError("Add at least one step.");
      return;
    }
    if (prepTime.trim() && intOrNull(prepTime, { min: 0, max: 100000 }) == null) {
      setError("Prep time must be a whole number of minutes.");
      return;
    }
    if (cookTime.trim() && intOrNull(cookTime, { min: 0, max: 100000 }) == null) {
      setError("Cook time must be a whole number of minutes.");
      return;
    }
    if (servings.trim() && intOrNull(servings, { min: 1, max: 100 }) == null) {
      setError("Servings must be a whole number between 1 and 100.");
      return;
    }
    const payload = {
      title: cleanTitle,
      ingredients,
      steps,
      prep_time_min: intOrNull(prepTime, { min: 0, max: 100000 }),
      cook_time_min: intOrNull(cookTime, { min: 0, max: 100000 }),
      servings: intOrNull(servings, { min: 1, max: 100 }),
      dietary_flags: dietaryFlags,
    };

    // Persist calculated macros on save; compute now if user skipped the button.
    let nutritionToSave = nutrition;
    if (!nutritionToSave?.total?.calories && !nutritionToSave?.per_serving?.calories && ingredients.length > 0) {
      try {
        nutritionToSave = await api.computeNutrition(ingredients, payload.servings, sourceContextText);
        setNutrition(nutritionToSave);
      } catch {
        /* save without nutrition if lookup fails */
      }
    }

    setSaving(true);
    try {
      if (editingId != null) {
        await api.updateRecipe(editingId, {
          ...payload,
          nutrition: nutritionToSave,
          source_context_text: sourceContextText,
        });
        navigate(`/recipe/${editingId}`);
      } else {
        const created = await api.createRecipe({
          ...payload,
          source_url: sourceUrl,
          source_platform: sourcePlatform,
          source_context_text: sourceContextText,
          thumbnail_url: thumbnailUrl,
          nutrition: nutritionToSave,
        });
        navigate(`/recipe/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p style={{ color: "var(--text-muted)" }}>Loading…</p>;

  return (
    <section className={`page ${showReveal ? "reveal-card-spring" : "reveal-up"}`}>
      {showReveal && nutrition?.per_serving ? (
        <div className="card macro-reveal-card" style={{ padding: 0, overflow: "hidden", marginBottom: "1rem" }}>
          <MacroHero
            animate
            calories={nutrition.per_serving.calories}
            nutrition={nutrition.per_serving}
            subtitle="per serving — from your video"
          />
        </div>
      ) : null}

      <h1 className="page-title" style={{ fontSize: "1.35rem" }}>
        {editingId != null ? "Edit recipe" : isManualNew ? "New recipe" : "Review & save"}
      </h1>
      {isManualNew ? (
        <p className="page-sub" style={{ marginTop: 0 }}>
          Enter your recipe by hand — no video link required.
        </p>
      ) : null}

      {banner ? (
        <div className="card" role="status" style={{ borderColor: "var(--accent)", color: "var(--info-text)", marginBottom: "1rem", fontSize: "0.88rem" }}>
          {banner}
        </div>
      ) : null}
      {error ? (
        <div className="card" role="alert" style={{ color: "var(--danger-soft-text)", marginBottom: "1rem" }}>
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="form-stack">
        <label className="field">
          <span className="field__label">Title</span>
          <input
            className="input"
            type="text"
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Recipe name"
          />
        </label>

        <div className="form-grid-3">
          <label className="field">
            <span className="field__label">Prep (min)</span>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              min={0}
              max={100000}
              step={1}
              value={prepTime}
              onChange={(e) => setPrepTime(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Cook (min)</span>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              min={0}
              max={100000}
              step={1}
              value={cookTime}
              onChange={(e) => setCookTime(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Servings</span>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              min={1}
              max={100}
              step={1}
              value={servings}
              onChange={(e) => setServings(e.target.value)}
            />
          </label>
        </div>

        <div className="form-section">
          <span className="field__label">Dietary flags</span>
          <div className="chip-row">
            {DIETARY_FLAGS.map((flag) => (
              <button
                key={flag}
                type="button"
                className={`chip ${dietaryFlags.includes(flag) ? "chip--on" : ""}`}
                onClick={() => toggleFlag(flag)}
              >
                {flag
                  .split("-")
                  .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
                  .join(" ")}
              </button>
            ))}
          </div>
        </div>

        <label className="field">
          <span className="field__label">Ingredients (one per line)</span>
          <textarea
            className="textarea"
            value={ingredientsText}
            onChange={(e) => setIngredientsText(e.target.value)}
            rows={7}
            required
            placeholder={"2 eggs\n1 tbsp butter\nSalt"}
          />
        </label>
        <label className="field">
          <span className="field__label">Steps (one per line)</span>
          <textarea
            className="textarea"
            value={stepsText}
            onChange={(e) => setStepsText(e.target.value)}
            rows={6}
            required
            placeholder={"Whisk the eggs\nMelt butter in a pan\nScramble gently"}
          />
        </label>

        <label className="field">
          <span className="field__label">
            {isManualNew ? "Stated macros (optional)" : "Video caption (optional — for exact stated macros)"}
          </span>
          <textarea
            className="textarea"
            value={sourceContextText ?? ""}
            onChange={(e) => setSourceContextText(e.target.value.trim() || null)}
            rows={3}
            maxLength={20000}
            placeholder={
              isManualNew
                ? "Paste macros from packaging or notes, e.g.\n396 calories per serving\n32g protein"
                : "Paste caption text with macros, e.g.\nMacros for one (makes 8)\n396 calories\n38g C | 14g F | 32g P"
            }
          />
        </label>

        <div className="card nutrition-portion-box" style={{ padding: "0.85rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", marginBottom: nutrition ? "0.6rem" : 0 }}>
            <strong style={{ color: "var(--text)" }}>Nutrition &amp; macros</strong>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => void calcMacros()}
              disabled={recalcing || linesToList(ingredientsText).length === 0}
              style={{ padding: "0.35rem 0.7rem", fontSize: "0.82rem" }}
            >
              {recalcing ? "Calculating…" : nutrition ? "Recalculate" : "Calculate macros"}
            </button>
          </div>
          {nutrition ? (
            <NutritionPanel nutrition={nutrition} portion={portion} onPortionChange={setPortion} />
          ) : (
            <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--text-muted)" }}>
              {isManualNew
                ? "Add ingredients, then calculate — or paste stated macros above for exact values."
                : "Uses exact macros from the video caption when available (stable on recalculate)."}
              {!isManualNew && !sourceContextText ? " Re-import the video to store the caption for accurate recalc." : ""}
            </p>
          )}
        </div>

        {insights ? <FitDayCard insights={insights} /> : null}

        <div className="btn-row">
          <button type="submit" className="btn btn--primary" style={{ flex: 1 }} disabled={saving}>
            {saving ? "Saving…" : editingId == null ? "Save to cookbook" : "Save changes"}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => navigate(-1)} disabled={saving}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
