import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { Recipe, RecipeInsights, RecipeUpgradeResponse } from "../api";
import * as api from "../api";
import { CookStepViewer } from "../components/CookStepViewer";
import { DietaryTags } from "../components/DietaryTags";
import { FavoriteButton } from "../components/FavoriteButton";
import { FitDayCard } from "../components/FitDayCard";
import { LogMealModal } from "../components/LogMealModal";
import { MacroHero } from "../components/MacroHero";
import { RecipeThumb } from "../components/RecipeThumb";
import { NutritionPanel } from "../NutritionPanel";
import type { PortionInput } from "../portion";
import { useFavorites } from "../context/FavoritesContext";
import { useShoppingCart } from "../context/ShoppingCartContext";
import { platformOpenLabel } from "../lib/videoUrl";
import { canShareRecipe, shareRecipe } from "../lib/shareRecipe";
import { portionNutrition } from "../portion";

type Tab = "nutrition" | "cook" | "upgrades" | "original";

const FEMININE_VOICE_HINTS = [
  "samantha",
  "ava",
  "jenny",
  "aria",
  "zira",
  "susan",
  "karen",
  "moira",
  "tessa",
  "fiona",
  "victoria",
  "allison",
  "female",
  "google us english",
];

const MASCULINE_VOICE_HINTS = ["daniel", "alex", "fred", "thomas", "male"];

function preferredCookVoice(): SpeechSynthesisVoice | null {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  const scored = voices
    .filter((voice) => voice.lang.toLowerCase().startsWith("en"))
    .map((voice) => {
      const name = voice.name.toLowerCase();
      let score = 0;
      if (voice.localService) score += 2;
      if (voice.default) score += 1;
      if (voice.lang.toLowerCase().startsWith("en-us")) score += 2;
      if (FEMININE_VOICE_HINTS.some((hint) => name.includes(hint))) score += 10;
      if (MASCULINE_VOICE_HINTS.some((hint) => name.includes(hint))) score -= 8;
      return { voice, score };
    })
    .sort((a, b) => b.score - a.score);

  return scored[0]?.voice ?? voices[0] ?? null;
}

export function RecipeDetailPage() {
  const { id } = useParams();
  const recipeId = id ? parseInt(id, 10) : null;
  const navigate = useNavigate();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [insights, setInsights] = useState<RecipeInsights | null>(null);
  const [upgrades, setUpgrades] = useState<RecipeUpgradeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("nutrition");
  const [portion, setPortion] = useState<PortionInput>({ amount: 1, unit: "serving" });
  const [showLog, setShowLog] = useState(false);
  const [doneSteps, setDoneSteps] = useState<Set<number>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  const [cartMsg, setCartMsg] = useState<string | null>(null);
  const [shareMsg, setShareMsg] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [cookVoice, setCookVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [showDeletePrompt, setShowDeletePrompt] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const wakeRef = useRef<{ release: () => Promise<void> } | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const { addRecipe, recipeEntryCount } = useShoppingCart();
  const { removeFavorite } = useFavorites();

  useEffect(() => {
    if (recipeId == null) return;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    setUpgrades(null);
    void api
      .fetchRecipe(recipeId)
      .then((r) => {
        if (cancelled) return;
        setRecipe(r);
        return Promise.all([
          api.getInsights(r.ingredients, r.servings, r.nutrition).then((i) => !cancelled && setInsights(i)),
          api.getRecipeUpgrades({
            title: r.title,
            ingredients: r.ingredients,
            steps: r.steps,
            servings: r.servings,
            nutrition: r.nutrition,
          }).then((u) => !cancelled && setUpgrades(u)),
        ]).catch(() => undefined);
      })
      .catch((e) => !cancelled && setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [recipeId]);

  useEffect(() => {
    if (tab !== "cook") {
      void wakeRef.current?.release();
      wakeRef.current = null;
      return;
    }
    if ("wakeLock" in navigator) {
      void navigator.wakeLock.request("screen").then((s) => {
        wakeRef.current = s;
      }).catch(() => undefined);
    }
    return () => {
      void wakeRef.current?.release();
    };
  }, [tab]);

  useEffect(() => {
    const loadVoice = () => setCookVoice(preferredCookVoice());
    loadVoice();
    window.speechSynthesis?.addEventListener("voiceschanged", loadVoice);
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      window.speechSynthesis?.cancel();
      window.speechSynthesis?.removeEventListener("voiceschanged", loadVoice);
    };
  }, []);

  async function handleRefreshNutrition() {
    if (!recipe) return;
    setRefreshing(true);
    setErr(null);
    try {
      const updated = await api.refreshRecipeNutrition(recipe.id);
      setRecipe(updated);
      const i = await api.getInsights(updated.ingredients, updated.servings, updated.nutrition);
      setInsights(i);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleDelete() {
    if (!recipe) return;
    setDeleting(true);
    setDeleteErr(null);
    try {
      await api.deleteRecipe(recipe.id);
      removeFavorite(recipe.id);
      setShowDeletePrompt(false);
      navigate("/cookbook");
    } catch (e) {
      setDeleteErr(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  function narrationText(): string {
    const fallbackNarration = [
      recipe?.title ? `Starting ${recipe.title}.` : "Starting this recipe.",
      ...((recipe?.steps ?? []).map((s, i) => `Step ${i + 1}. ${s}`)),
    ].join(" ");
    return upgrades?.cook_narration?.length
      ? upgrades.cook_narration.join(" ")
      : fallbackNarration;
  }

  function stopReadAloud() {
    audioRef.current?.pause();
    audioRef.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function speakWithBrowserVoice(narration: string, reason?: string) {
    if (reason) {
      setCartMsg(reason);
      globalThis.setTimeout(() => setCartMsg(null), 3200);
    }
    if (!("speechSynthesis" in window)) {
      setSpeaking(false);
      setCartMsg("Read-aloud is not supported in this browser.");
      globalThis.setTimeout(() => setCartMsg(null), 2800);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(narration);
    const voice = cookVoice ?? preferredCookVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 0.94;
    utterance.pitch = 1.08;
    utterance.volume = 1;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  async function handleReadAloud() {
    if (speaking) {
      stopReadAloud();
      return;
    }
    const narration = narrationText();
    if (!narration.trim()) return;
    setSpeaking(true);
    try {
      const blob = await api.synthesizeSpeech(narration);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setSpeaking(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        speakWithBrowserVoice(narration, "AI voice could not play — using device voice.");
      };
      try {
        await audio.play();
      } catch (e) {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        throw e;
      }
    } catch (err) {
      const reason =
        err instanceof Error && err.message
          ? `AI voice unavailable (${err.message}) — using device voice.`
          : "AI voice unavailable — using device voice.";
      speakWithBrowserVoice(narration, reason);
    }
  }

  if (loading) return <p style={{ color: "var(--text-muted)" }}>Loading…</p>;
  if (err) return <div className="card" role="alert" style={{ color: "var(--danger-soft-text)" }}>{err}</div>;
  if (!recipe) return null;

  const perServing = recipe.nutrition?.per_serving;
  const scaled = recipe.nutrition
    ? portionNutrition(recipe.nutrition, portion).portion
    : null;
  const displayNutrition = scaled ?? perServing;

  const tags: string[] = [];
  if (recipe.dietary_flags?.length) tags.push(...recipe.dietary_flags);
  if (perServing?.protein_g != null && perServing.protein_g >= 25) tags.push("high-protein");

  return (
    <article className="page reveal-up">
      <button type="button" className="btn btn--ghost" style={{ marginBottom: "0.75rem", padding: "0.35rem 0.7rem", fontSize: "0.82rem" }} onClick={() => navigate(-1)}>
        ← Back
      </button>

      <RecipeThumb
        variant="hero"
        recipeId={recipe.id}
        title={recipe.title}
        thumbnailUrl={recipe.thumbnail_url}
        sourceUrl={recipe.source_url}
        sourcePlatform={recipe.source_platform}
        calories={perServing?.calories}
        proteinG={perServing?.protein_g}
      />

      <header style={{ marginBottom: "1rem", marginTop: "1rem" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.75rem" }}>
          <h1 className="page-title" style={{ fontSize: "1.4rem", wordBreak: "break-word", margin: 0, flex: 1 }}>
            {recipe.title}
          </h1>
          <FavoriteButton recipeId={recipe.id} showLabel />
        </div>
        {recipe.servings != null ? (
          <p className="page-sub" style={{ margin: "0.25rem 0 0" }}>Makes {recipe.servings} servings</p>
        ) : null}
        {tags.length ? <DietaryTags tags={tags} /> : null}
      </header>

      {displayNutrition?.calories != null ? (
        <section className="card" style={{ padding: 0, overflow: "hidden", marginBottom: "1rem" }}>
          <MacroHero
            animate
            calories={displayNutrition.calories}
            nutrition={displayNutrition}
            subtitle="per serving"
          />
        </section>
      ) : null}

      {insights ? <FitDayCard insights={insights} /> : null}

      {cartMsg ? (
        <div className="alert alert--success" role="status" style={{ marginBottom: "0.75rem" }}>
          {cartMsg}
        </div>
      ) : null}

      {shareMsg ? (
        <div className="alert alert--success" role="status" style={{ marginBottom: "0.75rem" }}>
          {shareMsg}
        </div>
      ) : null}

      <div className="btn-row" style={{ margin: "1rem 0" }}>
        {canShareRecipe() ? (
          <button
            type="button"
            className="btn btn--secondary"
            style={{ flex: 1 }}
            onClick={() => {
              void shareRecipe(recipe).then((result) => {
                if (result === "shared") {
                  setShareMsg("Ready to share — pick an app from the share sheet.");
                  window.setTimeout(() => setShareMsg(null), 2800);
                } else if (result === "unavailable") {
                  setShareMsg("Sharing is not available on this device.");
                  window.setTimeout(() => setShareMsg(null), 2800);
                }
              });
            }}
          >
            Share recipe
          </button>
        ) : null}
        <button type="button" className="btn btn--secondary" style={{ flex: 1 }} onClick={() => navigate(`/edit/${recipe.id}`)}>
          Edit recipe
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          style={{ flex: 1 }}
          disabled={!recipe.ingredients.length}
          onClick={() => {
            const n = recipeEntryCount(recipe.id);
            addRecipe({ id: recipe.id, title: recipe.title, ingredients: recipe.ingredients });
            setCartMsg(
              n > 0
                ? `Added again (${n + 1}× in cart) — ingredients merged in shopping list.`
                : "Added to shopping list — ingredients merged automatically.",
            );
            window.setTimeout(() => setCartMsg(null), 2800);
          }}
        >
          Add to cart
        </button>
        {recipe.nutrition ? (
          <button type="button" className="btn btn--primary" style={{ flex: 1 }} onClick={() => setShowLog(true)}>
            Log to today
          </button>
        ) : null}
      </div>

      <div className="tabs">
        {(["nutrition", "cook", "upgrades", "original"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`tabs__btn ${tab === t ? "tabs__btn--active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "nutrition" ? "Nutrition" : t === "cook" ? "Cook" : t === "upgrades" ? "Upgrades" : "Original"}
          </button>
        ))}
      </div>

      {tab === "nutrition" && recipe.nutrition ? (
        <section className="card">
          {recipe.source_url ? (
            <div style={{ marginBottom: "0.75rem" }}>
              <button
                type="button"
                className="btn btn--secondary"
                style={{ width: "100%", fontSize: "0.82rem" }}
                disabled={refreshing}
                onClick={() => void handleRefreshNutrition()}
              >
                {refreshing ? "Refreshing…" : "Refresh macros from video"}
              </button>
            </div>
          ) : null}
          <NutritionPanel nutrition={recipe.nutrition} portion={portion} onPortionChange={setPortion} />
        </section>
      ) : null}

      {tab === "nutrition" && !recipe.nutrition ? (
        <p className="card" style={{ color: "var(--text-muted)" }}>No nutrition data — edit recipe to calculate macros.</p>
      ) : null}

      {tab === "cook" ? (
        <section className="cook-mode">
          <p className="cook-mode__hint">
            Cook mode — screen stays awake. Tap steps as you go.
          </p>
          <button type="button" className="btn btn--secondary btn--block" style={{ marginBottom: "0.85rem" }} onClick={handleReadAloud}>
            {speaking ? "Stop read-aloud" : "Read recipe aloud"}
          </button>
          <CookStepViewer
            steps={recipe.steps}
            doneSteps={doneSteps}
            onToggleStep={(i) => {
              setDoneSteps((prev) => {
                const next = new Set(prev);
                if (next.has(i)) next.delete(i);
                else next.add(i);
                return next;
              });
            }}
          />
          <h3 style={{ fontSize: "0.95rem", color: "var(--text-muted)", marginTop: "1.25rem" }}>Ingredients</h3>
          <ul style={{ paddingLeft: "1.1rem", margin: 0 }}>
            {recipe.ingredients.map((line, i) => (
              <li key={i} style={{ marginBottom: "0.35rem" }}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {tab === "upgrades" ? (
        <section className="form-stack">
          {!upgrades ? (
            <p className="card" style={{ color: "var(--text-muted)" }}>Loading upgrades…</p>
          ) : (
            <>
              <div className="card">
                <h2 style={{ fontSize: "1rem", margin: "0 0 0.5rem" }}>Grocery estimate</h2>
                <p style={{ margin: "0 0 0.75rem", color: "var(--text-muted)", fontSize: "0.86rem" }}>
                  {upgrades.pricing.total_best_price != null
                    ? `Estimated ingredient use: ${upgrades.pricing.currency} ${upgrades.pricing.total_best_price.toFixed(2)}`
                    : "Add ingredient quantities to estimate grocery cost."}
                </p>
                <div className="upgrade-list">
                  {upgrades.pricing.items.slice(0, 8).map((item, i) => (
                    <div key={`${item.ingredient}-${i}`} className="upgrade-row">
                      <div>
                        <p className="upgrade-row__title">{item.ingredient}</p>
                        <p className="upgrade-row__meta">
                          {item.best_price != null && item.best_store
                            ? `${item.best_store}: ${upgrades.pricing.currency} ${item.best_price.toFixed(2)}`
                            : item.notes[0] ?? "No estimate yet"}
                        </p>
                      </div>
                      {item.quantity_label ? <span className="pill-soft">{item.quantity_label}</span> : null}
                    </div>
                  ))}
                </div>
                {upgrades.pricing.notes.map((note) => (
                  <p key={note} style={{ margin: "0.55rem 0 0", color: "var(--text-dim)", fontSize: "0.76rem" }}>
                    {note}
                  </p>
                ))}
              </div>

              {upgrades.repairs.length ? (
                <div className="card">
                  <h2 style={{ fontSize: "1rem", margin: "0 0 0.65rem" }}>Recipe repair</h2>
                  <ul className="upgrade-bullets">
                    {upgrades.repairs.map((r, i) => (
                      <li key={`${r.field}-${i}`}>
                        <strong>{r.field.replace("_", " ")}:</strong> {r.suggestion}
                        <span>{r.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {upgrades.low_calorie_options.length ? (
                <div className="card">
                  <h2 style={{ fontSize: "1rem", margin: "0 0 0.65rem" }}>Lower-calorie options</h2>
                  <ul className="upgrade-bullets">
                    {upgrades.low_calorie_options.map((opt, i) => (
                      <li key={`${opt.title}-${i}`}>
                        <strong>{opt.title}:</strong> {opt.suggestion}
                        {opt.estimated_savings ? <span>{opt.estimated_savings}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {upgrades.substitutions.length ? (
                <div className="card">
                  <h2 style={{ fontSize: "1rem", margin: "0 0 0.65rem" }}>Cheaper or easier swaps</h2>
                  <ul className="upgrade-bullets">
                    {upgrades.substitutions.map((s, i) => (
                      <li key={`${s.ingredient}-${i}`}>
                        <strong>{s.ingredient}:</strong> {s.suggestion}
                        <span>{s.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {tab === "original" ? (
        <section className="card">
          {recipe.source_url ? (
            <>
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.9rem", color: "var(--text-muted)" }}>
                Re-watch the source video if the AI missed an ingredient.
              </p>
              <a href={recipe.source_url} target="_blank" rel="noreferrer" className="btn btn--primary" style={{ display: "inline-block", textDecoration: "none" }}>
                {platformOpenLabel(recipe.source_platform)}
              </a>
            </>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>No source link saved.</p>
          )}
        </section>
      ) : null}

      <div className="btn-row" style={{ marginTop: "1.5rem" }}>
        <button type="button" className="btn btn--danger" onClick={() => {
          setDeleteErr(null);
          setShowDeletePrompt(true);
        }}>
          Delete
        </button>
      </div>

      {showDeletePrompt ? (
        <div className="modal-backdrop" role="presentation" onClick={() => !deleting && setShowDeletePrompt(false)}>
          <div
            className="modal-sheet delete-prompt card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-recipe-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="delete-prompt__icon" aria-hidden="true">!</div>
            <h2 id="delete-recipe-title" className="delete-prompt__title">Delete this recipe?</h2>
            <p className="delete-prompt__text">
              <strong>{recipe.title}</strong> will be removed from your cookbook and favorites. This cannot be undone.
            </p>
            {deleteErr ? <div className="alert alert--error" role="alert">{deleteErr}</div> : null}
            <div className="delete-prompt__actions">
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => setShowDeletePrompt(false)}
                disabled={deleting}
              >
                Keep recipe
              </button>
              <button
                type="button"
                className="btn btn--danger"
                onClick={() => void handleDelete()}
                disabled={deleting}
              >
                {deleting ? "Deleting…" : "Delete recipe"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showLog && recipe.nutrition && scaled ? (
        <LogMealModal
          recipe={recipe}
          perServing={scaled}
          onClose={() => setShowLog(false)}
          onLogged={() => navigate("/home", { state: { mealLogged: true } })}
        />
      ) : null}
    </article>
  );
}
